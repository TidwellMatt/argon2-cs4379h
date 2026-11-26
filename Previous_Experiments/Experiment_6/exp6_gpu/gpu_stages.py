"""Synthetic GPU Argon2 stage benchmarks; serial cascade estimates, NOT measured hybrid hashes."""
import argparse,csv,json,math,re,shutil,statistics,subprocess,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def key(s): return (s['kind'],int(s['m']),int(s['t']),int(s['p']))
def stage_name(k): return f'{k[0]}_m{k[1]}_t{k[2]}_p{k[3]}'
def parse_ns(txt):
    # argon2-gpu-bench machine-readable mean output: exactly one positive number.
    # Fail closed if the upstream CLI prints a different format.
    lines=[line.strip() for line in txt.splitlines() if line.strip()]
    nums=[float(x) for x in lines if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',x)]
    if len(nums)!=1 or not math.isfinite(nums[0]) or nums[0]<=0: raise ValueError('Expected one positive numeric ns-per-hash value; inspect raw log')
    return nums[0]
def serial_rate(ns): return 1e9/sum(ns)
def csvwrite(path, rows, fields=None):
    if fields is None: fields=list(rows[0]) if rows else ['status']
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def capture(cmd,cwd,timeout=180):
    try:
        p=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,errors='replace',timeout=timeout)
        return p.returncode,p.stdout,p.stderr
    except (OSError,subprocess.TimeoutExpired) as e:return -1,'',str(e)
def self_test():
    assert parse_ns('12345\n')==12345
    assert parse_ns('1.2e6\n')==1200000
    for bad in ('0','nan','-10','5\n6','unsupported'):
        try:parse_ns(bad)
        except ValueError:pass
        else:raise AssertionError(bad)
    assert serial_rate([1e6,1e6])==500
    assert serial_rate([2e6,1e6])==serial_rate([1e6,2e6])
    p=json.loads((ROOT/'gpu_plan.json').read_text()); assert all(s['kind'] in ('argon2d','argon2i','argon2id') and 1<=s['m']<=192 and 1<=s['t']<=4 and s['p'] in (1,2,4) for c in p['configurations'] for s in c['stages'])
    print('PASS: parser, model, order symmetry, fixed synthetic plan.')
