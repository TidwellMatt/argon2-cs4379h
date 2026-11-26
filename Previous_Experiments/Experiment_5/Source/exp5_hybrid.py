"""Experiment 5: controlled KDF cascade performance study, not production crypto."""
import argparse, base64, csv, hashlib, hmac, importlib.metadata, json, os, platform
import random, ssl, statistics as st, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
from argon2.low_level import Type, hash_secret_raw
import psutil

@dataclass(frozen=True)
class Config:
    name: str
    order: str
    m: int
    t: int
    iterations: int = 0
    n: int = 0
    sp: int = 0

def fixture(i):
    return (f'exp5-synthetic-password-{i}'.encode(), hashlib.sha256(f'exp5-salt-{i}'.encode()).digest()[:16])

def stage_salt(c, label, salt):
    return hashlib.sha256(b'exp5/v1/'+c.order.encode()+b'/'+label.encode()+salt).digest()[:16]

def derive(c, password, salt):
    value = password
    for label in c.order:
        s = stage_salt(c,label,salt)
        if label == 'a':
            value = hash_secret_raw(value,s,c.t,c.m,1,32,Type.ID,version=19)
        elif label == 'p':
            value = hashlib.pbkdf2_hmac('sha256',value,s,c.iterations,dklen=32)
        elif label == 's':
            value = hashlib.scrypt(value,salt=s,n=c.n,r=8,p=c.sp,maxmem=2*c.m*1024+4*1024*1024,dklen=32)
        else: raise ValueError(label)
    return value

def latency(c, repeats):
    derive(c,*fixture(0)); samples=[]
    for i in range(repeats):
        start=time.perf_counter(); derive(c,*fixture(i)); samples.append(time.perf_counter()-start)
    return st.median(samples)

