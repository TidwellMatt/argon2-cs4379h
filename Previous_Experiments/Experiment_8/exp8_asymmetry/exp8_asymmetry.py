#!/usr/bin/env python3
"""Experiment 8: matched CPU/GPU Argon2 benchmarks, synthetic inputs only."""
import argparse, csv, hashlib, importlib.metadata, itertools, json, math, os, platform, random, statistics, subprocess, sys, time, threading, shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from argon2.low_level import Type, hash_secret, verify_secret
import numpy as np
import psutil

TYPES={'d':Type.D,'i':Type.I,'id':Type.ID}
SECRET=b'EXP8-synthetic-public!'
# Fixed controls: RFC 9106, prior GPU benchmark, and Exp7 tuned anchors.
CONTROLS={'rfc_low':('id',64,3,4),'rfc_high':('id',2048,1,4),
          'gpu_reference':('id',64,3,1),'tuned_d':('d',157,3,4),
          'tuned_i':('i',170,3,4),'tuned_id':('id',135,4,4),
          'exp7_best':('i',256,6,4),'exp7_best_d':('d',256,6,4),'exp7_best_id':('id',128,6,4)}
BUDGETS=(50,75,100,125,150,200,300,500,1000)
CPU_FIELDS=['config','variant','memory_mib','t','p','round','status','latency_ms','cpu_ms','concurrent_hps','concurrent_p95_ms','rss_peak_mib','available_mib','error']
GPU_FIELDS=['config','variant','memory_mib','t','p','round','status','gpu_hps','samples','gpu_temp_max_c','gpu_util_median','gpu_vram_peak_mib','gpu_vram_idle_mib','elapsed_s','returncode','error']

def key(c):
    v,m,t,p=c; return f'{v}_m{m}_t{t}_p{p}'
def row(c,r):
    v,m,t,p=c; return dict(config=key(c),variant=v,memory_mib=m,t=t,p=p,round=r)
def salt(c,i=0):
    return hashlib.sha256(f'exp8-public-salt/{key(c)}/{i}'.encode()).digest()[:16]
def hashit(c,i=0,password=SECRET):
    v,m,t,p=c
    return hash_secret(password,salt(c,i),t,m*1024,p,32,TYPES[v],version=19)
def dump(p,o):
    p.write_text(json.dumps(o,indent=2)+'\n',encoding='utf8')
def load(p): return json.loads(p.read_text(encoding='utf8'))
def readcsv(p):
    if not p.exists():return []
    with p.open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))
def append(p,fields,r):
    exists=p.exists() and p.stat().st_size>0
    with p.open('a',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields); 
        if not exists:w.writeheader()
        w.writerow(r);f.flush();os.fsync(f.fileno())
def writecsv(p,rows,fields=None):
    if fields is None:fields=list(rows[0]) if rows else ['config']
    with p.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def configs(stage):
    if stage=='pilot':
        base=[(v,64,3,p) for v in TYPES for p in (1,4)]
        base += [('id',m,t,p) for m,t in ((32,4),(128,2),(256,1),(256,2),(512,1)) for p in (1,4)]
    elif stage=='screen':base=list(itertools.product(TYPES,(16,32,64,128,256,512),(1,2,3,4,5,6),(1,2,4,8)))
    else:base=list(itertools.product(TYPES,(16,32,64,128,256,512,1024,2048),(1,2,3,4,5,6),(1,2,4,8)))
    return sorted(set(base)|set(CONTROLS.values()))