def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--self-test',action='store_true'); ap.add_argument('--bench',type=Path); ap.add_argument('--test',type=Path,help='Optional upstream argon2-gpu-test executable'); ap.add_argument('--backend',choices=['cuda','opencl'],default='opencl'); ap.add_argument('--device',type=int,default=0); ap.add_argument('--cwd',type=Path,help='Upstream checkout containing data/kernels'); ap.add_argument('--out',type=Path,default=Path('results/gpu_stages')); ap.add_argument('--smoke',action='store_true'); a=ap.parse_args()
    if a.self_test:self_test();return
    if not a.bench or not a.bench.is_file():ap.error('Provide the path to a built argon2-gpu-bench executable. See README.')
    binary=str(a.bench.resolve()); cwd=str(a.cwd.resolve() if a.cwd else a.bench.resolve().parent)
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):ap.error('Use an empty output directory')
    logs=out/'logs';logs.mkdir(); plan=json.loads((ROOT/'gpu_plan.json').read_text()); configs=plan['configurations'];
    if a.smoke:configs=[c for c in configs if c['name'].lower()=='argon2id baseline']
    stages=sorted({key(s) for c in configs for s in c['stages']}); batches=[4] if a.smoke else [4,16,32,64]; repeats=1 if a.smoke else 3; samples=3 if a.smoke else 5
    meta=dict(backend=a.backend,device=a.device,executable=binary,cwd=cwd,stage_count=len(stages),batches=batches,repeats=repeats,samples_per_run=samples,hybrid_gpu_measured=False,synthetic_only=True,scope='Measured standalone stages; serial hybrid estimates only')
    (out/'environment.json').write_text(json.dumps(meta,indent=2));(out/'plan.json').write_text(json.dumps(configs,indent=2))
    rc,stdout,stderr=capture([binary,'--help'],cwd);(logs/'help.txt').write_text(stdout+'\n'+stderr,encoding='utf-8')
    if a.test:
        rc,stdout,stderr=capture([str(a.test.resolve()),'-m',a.backend,'-d',str(a.device)],cwd,600);(logs/'upstream_test.txt').write_text(stdout+'\n'+stderr,encoding='utf-8');meta['upstream_test_returncode']=rc
        if rc!=0:raise SystemExit('Upstream tests failed. Inspect logs/upstream_test.txt.')
    smi=shutil.which('nvidia-smi'); stop=threading.Event(); telemetry=[]; active=['setup']; cols=['index','name','utilization.gpu','memory.used','memory.total','temperature.gpu','power.draw']
    def monitor():
        while not stop.is_set():
            label=active[0];rc,txt,_=capture([smi,'--query-gpu='+','.join(cols),'--format=csv,noheader,nounits'],cwd,5)
            if rc==0:
                for row in csv.reader(txt.splitlines()):
                    if len(row)==len(cols):telemetry.append(dict(zip(['unix_time','run']+cols,[time.time(),label]+[x.strip() for x in row])))
            stop.wait(.5)
    th=threading.Thread(target=monitor,daemon=True) if smi else None
    if th:th.start()
    raw=[]
    try:
        for batch in batches:
            for k in stages:
                for repeat in range(1,repeats+1):
                    tag=f'{stage_name(k)}_b{batch}_r{repeat}';active[0]=tag
                    cmd=[binary,'-t',k[0].removeprefix('argon2'),'-v','1.3','-m',a.backend,'-d',str(a.device),'-k','by-segment','-b',str(batch),'-s',str(samples),'-T',str(k[2]),'-M',str(k[1]*1024),'-L',str(k[3]),'-o','ns-per-hash','--output-mode','mean']
                    rc,stdout,stderr=capture(cmd,cwd);(logs/(tag+'.txt')).write_text(json.dumps(cmd)+'\nSTDOUT:\n'+stdout+'\nSTDERR:\n'+stderr,encoding='utf-8'); ns=None;status='ok'
                    try:
                        if rc:raise ValueError('backend failed')
                        ns=parse_ns(stdout)
                    except ValueError as e:status=str(e)
                    raw.append(dict(stage=stage_name(k),kind=k[0],memory_mib=k[1],passes=k[2],lanes=k[3],batch=batch,repeat=repeat,status=status,returncode=rc,ns_per_hash=ns,derivations_per_s=1e9/ns if ns else None));csvwrite(out/'raw_gpu_stages.csv',raw)
                    print(tag,status,flush=True)
                    if a.smoke and ns is None:raise SystemExit('Smoke failed. Inspect raw log; no GPU measurement claimed.')
    finally:
        stop.set()
        if th:th.join(timeout=6)
        csvwrite(out/'gpu_telemetry.csv',telemetry,['unix_time','run']+cols)
    measures={}; summary=[]
    for k in stages:
        for batch in batches:
            v=[r['ns_per_hash'] for r in raw if r['stage']==stage_name(k) and r['batch']==batch and r['status']=='ok'];complete=len(v)==repeats
            ns=statistics.median(v) if v else None
            summary.append(dict(stage=stage_name(k),batch=batch,successful_repeats=len(v),expected_repeats=repeats,complete=complete,median_ns_per_hash=ns,median_derived_rate=1e9/ns if ns else None,min_ns=min(v) if v else None,max_ns=max(v) if v else None))
            if complete:measures[(k,batch)]=ns
    csvwrite(out/'gpu_stage_summary.csv',summary)
    models=[]
    for c in configs:
        for batch in batches:
            ns=[measures.get((key(s),batch)) for s in c['stages']];complete=all(v is not None for v in ns)
            models.append(dict(name=c['name'],batch=batch,measurement_kind='measured standalone' if len(ns)==1 else 'serial stage model ONLY',cpu_latency_ms=c['cpu_latency_ms'],cpu_latency_eligible=c['cpu_latency_eligible'],cpu_8worker_per_s=c['cpu_8worker_per_s'],complete=complete,gpu_rate_per_s=serial_rate(ns) if complete else None,stages=';'.join(stage_name(key(s)) for s in c['stages'])))
    csvwrite(out/'gpu_comparison.csv',models);meta['successful_stage_runs']=sum(r['status']=='ok' for r in raw);meta['total_stage_runs']=len(raw);meta['telemetry_samples']=len(telemetry);(out/'environment.json').write_text(json.dumps(meta,indent=2));print('Saved',out,'; verify device and GPU telemetry. Hybrids are modeled, not measured.')
if __name__=='__main__':main()