def calibrate(m,t,repeats):
    baseline=Config('Argon2id alone','a',m,t)
    target=latency(baseline,repeats); configs=[baseline]; logs=[]
    logs.append({'name':baseline.name,'target_ms':target*1000,'calibration_ms':target*1000})
    for passes in sorted({1,t-1},reverse=True):
        for order in ('pa',):
            name=('PBKDF2 -> Argon2id' if order=='pa' else 'Argon2id -> PBKDF2')+f' (t={passes})'
            a=latency(Config('cal','a',m,passes),repeats); budget=max(target-a,.0001)
            iterations=10000; best=None
            for _ in range(7):
                c=Config(name,order,m,passes,iterations); elapsed=latency(c,repeats)
                if best is None or abs(elapsed-target)<abs(best[1]-target): best=(c,elapsed)
                if abs(elapsed-target)/target<.035: break
                ratio=max(.3,min(3,budget/max(elapsed-a,.0001)))
                iterations=max(1000,min(5000000,round(iterations*ratio/1000)*1000))
            c,elapsed=best; configs.append(c); logs.append({'name':name,'target_ms':target*1000,'calibration_ms':elapsed*1000})
            reverse=Config(f'Argon2id -> PBKDF2 (t={passes})','ap',m,passes,c.iterations)
            configs.append(reverse); logs.append({'name':reverse.name,'target_ms':target*1000,'calibration_ms':latency(reverse,repeats)*1000})
    # Discrete scrypt grid. At r=8, dominant working memory is N KiB.
    # Calibrate one order and use the identical parameters for the reverse order.
    candidates=[]
    for passes in sorted({1,t-1}):
        for n in (1024,2048,4096,8192,16384,32768,65536):
            if n>m: continue
            for sp in (1,2):
                c=Config('scrypt -> Argon2id','sa',m,passes,n=n,sp=sp)
                elapsed=latency(c,max(2,repeats//2)); candidates.append((abs(elapsed-target),c,elapsed))
    _,c,elapsed=min(candidates,key=lambda x:x[0]); configs.append(c)
    logs.append({'name':c.name,'target_ms':target*1000,'calibration_ms':elapsed*1000})
    reverse=Config('Argon2id -> scrypt','as',m,c.t,n=c.n,sp=c.sp); configs.append(reverse)
    logs.append({'name':reverse.name,'target_ms':target*1000,'calibration_ms':latency(reverse,repeats)*1000})
    return configs,target,logs

def verify(configs):
    assert hashlib.pbkdf2_hmac('sha256',b'password',b'salt',1,32).hex()=='120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'
    assert hashlib.scrypt(b'',salt=b'',n=16,r=1,p=1,dklen=64).hex()==('77d6576238657b203b19ca42c18a0497f16b4844e3074ae8dfdffa3fede21442' 'fcd0069ded0948f8326a753a0fc81f17e8d3e0fb2e0d3628cf35e20c38d18906')
    p,s=fixture(0)
    for c in configs:
        tag=derive(c,p,s)
        assert len(tag)==32 and hmac.compare_digest(tag,derive(c,p,s))
        assert not hmac.compare_digest(tag,derive(c,p+b'!',s))
        assert not hmac.compare_digest(tag,derive(c,p,fixture(1)[1]))
    from argon2 import PasswordHasher
    c=configs[0]
    encoded=PasswordHasher(time_cost=c.t,memory_cost=c.m,parallelism=1,hash_len=32,salt_len=16,type=Type.ID).hash(p,salt=stage_salt(c,'a',s))
    assert hmac.compare_digest(base64.b64decode(encoded.split('$')[-1]+'=='),derive(c,p,s))
    return 'PASS: PBKDF2 and scrypt known answers; Argon2 high-level cross-check; deterministic tags and changed inputs'

def worker(c,workers,jobs):
    proc=psutil.Process(); base=proc.memory_info().rss; peak=[base]; stop=threading.Event()
    def sample():
        while not stop.is_set():
            peak[0]=max(peak[0],proc.memory_info().rss); stop.wait(.002)
    def task(i):
        p,s=fixture(i); start=time.perf_counter(); derive(c,p,s); return (time.perf_counter()-start)*1000
    with ThreadPoolExecutor(max_workers=workers) as pool:
        monitor=threading.Thread(target=sample,daemon=True); monitor.start()
        start=time.perf_counter(); cpu=time.process_time()
        try:
            times=list(pool.map(task,range(jobs))); elapsed=time.perf_counter()-start; cpu=time.process_time()-cpu
        finally: stop.set(); monitor.join()
    return {'workers':workers,'jobs':jobs,'batch_ms':elapsed*1000,'throughput_per_s':jobs/elapsed,'cpu_ms_per_job':cpu*1000/jobs,'median_task_ms':st.median(times),'max_task_ms':max(times),'peak_rss_mib':peak[0]/2**20,'rss_delta_mib':max(0,peak[0]-base)/2**20}

def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def graphs(out,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=list(dict.fromkeys(r['name'] for r in rows)); workers=sorted({r['workers'] for r in rows})
    for field,title,unit,file in [('throughput_per_s','Synthetic derivation throughput','Derivations / second','throughput.png'),('peak_rss_mib','Sampled peak process memory','MiB','memory.png'),('median_task_ms','Median task service time','Milliseconds','latency.png')]:
        fig,ax=plt.subplots(figsize=(10,6))
        for name in names:
            rr=[next(r for r in rows if r['name']==name and r['workers']==w) for w in workers]
            ax.plot(workers,[r[field] for r in rr],marker='o',label=name+(' *' if not rr[0]['matched'] else ''))
        ax.set(title=title,xlabel='Concurrent worker threads (* unmatched latency)',ylabel=unit,xticks=workers); ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(out/file,dpi=160); plt.close(fig)
    rr=[r for r in rows if r['workers']==1]; target=rr[0]['median_task_ms']; fig,ax=plt.subplots(figsize=(10,5)); ax.barh([r['name'] for r in rr],[r['median_task_ms'] for r in rr]); ax.axvline(target,ls='--',label='Measured baseline'); ax.axvspan(target*.85,target*1.15,alpha=.15,label='±15% window'); ax.set(xlabel='Milliseconds',title='Independent single-worker latency check'); ax.legend(); fig.tight_layout(); fig.savefig(out/'calibration.png',dpi=160); plt.close(fig)

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--quick',action='store_true'); ap.add_argument('--self-test',action='store_true'); ap.add_argument('--out',type=Path,default=Path('results/exp5')); ap.add_argument('--memory-mib',type=int); ap.add_argument('--passes',type=int,default=3); ap.add_argument('--worker-json',help=argparse.SUPPRESS); ap.add_argument('--workers',type=int,default=1); ap.add_argument('--jobs',type=int,default=4); args=ap.parse_args()
    if args.worker_json:
        print(json.dumps(worker(Config(**json.loads(args.worker_json)),args.workers,args.jobs))); return
    if args.self_test:
        print(verify([Config('base','a',1024,1),Config('pa','pa',1024,1,1000),Config('ap','ap',1024,1,1000),Config('sa','sa',1024,1,n=1024,sp=1),Config('as','as',1024,1,n=1024,sp=1)])); return
    m=(args.memory_mib or (16 if args.quick else 64))*1024; t=args.passes
    if not 8192<=m<=262144 or not 2<=t<=6: ap.error('memory must be 8–256 MiB and passes 2–6')
    workers=[1,2] if args.quick else [1,2,4]; repeats=2 if args.quick else 5; jobs_per_worker=3 if args.quick else 6
    out=args.out; out.mkdir(parents=True,exist_ok=True)
    print('Calibrating...',flush=True); configs,target,cal=calibrate(m,t,5 if args.quick else 7); checks=verify(configs); print(checks,flush=True)
    raw=[]; plan=[(c,w,r) for r in range(repeats) for c in configs for w in workers]; random.Random(4379).shuffle(plan)
    for i,(c,w,r) in enumerate(plan,1):
        if i==1 or i%10==0: print(f'Batch {i}/{len(plan)}',flush=True)
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker-json',json.dumps(asdict(c)),'--workers',str(w),'--jobs',str(w*jobs_per_worker)],capture_output=True,text=True,check=True)
        raw.append({'name':c.name,'repeat':r+1,**json.loads(result.stdout)})
    write_csv(out/'raw_batches.csv',raw); write_csv(out/'calibration.csv',cal); write_csv(out/'configs.csv',[asdict(c) for c in configs]); summary=[]
    baseline=st.median(r['median_task_ms'] for r in raw if r['name']==configs[0].name and r['workers']==1)
    for c in configs:
        solo=st.median(r['median_task_ms'] for r in raw if r['name']==c.name and r['workers']==1); err=(solo/baseline-1)*100
        for w in workers:
            rr=[r for r in raw if r['name']==c.name and r['workers']==w]; fields=['batch_ms','throughput_per_s','cpu_ms_per_job','median_task_ms','max_task_ms','peak_rss_mib','rss_delta_mib']; row={'name':c.name,'workers':w,'repeats':len(rr),'calibration_target_ms':target*1000,'single_worker_error_pct':err,'matched':abs(err)<=15}; row.update({k:st.median(r[k] for r in rr) for k in fields}); row['throughput_min']=min(r['throughput_per_s'] for r in rr); row['throughput_max']=max(r['throughput_per_s'] for r in rr); summary.append(row)
    write_csv(out/'summary.csv',summary); graphs(out,summary)
    meta={'python':sys.version,'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'openssl':ssl.OPENSSL_VERSION,'argon2_cffi':importlib.metadata.version('argon2-cffi'),'psutil':psutil.__version__,'quick':args.quick,'calibration_target_ms':target*1000,'checks':checks,'memory_mib':m//1024,'passes':t,'worker_counts':workers,'repeats':repeats,'jobs_per_worker':jobs_per_worker,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    (out/'environment.json').write_text(json.dumps(meta,indent=2),encoding='utf-8'); print(f'Results: {out.resolve()}',flush=True)

if __name__=='__main__': main()