def cpu(c,r,workers,inner):
    a=row(c,r); available=psutil.virtual_memory().available/2**20; a['available_mib']=round(available,1)
    # Conservative guard; do not interpret skipped configurations as an advantage.
    if c[1]*workers > available*.60:
        return dict(a,status='skipped',error='memory guard: requested working memory exceeds 60% of available RAM')
    try:
        h=hashit(c,0); assert verify_secret(h,SECRET,TYPES[c[0]])
        ls=[]; cs=[]; process=psutil.Process(); rss=process.memory_info().rss
        for i in range(inner):
            start=time.perf_counter(); cpu0=time.process_time(); hashit(c,r*100+i+1)
            ls.append((time.perf_counter()-start)*1000);cs.append((time.process_time()-cpu0)*1000)
        # Closed-loop batches, 2 waves per round; native argon2 CFFI releases GIL.
        # Sample whole process working set while the hashes are actually in flight.
        import threading
        stop=threading.Event(); peaks=[rss]
        def monitor():
            while not stop.is_set():
                peaks[0]=max(peaks[0],process.memory_info().rss);stop.wait(.005)
        def task(i):
            s=time.perf_counter();hashit(c,100000+r*100+i);return (time.perf_counter()-s)*1000
        with ThreadPoolExecutor(max_workers=workers) as pool:
            mon=threading.Thread(target=monitor,daemon=True);mon.start();s=time.perf_counter()
            try: times=list(pool.map(task,range(workers*2))); elapsed=time.perf_counter()-s
            finally: stop.set();mon.join()
        return dict(a,status='ok',latency_ms=statistics.median(ls),cpu_ms=statistics.median(cs),concurrent_hps=workers*2/elapsed,concurrent_p95_ms=float(np.percentile(times,95)),rss_peak_mib=peaks[0]/2**20,error='')
    except Exception as e:return dict(a,status='failed',error=repr(e))

