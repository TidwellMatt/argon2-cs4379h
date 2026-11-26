"""Experiment 5B: exploratory KDF cascade benchmarks on synthetic inputs only.
Not a production password storage scheme or a password recovery tool.
"""
import argparse, base64, csv, hashlib, hmac, importlib.metadata as md, json, os
import platform, random, ssl, statistics as st, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from argon2.low_level import Type, hash_secret_raw
import psutil
try:
    import bcrypt
except ImportError:
    bcrypt = None


VARIANTS={'argon2id':Type.ID,'argon2i':Type.I,'argon2d':Type.D}
LABELS={'argon2id':'Argon2id','argon2i':'Argon2i','argon2d':'Argon2d'}
def a(m,t,variant='argon2id'): return {'kind':variant,'m':int(m),'t':int(t)}
def pb(d,it): return {'kind':'pbkdf2','digest':d,'iterations':int(it)}
def sc(n,r,p): return {'kind':'scrypt','n':n,'r':r,'p':p}
def bc(rounds): return {'kind':'bcrypt_pbkdf','rounds':int(rounds)}
def config(name, stages, family): return {'name':name,'stages':stages,'family':family}
def fixture(i):
    return f'exp5b-synthetic-{i}'.encode(), hashlib.sha256(f'exp5b-salt-{i}'.encode()).digest()[:16]
def stage_salt(salt,i): return hashlib.sha256(b'exp5b/v1/'+i.to_bytes(4,'big')+salt).digest()[:16]

def stage(s,value,salt):
    k=s['kind']
    if k in VARIANTS: return hash_secret_raw(value,salt,s['t'],s['m']*1024,1,32,VARIANTS[k],version=19)
    if k=='pbkdf2': return hashlib.pbkdf2_hmac(s['digest'],value,salt,s['iterations'],32)
    if k=='scrypt': return hashlib.scrypt(value,salt=salt,n=s['n'],r=s['r'],p=s['p'],maxmem=2*(128*s['n']*s['r'])+8*1024**2,dklen=32)
    if k=='bcrypt_pbkdf':
        if bcrypt is None: raise RuntimeError('Install bcrypt: python -m pip install bcrypt')
        return bcrypt.kdf(password=value,salt=salt,desired_key_bytes=32,rounds=s['rounds'],ignore_few_rounds=True)
    raise ValueError(k)

def derive(c,p,salt):
    for i,s in enumerate(c['stages']): p=stage(s,p,stage_salt(salt,i))
    return p

def latency(c,n=3):
    derive(c,*fixture(0)); times=[]
    for i in range(n):
        start=time.perf_counter(); derive(c,*fixture(i+1)); times.append(time.perf_counter()-start)
    return st.median(times)

def memory_mib(s):
    if s['kind'] in VARIANTS: return s['m']
    if s['kind']=='scrypt': return 128*s['n']*s['r']/2**20
    return 0

def verify(configs):
    assert hashlib.pbkdf2_hmac('sha256',b'password',b'salt',1,32).hex()=='120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'
    assert hashlib.pbkdf2_hmac('sha512',b'password',b'salt',1,32).hex()=='867f70cf1ade02cff3752599a3a53dc4af34c7a669815ae5d513554e1c8cf252'
    assert hashlib.scrypt(b'',salt=b'',n=16,r=1,p=1,dklen=64).hex()==('77d6576238657b203b19ca42c18a0497f16b4844e3074ae8dfdffa3fede21442fcd0069ded0948f8326a753a0fc81f17e8d3e0fb2e0d3628cf35e20c38d18906')
    from argon2 import PasswordHasher
    p,s=fixture(0)
    for v,typ in VARIANTS.items():
        c=config('test',[a(1,1,v)],'test')
        enc=PasswordHasher(time_cost=1,memory_cost=1024,parallelism=1,hash_len=32,salt_len=16,type=typ).hash(p,salt=stage_salt(s,0))
        assert hmac.compare_digest(base64.b64decode(enc.split('$')[-1]+'=='),derive(c,p,s))
    for c in configs:
        result=derive(c,p,s); assert len(result)==32
        assert hmac.compare_digest(result,derive(c,p,s))
        assert not hmac.compare_digest(result,derive(c,p+b'!',s))
        assert not hmac.compare_digest(result,derive(c,p,fixture(1)[1]))
    print('PASS: known answers (PBKDF2 SHA256/SHA512 and scrypt), Argon2 API cross-check, deterministic cascades and input sensitivity',flush=True)