def invoke(exe,args,timeout):
    return subprocess.run([str(exe),*map(str,args)],cwd=exe.parent,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',timeout=timeout)
def setup_inputs(out):
    p=out/'synthetic_inputs';p.mkdir(exist_ok=True)
    (p/'known.txt').write_bytes(SECRET+b'\n')
    # Workload is deliberately disjoint from the public known input; no real credentials.
    w=p/'workload.txt'
    if not w.exists():
        tmp=w.with_suffix('.tmp')
        with tmp.open('wb') as f:
            for i in range(1_000_000):f.write(f'EXP8-synthetic-{i:07d}\n'.encode())
        tmp.replace(w)
    return p

def parse_status(text):
    samples=[]; terminal=None
    for line in text.splitlines():
        try: o=json.loads(line.strip())
        except (ValueError,TypeError):continue
        if not isinstance(o,dict) or 'status' not in o:continue
        terminal=o['status']
        if terminal!=3:continue
        ds=o.get('devices',[])
        # Strictly one active GPU. Do not sum CPU or multi-device performance.
        if len(ds)!=1 or ds[0].get('device_type')!='GPU' or '4090' not in ds[0].get('device_name',''):continue
        d=ds[0]; h=d.get('speed',0)
        if isinstance(h,(int,float)) and h>0 and math.isfinite(h):samples.append(d)
    return samples,terminal

def vram_sample():
    exe=shutil.which('nvidia-smi')
    if not exe:return None
    try:
        r=subprocess.run([exe,'--query-gpu=name,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
        vals=[float(x.rsplit(',',1)[1]) for x in r.stdout.splitlines() if '4090' in x]
        return vals[0] if len(vals)==1 else None
    except (ValueError,IndexError,OSError,subprocess.SubprocessError):return None

def gpu(c,r,exe,out,inputs,seconds,backend):
    a=row(c,r);log=out/'gpu_logs';log.mkdir(exist_ok=True);k=key(c)
    target=inputs/(k+'.phc'); known=inputs/(k+'.verified.json'); answer=inputs/(k+'.answer')
    flags=['-m','34000','-a','0','--potfile-disable','--restore-disable','--logfile-disable','--hwmon-temp-abort','85']
    flags+=['--backend-ignore-opencl'] if backend=='cuda' else ['--backend-ignore-cuda','-D','2']
    try:
        if not known.exists():
            if c[1]>psutil.virtual_memory().available/2**20*.60:
                return dict(a,status='skipped',error='memory guard for synthetic target generation')
            target.write_bytes(hashit(c,0)+b'\n');answer.unlink(missing_ok=True)
            result=invoke(exe,flags+['--outfile',answer,'--outfile-format','2',target,inputs/'known.txt'],180)
            (log/(k+'_verify.txt')).write_text(result.stdout,encoding='utf8')
            if result.returncode!=0 or not answer.exists() or answer.read_bytes().strip()!=SECRET:
                return dict(a,status='failed',returncode=result.returncode,error='GPU known-input verification failed; see verify log')
            dump(known,{'backend':backend,'target_sha256':hashlib.sha256(target.read_bytes()).hexdigest()});answer.unlink()
        elif load(known)!={'backend':backend,'target_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}:
            raise ValueError('cached verification does not match target/backend')
        idle=vram_sample(); readings=[]; stop=threading.Event()
        def monitor_gpu():
            while not stop.is_set():
                x=vram_sample()
                if x is not None:readings.append(x)
                stop.wait(1)
        mon=threading.Thread(target=monitor_gpu,daemon=True);mon.start();start=time.perf_counter()
        try:
            result=invoke(exe,flags+['-w','3','--status','--status-json','--status-timer','2','--runtime',str(seconds),target,inputs/'workload.txt'],seconds+180)
        finally:stop.set();mon.join()
        elapsed=time.perf_counter()-start
        (log/f'{k}_r{r:03d}.txt').write_text(result.stdout,encoding='utf8')
        samples,terminal=parse_status(result.stdout)
        if terminal not in (5,11) or result.returncode not in (0,1,4) or len(samples)<3:
            return dict(a,status='failed',samples=len(samples),elapsed_s=elapsed,returncode=result.returncode,error=f'no valid sustained GPU run: final status={terminal}; see log')
        samples=samples[1:] # remove first positive sample; not independent repetitions
        temps=[d['temp'] for d in samples if isinstance(d.get('temp'),(int,float)) and d['temp']>=0]
        util=[d['util'] for d in samples if isinstance(d.get('util'),(int,float)) and d['util']>=0]
        return dict(a,status='ok',gpu_hps=statistics.median(d['speed'] for d in samples),samples=len(samples),gpu_temp_max_c=max(temps) if temps else '',gpu_util_median=statistics.median(util) if util else '',gpu_vram_peak_mib=max(readings) if readings else '',gpu_vram_idle_mib=idle if idle is not None else '',elapsed_s=elapsed,returncode=result.returncode,error='')
    except (Exception,) as e:
        if isinstance(e,subprocess.TimeoutExpired):
            txt=e.stdout or b''; (log/f'{k}_r{r:03d}_timeout.txt').write_text(txt.decode(errors='replace') if isinstance(txt,bytes) else txt,encoding='utf8')
        return dict(a,status='failed',error=repr(e))

def analyze(out):
    manifest=load(out/'manifest.json'); cs=[tuple(c) for c in manifest['configs']]; n=manifest['rounds']
    cr=readcsv(out/'cpu_raw.csv');gr=readcsv(out/'gpu_raw.csv'); groups={};summary=[]
    def med(rs,field):return statistics.median(float(r[field]) for r in rs)
    for c in cs:
        k=key(c);C=[r for r in cr if r['config']==k and r['status']=='ok'];G=[r for r in gr if r['config']==k and r['status']=='ok']
        if not C or not G or len(C)!=n or len(G)!=n or {int(x['round']) for x in C}!=set(range(1,n+1)) or {int(x['round']) for x in G}!=set(range(1,n+1)):continue
        l=med(C,'latency_ms');g=med(G,'gpu_hps');s=dict(config=k,variant=c[0],memory_mib=c[1],t=c[2],p=c[3],cpu_rounds=len(C),gpu_rounds=len(G),latency_ms=l,cpu_ms=med(C,'cpu_ms'),concurrent_hps=med(C,'concurrent_hps'),concurrent_p95_ms=med(C,'concurrent_p95_ms'),rss_peak_mib=med(C,'rss_peak_mib'),gpu_hps=g,cost_product=l*g/1000)
        s['gpu_vram_peak_mib']=statistics.median(float(r['gpu_vram_peak_mib']) for r in G if r.get('gpu_vram_peak_mib')) if any(r.get('gpu_vram_peak_mib') for r in G) else '';groups[k]=(C,G);summary.append(s)
    summary.sort(key=lambda r:r['cost_product']);writecsv(out/'ranking.csv',summary)
    fronts=[]
    for v in TYPES:
        sub=[s for s in summary if s['variant']==v]
        for s in sub:
            if not any(z['latency_ms']<=s['latency_ms'] and z['gpu_hps']<=s['gpu_hps'] and (z['latency_ms']<s['latency_ms'] or z['gpu_hps']<s['gpu_hps']) for z in sub):fronts.append(s)
    writecsv(out/'pareto_same_variant.csv',fronts)
    budgets=[]
    for v,b in itertools.product(TYPES,BUDGETS):
        sub=[s for s in summary if s['variant']==v and s['latency_ms']<=b]
        if sub:budgets.append(dict(latency_ceiling_ms=b,**min(sub,key=lambda s:s['gpu_hps'])))
    writecsv(out/'latency_budgets.csv',budgets)
    # Relative comparisons: require same variant; mark resource tradeoff separately.
    # Bootstrap rounds (not within-run GPU samples); intervals exploratory, unadjusted.
    rng=np.random.default_rng(808);comparisons=[]; control_keys={key(c) for c in CONTROLS.values()}
    for name,c in CONTROLS.items():
        ref=next((s for s in summary if s['config']==key(c)),None)
        if ref is None:continue
        for s in summary:
            if s['variant']!=ref['variant'] or s['config']==ref['config']:continue
            lr=s['latency_ms']/ref['latency_ms'];gratio=s['gpu_hps']/ref['gpu_hps'];cpu_ratio=s['cpu_ms']/ref['cpu_ms'];qratio=s['concurrent_hps']/ref['concurrent_hps'];mr=s['memory_mib']/ref['memory_mib'];rssratio=s['rss_peak_mib']/ref['rss_peak_mib'];pr=s['concurrent_p95_ms']/ref['concurrent_p95_ms']
            ci={}
            if n>=5:
                for j,field in ((0,'latency_ms'),(1,'gpu_hps')):
                    A=np.array([float(x[field]) for x in groups[s['config']][j]]);B=np.array([float(x[field]) for x in groups[ref['config']][j]])
                    ix=rng.integers(0,n,size=(4000,n));iy=rng.integers(0,n,size=(4000,n));rr=np.median(A[ix],axis=1)/np.median(B[iy],axis=1)
                    ci[field+'_ratio_lo'],ci[field+'_ratio_hi']=np.quantile(rr,[.025,.975]).tolist()
            else:ci={x:'' for x in ('latency_ms_ratio_lo','latency_ms_ratio_hi','gpu_hps_ratio_lo','gpu_hps_ratio_hi')}
            comparisons.append(dict(control=name,control_config=ref['config'],candidate=s['config'],latency_ratio=lr,gpu_ratio=gratio,cpu_cost_ratio=cpu_ratio,concurrent_hps_ratio=qratio,concurrent_p95_ratio=pr,memory_ratio=mr,rss_ratio=rssratio,latency_gpu_improvement=lr<=1 and gratio<1,no_defender_resource_regression=lr<=1 and cpu_ratio<=1 and qratio>=1 and mr<=1 and rssratio<=1 and pr<=1 and gratio<1,**ci))
    writecsv(out/'control_comparisons.csv',comparisons)
    # Freeze confirmation selection: promising same-variant pairs, plus per-variant Pareto candidates and controls.
    selected={s['config'] for s in summary if s['config'] in control_keys}
    candidates=sorted([p for p in comparisons if p['latency_gpu_improvement'] and p['candidate'] not in control_keys],key=lambda p:(not p['no_defender_resource_regression'],p['gpu_ratio'],p['latency_ratio']))
    for p in candidates:
        if len(selected-control_keys)>=10:break
        selected.add(p['candidate'])
    for s in sorted(fronts,key=lambda z:z['cost_product']):
        if len(selected-control_keys)>=10:break
        selected.add(s['config'])
    dump(out/'confirmation_selection.json',{'source_manifest_sha256':hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest(),'configs':[list(c) for c in cs if key(c) in selected],'selection_rule':'up to 10 non-control candidates: first same-variant latency/GPU improvements (strict resource wins first), then lowest-product same-variant Pareto candidates; all successfully measured named controls'})
    dump(out/'analysis_notes.json',{'planned_configs':len(cs),'fully_measured_configs':len(summary),'planned_rounds':n,'cpu_records':len(cr),'gpu_records':len(gr),'cpu_non_ok':sum(r['status']!='ok' for r in cr),'gpu_non_ok':sum(r['status']!='ok' for r in gr),'point_estimate_latency_gpu_improvements':sum(p['latency_gpu_improvement'] for p in comparisons),'point_estimate_strict_resource_improvements':sum(p['no_defender_resource_regression'] for p in comparisons),'warning':'Only same-variant comparisons are interpreted. GPU throughput is implementation/hardware specific; unadjusted bootstrap intervals are exploratory; no cryptographic security proof.'})
    if summary:
        import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(9,6))
        for v in TYPES:
            sub=[s for s in summary if s['variant']==v];ax.scatter([s['latency_ms'] for s in sub],[s['gpu_hps'] for s in sub],label='Argon2'+v,alpha=.65)
        for s in summary:
            if s['config'] in control_keys:ax.annotate(s['config'],(s['latency_ms'],s['gpu_hps']),fontsize=7)
        ax.set(xlabel='CPU authentication latency (ms)',ylabel='GPU throughput (hashes/s)',xscale='log',yscale='log',title='Experiment 8: matched CPU and GPU measurements');ax.legend();fig.tight_layout();fig.savefig(out/'cpu_gpu_pareto.png',dpi=160);plt.close(fig)
    print(f'Analysis: {len(summary)}/{len(cs)} fully measured configurations; see analysis_notes.json',flush=True)

def selftest():
    for v in TYPES:
        c=(v,16,2,2); h=hashit(c);assert verify_secret(h,SECRET,TYPES[v]); assert h!=hashit(c,1)
    # Independent published Hashcat module test vector.
    h=b'$argon2id$v=19$m=65536,t=3,p=1$FBMjI4RJBhIykCgol1KEJA$2ky5GAdhT1kH4kIgPN/oERE3Taiy43vNN70a3HpiKQU'
    assert verify_secret(h,b'hashcat',Type.ID)
    sample={'status':3,'devices':[{'device_type':'GPU','device_name':'NVIDIA GeForce RTX 4090','speed':1530}]}
    assert len(parse_status(json.dumps(sample)+'\n'+json.dumps({'status':11}))[0])==1
    assert len(configs('full'))==579
    assert len(SECRET)==len(b'EXP8-synthetic-0000000')
    print('CPU known-answer verification and GPU JSON parser tests passed. Actual GPU requires pilot.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hashcat',type=Path);p.add_argument('--stage',choices=['pilot','screen','full','confirm'],default='pilot');p.add_argument('--from-results',type=Path);p.add_argument('--out',type=Path,default=Path('results/exp8_pilot'));p.add_argument('--rounds',type=int);p.add_argument('--gpu-seconds',type=int,default=18);p.add_argument('--workers',type=int,default=4);p.add_argument('--cpu-inner',type=int,default=3);p.add_argument('--backend',choices=['cuda','opencl'],default='cuda');p.add_argument('--self-test',action='store_true');p.add_argument('--analyze-only',action='store_true');p.add_argument('--resume',action='store_true');a=p.parse_args()
    if a.self_test:selftest();return
    out=a.out.resolve()
    if a.analyze_only:analyze(out);return
    if not a.hashcat:p.error('--hashcat is required')
    exe=a.hashcat.resolve()
    if not exe.is_file():p.error('Hashcat executable not found')
    if not 10<=a.gpu_seconds<=120 or not 1<=a.workers<=8 or not 1<=a.cpu_inner<=20:p.error('gpu-seconds 10–120, workers 1–8, cpu-inner 1–20')
    n=a.rounds if a.rounds is not None else (12 if a.stage=='confirm' else 2)
    if not 1<=n<=100:p.error('rounds must be 1–100')
    if a.stage=='confirm':
        if not a.from_results:p.error('--from-results required for confirm')
        sel=load(a.from_results/'confirmation_selection.json'); cs=[tuple(c) for c in sel['configs']]
        if not cs:p.error('no successfully measured candidates in source results')
        # Only allow tuples from the predefined synthetic grid.
        if not set(cs)<=set(configs('full')):p.error('invalid confirmation selection')
    else:cs=configs(a.stage)
    manifest=dict(stage=a.stage,configs=cs,rounds=n,gpu_seconds=a.gpu_seconds,workers=a.workers,cpu_inner=a.cpu_inner,backend=a.backend,hashcat=str(exe),hashcat_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),seed=808,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    manifest=json.loads(json.dumps(manifest))
    out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():
        if not a.resume or load(out/'manifest.json')!=manifest:p.error('output already exists; use matching --resume or a new output directory')
    else:
        dump(out/'manifest.json',manifest)
        version=invoke(exe,['--version'],30).stdout;info=invoke(exe,['-I'],60).stdout
        (out/'hashcat_info.txt').write_text(info,encoding='utf8')
        dump(out/'environment.json',dict(platform=platform.platform(),processor=platform.processor(),logical_cpus=os.cpu_count(),ram_mib=psutil.virtual_memory().total/2**20,python=sys.version,argon2_cffi=importlib.metadata.version('argon2-cffi'),hashcat_version=version.strip(),hashcat_executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),created=time.strftime('%Y-%m-%dT%H:%M:%S%z')))
    inputs=setup_inputs(out)
    print(f'{len(cs)} configurations x {n} rounds; separate CPU and GPU phases. Output: {out}',flush=True)
    for phase,fields in [('cpu',CPU_FIELDS),('gpu',GPU_FIELDS)]:
        path=out/(phase+'_raw.csv');done={(r['config'],int(r['round'])) for r in readcsv(path)}
        for r in range(1,n+1):
            order=cs[:];random.Random(808+r+ (10000 if phase=='gpu' else 0)).shuffle(order)
            if phase=='gpu' and a.stage=='pilot' and r==1:
                order.remove(CONTROLS['gpu_reference']);order.insert(0,CONTROLS['gpu_reference'])
            for i,c in enumerate(order,1):
                if (key(c),r) in done:continue
                result=cpu(c,r,a.workers,a.cpu_inner) if phase=='cpu' else gpu(c,r,exe,out,inputs,a.gpu_seconds,a.backend)
                append(path,fields,result);print(f'{phase.upper()} round {r}/{n} {i}/{len(cs)} {key(c)}: {result["status"]} {result.get("latency_ms",result.get("gpu_hps",result.get("error","")))}',flush=True)
                # Check the known working reference first in the pilot; record other unsupported configurations.
                if phase=='gpu' and a.stage=='pilot' and c==CONTROLS['gpu_reference'] and result['status']!='ok':
                    print('Pilot reference GPU configuration failed. Inspect gpu_logs before further testing. Remaining configurations not measured.',flush=True);analyze(out);raise SystemExit(2)
    analyze(out)
if __name__=='__main__':main()