def calibrate(m,t,cap,quick,include_bcrypt,variant):
    label=LABELS[variant]
    def ar(m,t): return a(m,t,variant)
    base=config(f'{label} baseline',[ar(m,t)],'baseline'); target=latency(base,5)
    configs=[base]; logs=[{'name':base['name'],'calibration_ms':target*1000,'target_ms':target*1000}]
    def add(c,elapsed=None):
        if elapsed is None: elapsed=latency(c,3)
        configs.append(c); logs.append({'name':c['name'],'calibration_ms':elapsed*1000,'target_ms':target*1000})
        print(f"  {c['name']}: {elapsed*1000:.1f} ms",flush=True)
    def standalone(s): return latency(config('cal',[s],'cal'),2)
    def pair(s1,s2,name,family):
        add(config(name+' -> '+label,[s2,s1],family))
        add(config(label+' -> '+name,[s1,s2],family))
    # Standalone memory-tuned comparator: match time by changing m, not just t.
    for passes in sorted({1,t-1}):
        mem=m; best=None
        for _ in range(5):
            c=config(f'{label} tuned t={passes}',[ar(mem,passes)],'tuned standalone')
            e=latency(c,3)
            if best is None or abs(e-target)<abs(best[1]-target): best=(c,e)
            if abs(e-target)/target<.025: break
            new=max(8,min(cap,round(mem*max(.5,min(2,target/e)))))
            if new==mem: break
            mem=new
        add(*best)
    # Same Argon2 memory across each of these cascades; tune second stage.
    for passes in sorted({1,t-1}):
        first=ar(m,passes); at=standalone(first); budget=max(.0002,target-at)
        for digest in ('sha256','sha512','sha3_256'):
            it=10000; best=None
            for _ in range(5):
                sec=pb(digest,it); e=standalone(sec)
                if best is None or abs(e-budget)<abs(best[1]-budget): best=(sec,e)
                if abs(e-budget)/budget<.025: break
                new=max(1000,min(4000000,round(it*max(.2,min(5,budget/e))/1000)*1000))
                if new==it: break
                it=new
            pair(first,best[0],f'PBKDF2-{digest} (a.t={passes})','PBKDF2 cascade')
        if include_bcrypt:
            single=standalone(bc(1)); rounds=max(1,min(128,round(budget/single)))
            grid=sorted({max(1,rounds-1),rounds,min(128,rounds+1)})
            sec=min((bc(r) for r in grid),key=lambda x:abs(standalone(x)-budget))
            pair(first,sec,f'bcrypt-PBKDF (a.t={passes})','bcrypt-PBKDF cascade')
    # Broaden scrypt r and p grid, tune second-stage latency, test one per pass
    # and another with greater permitted memory. Stage-only measurements are reused.
    print('  Screening scrypt parameters...',flush=True)
    grid=[]
    for n in (1024,2048,4096,8192,16384,32768,65536,131072):
        for r in ((4,8,12) if not quick else (4,8)):
            for p in ((1,2,3) if not quick else (1,2)):
                sec=sc(n,r,p); mem=memory_mib(sec)
                if mem>cap or mem<2 or mem*p>cap*1.5: continue
                grid.append((sec,standalone(sec)))
    for passes in sorted({1,t-1}):
        first=ar(m,passes); budget=max(.0002,target-standalone(first))
        fixed=[x for x in grid if memory_mib(x[0])<=m]
        sec=min(fixed,key=lambda x:abs(x[1]-budget))[0]
        pair(first,sec,f'scrypt (a.t={passes})','scrypt cascade')
    # Experimental memory-heavy split: spend time on a second Argon2id stage
    # with adjustable memory. It is a cascade, not equivalent to multiple passes.
    for primary in sorted({max(8,m//2),m}):
        first=ar(primary,1); budget=max(.0002,target-standalone(first)); mem=m; best=None
        for _ in range(5):
            sec=ar(mem,1); e=standalone(sec)
            if best is None or abs(e-budget)<abs(best[1]-budget): best=(sec,e)
            new=max(8,min(cap,round(mem*max(.4,min(2.5,budget/e)))))
            if new==mem or abs(e-budget)/budget<.03: break
            mem=new
        second=best[0]
        add(config(f'{label} {primary} MiB -> {label} {second["m"]} MiB',[first,second],'double Argon2'))
        if primary!=second['m']:
            add(config(f'{label} {second["m"]} MiB -> {label} {primary} MiB (reverse of {primary})',[second,first],'double Argon2'))
    # Mixed-variant cascades: same pair of parameters in both orders.
    for other in VARIANTS:
        if other==variant: continue
        first=ar(m,1); budget=max(.0002,target-standalone(first)); mem=m; best=None
        for _ in range(5):
            sec=a(mem,1,other); e=standalone(sec)
            if best is None or abs(e-budget)<abs(best[1]-budget): best=(sec,e)
            new=max(8,min(cap,round(mem*max(.4,min(2.5,budget/e)))))
            if new==mem or abs(e-budget)/budget<.03: break
            mem=new
        sec=best[0]; otherlabel=LABELS[other]
        add(config(f'{label} {m} MiB -> {otherlabel} {sec["m"]} MiB',[first,sec],'mixed Argon2'))
        add(config(f'{otherlabel} {sec["m"]} MiB -> {label} {m} MiB (reverse)',[sec,first],'mixed Argon2'))
    return configs,logs,target


def worker(c,w,jobs,offset):
    proc=psutil.Process(); baseline=proc.memory_info().rss; peak=[baseline]; stop=threading.Event()
    def monitor():
        while not stop.is_set():
            peak[0]=max(peak[0],proc.memory_info().rss); stop.wait(.002)
    def task(i):
        p,s=fixture(offset+i); start=time.perf_counter(); derive(c,p,s); return (time.perf_counter()-start)*1000
    with ThreadPoolExecutor(max_workers=w) as pool:
        thread=threading.Thread(target=monitor,daemon=True); thread.start(); start=time.perf_counter(); cpu=time.process_time()
        try:
            # Short Windows batches can return zero process CPU time. Extend
            # the sample in complete waves, with fresh synthetic inputs.
            times=[]; cpu_start=cpu
            while True:
                first=len(times)
                times.extend(pool.map(task,range(first,first+jobs)))
                elapsed=time.perf_counter()-start
                cpu=time.process_time()-cpu_start
                if (elapsed>=.15 and cpu>=.10) or elapsed>=2.0:
                    break
            jobs=len(times)
        finally:
            stop.set(); thread.join()
    return {'workers':w,'jobs':jobs,'throughput_per_s':jobs/elapsed,'median_task_ms':st.median(times),'cpu_ms_per_job':cpu*1000/jobs,'peak_rss_mib':peak[0]/2**20,'rss_delta_mib':max(0,peak[0]-baseline)/2**20}


def csvwrite(path,rows):
    if not rows: return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def summarize(configs,raw,workers,tolerance):
    base=configs[0]['name']; rows=[]
    def group(n,w): return [r for r in raw if r['name']==n and r['workers']==w]
    def med(n,w,key): return st.median(r[key] for r in group(n,w))
    for c in configs:
        name=c['name']; solo=med(name,1,'median_task_ms'); err=100*(solo/med(base,1,'median_task_ms')-1)
        for w in workers:
            rr=group(name,w); throughput=med(name,w,'throughput_per_s'); ratio=throughput/med(base,w,'throughput_per_s'); scaling=(throughput/med(name,1,'throughput_per_s'))/(med(base,w,'throughput_per_s')/med(base,1,'throughput_per_s'))
            row={'name':name,'family':c['family'],'workers':w,'repeats':len(rr),'solo_latency_ms':solo,'solo_error_pct':err,'matched':abs(err)<=tolerance,'throughput_per_s':throughput,'throughput_change_pct':100*(ratio-1),'relative_scaling':scaling,'throughput_min':min(r['throughput_per_s'] for r in rr),'throughput_max':max(r['throughput_per_s'] for r in rr)}
            for key in ('median_task_ms','cpu_ms_per_job','peak_rss_mib','rss_delta_mib'): row[key]=med(name,w,key)
            rows.append(row)
    for row in rows:
        controls=[r for r in rows if r['workers']==row['workers'] and r['matched'] and r['family'] in ('baseline','tuned standalone')]
        best=min(controls,key=lambda r:r['throughput_per_s'])
        row['best_matched_standalone']=best['name']
        row['change_vs_best_standalone_pct']=100*(row['throughput_per_s']/best['throughput_per_s']-1)
        row['candidate_improvement']=row['matched'] and row['family'] not in ('baseline','tuned standalone') and row['change_vs_best_standalone_pct']<0
    return rows

def graphs(out,rows,workers,tol):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rr=sorted([r for r in rows if r['workers']==max(workers)],key=lambda x:x['throughput_per_s'],reverse=True)
    labels=[r['name']+(' *' if not r['matched'] else '') for r in rr]; colors=['#a6a6a6' if not r['matched'] else '#237a8a' if r['family']!='baseline' else '#193a70' for r in rr]
    for key,title,unit,file in [('throughput_per_s','Concurrent synthetic derivation throughput','Derivations / second','throughput.png'),('solo_latency_ms','Independent single-worker latency','Milliseconds','latency.png'),('peak_rss_mib','Sampled peak process memory','MiB','memory.png'),('relative_scaling','Parallel scaling relative to baseline','Relative scaling (baseline = 1)','scaling.png')]:
        fig,ax=plt.subplots(figsize=(11,max(5,len(rr)*.31+1.5))); ax.barh(labels,[r[key] for r in rr],color=colors)
        if key=='relative_scaling': ax.axvline(1,ls='--',color='black',lw=1)
        if key=='solo_latency_ms':
            b=next(r[key] for r in rr if r['family']=='baseline'); ax.axvspan(b*(1-tol/100),b*(1+tol/100),alpha=.13,color='green')
        ax.set(title=f'{title} ({max(workers)} workers for concurrent metrics)',xlabel=unit); ax.tick_params(axis='y',labelsize=8); ax.grid(axis='x',alpha=.2); fig.tight_layout(); fig.savefig(out/file,dpi=150); plt.close(fig)

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--variant',choices=['all',*VARIANTS],default='all'); ap.add_argument('--self-test',action='store_true'); ap.add_argument('--quick',action='store_true'); ap.add_argument('--screen',action='store_true',help='Full-size memory and concurrency, fewer repetitions for candidate screening'); ap.add_argument('--smoke',action='store_true',help=argparse.SUPPRESS); ap.add_argument('--out',type=Path,default=Path('results/exp5b')); ap.add_argument('--memory-mib',type=int); ap.add_argument('--max-memory-mib',type=int); ap.add_argument('--passes',type=int,default=3); ap.add_argument('--max-workers',type=int,choices=[2,4,8],default=4); ap.add_argument('--tolerance',type=float,default=5); ap.add_argument('--skip-bcrypt',action='store_true'); ap.add_argument('--confirm-from',type=Path); ap.add_argument('--worker-json',help=argparse.SUPPRESS); ap.add_argument('--workers',type=int,default=1); ap.add_argument('--jobs',type=int,default=2); ap.add_argument('--offset',type=int,default=0); args=ap.parse_args()
    if args.worker_json:
        print(json.dumps(worker(json.loads(args.worker_json),args.workers,args.jobs,args.offset))); return
    include_bcrypt=bcrypt is not None and not args.skip_bcrypt
    if not include_bcrypt: print('NOTE: bcrypt-PBKDF skipped (dependency not installed or --skip-bcrypt).',flush=True)
    if args.self_test:
        configs=[config('test',[a(1,1),pb(d,1000)],'test') for d in ('sha256','sha512','sha3_256')]+[config('test',[sc(1024,8,1),a(1,1)],'test'),config('test',[a(1,1),a(2,1)],'test')]
        if include_bcrypt: configs.append(config('test',[bc(1),a(1,1)],'test'))
        configs += [config('test',[a(1,1,v),a(1,1,w)],'test') for v in VARIANTS for w in VARIANTS]
        verify(configs); return
    if args.variant=='all':
        # Run independent variant blocks with separate output and control latency.
        # Pass through original CLI options, replacing output/variant/confirmation paths.
        argv=[]; i=0; original=sys.argv[1:]
        while i<len(original):
            x=original[i]
            if x in ('--variant','--out','--confirm-from'): i+=2; continue
            if any(x.startswith(k+'=') for k in ('--variant','--out','--confirm-from')): i+=1; continue
            argv.append(x); i+=1
        args.out.mkdir(parents=True,exist_ok=True); aggregate=[]
        for v in VARIANTS:
            dest=args.out/v; extra=['--confirm-from',str(args.confirm_from/v)] if args.confirm_from else []
            print(f'\n=== {LABELS[v]} ===',flush=True)
            subprocess.run([sys.executable,str(Path(__file__).resolve()),*argv,'--variant',v,'--out',str(dest),*extra],check=True)
            with (dest/'ranking.csv').open(newline='',encoding='utf-8') as f:
                aggregate.extend({'baseline_variant':v,**r} for r in csv.DictReader(f))
        csvwrite(args.out/'all_variants_ranking.csv',aggregate)
        print('Combined rankings:',args.out/'all_variants_ranking.csv',flush=True); return
    m=args.memory_mib or (8 if args.smoke else 16 if args.quick else 64); cap=args.max_memory_mib or (m if args.smoke else 3*m)
    if not 8<=m<=256 or not m<=cap<=768 or not 2<=args.passes<=6 or not 0<args.tolerance<=20: ap.error('Use 8–256 MiB baseline, cap >= baseline and <=768 MiB, 2–6 passes, tolerance 0–20%')
    workers=[1,2] if args.quick or args.smoke else [w for w in (1,2,4,8) if w<=args.max_workers]
    repeats=1 if args.smoke else 2 if args.quick or args.screen else 5; per=1 if args.smoke else 3 if args.quick or args.screen else 6; out=args.out
    if args.confirm_from:
        if args.confirm_from.resolve()==out.resolve(): ap.error('Use a different output directory for confirmation')
        if args.quick or args.smoke or args.screen: ap.error('confirmation requires a full benchmark')
        old=json.loads((args.confirm_from/'configs.json').read_text());
        if old[0]['stages'][0]['kind']!=args.variant: ap.error('Confirmation variant does not match screening baseline')
        prev=list(csv.DictReader((args.confirm_from/'summary.csv').open(newline='',encoding='utf-8'))); wmax=max(int(r['workers']) for r in prev); workers=sorted({int(r['workers']) for r in prev}); rr=[r for r in prev if int(r['workers'])==wmax and r['matched']=='True' and r['family'] not in ('baseline','tuned standalone')]; rr.sort(key=lambda r:float(r['throughput_per_s'])); names={r['name'] for r in rr[:3]}; configs=[c for c in old if c['family'] in ('baseline','tuned standalone') or c['name'] in names]; logs=[]; target=None; repeats=7; per=8
        if not names: print('No matched hybrids in screening; confirming standalone controls only.',flush=True)
    else:
        if psutil.virtual_memory().available < (2*cap+256)*2**20: ap.error('Insufficient available RAM for calibration; reduce --max-memory-mib')
        print('Calibrating candidate families...',flush=True); configs,logs,target=calibrate(m,args.passes,cap,args.quick or args.smoke,include_bcrypt,args.variant)
    if len({c['name'] for c in configs})!=len(configs): raise RuntimeError('Duplicate configuration name')
    max_stage=max(memory_mib(s) for c in configs for s in c['stages']); required=(2*max_stage*max(workers)+256)*2**20
    if psutil.virtual_memory().available<required: ap.error('Insufficient available RAM for benchmark; close other programs or lower memory/worker limits')
    out.mkdir(parents=True,exist_ok=True); (out/'configs.json').write_text(json.dumps(configs,indent=2)); csvwrite(out/'calibration.csv',logs); verify(configs)
    plan=[(c,w,r) for r in range(repeats) for c in configs for w in workers]; seed=54380 if args.confirm_from else 54379; random.Random(seed).shuffle(plan); raw=[]
    for i,(c,w,r) in enumerate(plan,1):
        if i==1 or i%10==0 or i==len(plan): print(f'Batch {i}/{len(plan)}',flush=True)
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker-json',json.dumps(c),'--workers',str(w),'--jobs',str(w*per),'--offset',str((100000 if args.confirm_from else 1000)+r*100)],capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stderr or result.stdout)
        raw.append({'name':c['name'],'repeat':r+1,**json.loads(result.stdout)})
        if i%10==0: csvwrite(out/'raw_batches.csv',raw)
    csvwrite(out/'raw_batches.csv',raw); rows=summarize(configs,raw,workers,args.tolerance); csvwrite(out/'summary.csv',rows); graphs(out,rows,workers,args.tolerance)
    ranked=sorted([r for r in rows if r['workers']==max(workers)],key=lambda r:r['throughput_per_s']); csvwrite(out/'ranking.csv',ranked)
    meta={'baseline_variant':args.variant,'python':sys.version,'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'openssl':ssl.OPENSSL_VERSION,'argon2_cffi':md.version('argon2-cffi'),'bcrypt':md.version('bcrypt') if include_bcrypt else None,'psutil':psutil.__version__,'workers':workers,'repeats':repeats,'jobs_per_worker':per,'tolerance_pct':args.tolerance,'seed':seed,'confirmation_from':str(args.confirm_from) if args.confirm_from else None,'calibration_target_ms':target*1000 if target else None,'quick':args.quick,'screen':args.screen,'smoke':args.smoke,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}; (out/'environment.json').write_text(json.dumps(meta,indent=2))
    print(f'\nResults at {out.resolve()}\nMatched configurations at {max(workers)} workers (negative change = lower throughput):')
    for r in ranked:
        if r['matched']: print(f"{r['name']}: {r['throughput_per_s']:.2f}/s ({r['throughput_change_pct']:+.1f}%), solo {r['solo_error_pct']:+.1f}%, relative scaling {r['relative_scaling']:.3f}, vs best standalone {r['change_vs_best_standalone_pct']:+.1f}%")
    print('Screening only unless independently confirmed. No GPU/ASIC or real password recovery measured.')

if __name__=='__main__': main()
