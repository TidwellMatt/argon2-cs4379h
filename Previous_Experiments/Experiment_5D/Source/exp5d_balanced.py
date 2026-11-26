"""5D: balanced CPU synthetic derivation benchmark, derived from 5C configurations.
No password recovery. All inputs are generated fixtures. GPU baseline is separate.
"""
import argparse, copy, csv, json, math, os, random, statistics as st, subprocess, sys, time, platform
from pathlib import Path
import psutil
import exp5c_global as prev
import exp5b_core as core

HERE=Path(__file__).resolve().parent
CONTROL=prev.CONTROL
V=prev.VARIANTS

def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def dump(path,x): Path(path).write_text(json.dumps(x,indent=2),encoding='utf-8')
def key(x): return json.dumps(x,sort_keys=True)
def configs_for(source,smoke=False,skip_bcrypt=False):
    result=[]
    for c in source:
        if skip_bcrypt and any(s['kind']=='bcrypt_pbkdf' for s in c['stages']): continue
        if smoke and c['family'] not in CONTROL and c['family'] not in ('PBKDF2 cascade','mixed Argon2'): continue
        if smoke and c['family'] in CONTROL and c['family']!='baseline': continue
        if smoke and c['family'] not in CONTROL and sum(x['family'] not in CONTROL for x in result)>=12: continue
        for p in ((1,2) if smoke else (1,2,4)) if c['family'] not in CONTROL else (None,):
            d=copy.deepcopy(c)
            if p is not None:
                d['name']+=f' [p={p}]'
                for s in d['stages']:
                    if s['kind'] in V: s['p']=p
            if smoke:
                for s in d['stages']:
                    if s['kind'] in V: s['m']=max(1,round(s['m']/16))
                    elif s['kind']=='pbkdf2': s['iterations']=max(1,s['iterations']//16)
            result.append(d)
    return result

def scale_stage(s,factor,cap):
    s=copy.deepcopy(s); k=s['kind']
    if k in V: s['m']=max(1,min(cap,round(s['m']*factor)))
    elif k=='pbkdf2': s['iterations']=max(1,min(4000000,round(s['iterations']*factor)))
    elif k in ('bcrypt_pbkdf','cipher_workload'): s['rounds']=max(1,min(128 if k=='bcrypt_pbkdf' else 4096,round(s['rounds']*factor)))
    elif k=='scrypt':
        # Adjust discrete r and p, preserving n. If needed, n can be halved/doubled.
        desired=s['n']*s['r']*s['p']*factor
        candidates=[]
        for n in (max(1024,s['n']//2),s['n'],min(131072,s['n']*2)):
            for r in (2,4,6,8,10,12,16):
                for p in (1,2,3,4):
                    a=core.sc(n,r,p)
                    if core.memory_mib(a)<=cap: candidates.append(a)
        if candidates: s=min(candidates,key=lambda a:abs(math.log(a['n']*a['r']*a['p']/max(desired,1))))
    return s

def retune_pair(stages,target,cap,steps):
    # Tune a canonical unordered pair so forward and reverse always share parameters.
    # Prefer adjusting the non-Argon2 stage; if it cannot shrink enough, tune both.
    ss=copy.deepcopy(stages); best=None; seen=set()
    for step in range(steps):
        k=key(ss)
        if k in seen: break
        seen.add(k)
        e=[core.latency(core.config('fit',x,'fit'),2) for x in (ss,list(reversed(ss)))]
        score=max(abs(z-target) for z in e)
        if best is None or score<best[0]: best=(score,copy.deepcopy(ss),e)
        if score<=target*.018: break
        mean=st.mean(e); factor=max(.5,min(2,target/mean))
        non=[i for i,s in enumerate(ss) if s['kind'] not in V]
        if non and step==0:
            i=non[0]; cost=core.latency(core.config('fit',[ss[i]],'fit'),2)
            f=max(.2,min(4,(target-mean+cost)/max(cost,1e-8)))
            new=copy.deepcopy(ss); new[i]=scale_stage(ss[i],f,cap)
        else: new=[scale_stage(s,factor,cap) for s in ss]
        if key(new)==k: new=[scale_stage(s,factor,cap) for s in ss]
        ss=new
    return best[1:]

def calibrate(configs,cap,steps,out):
    anchor=next(c for c in configs if c['name']=='Argon2id baseline'); target=core.latency(anchor,7)
    print(f'Common latency target: {target*1000:.2f} ms',flush=True)
    cache={}; logs=[]; result=[]
    for i,c in enumerate(configs,1):
        d=copy.deepcopy(c); ss=d['stages']
        if d['family']=='tuned standalone':
            start=ss[0]; d,e=prev.fit(lambda m:core.config(c['name'],[dict(start,m=m)],c['family']),start['m'],1,cap,target,steps=steps)
        elif d['family'] in CONTROL: e=core.latency(d,3)
        else:
            canonical=sorted(ss,key=key); k=key(canonical)
            if k not in cache: cache[k]=retune_pair(canonical,target,cap,steps)
            pair,times=cache[k]; reverse=key(ss)!=k
            d['stages']=list(reversed(pair)) if reverse else pair; e=times[int(reverse)]
        result.append(d); logs.append(dict(name=d['name'],family=d['family'],target_ms=target*1000,calibration_ms=e*1000,error_pct=100*(e/target-1)))
        if i%10==0 or i==len(configs):
            print(f'Calibration {i}/{len(configs)}',flush=True); core.csvwrite(out/'calibration.csv',logs); dump(out/'calibrated_partial.json',result)
    core.csvwrite(out/'calibration.csv',logs); return result,target

def summarize(configs,raw,levels,tol,gain,resource_tol):
    rows=prev.summarize(configs,raw,levels,0,tol,gain)
    solo={r['name']:r for r in rows if r['workers']==1}; byname={c['name']:c for c in configs}
    for r in rows:
        c=byname[r['name']]; s=solo[r['name']]; r['solo_cpu_ms']=s['cpu_ms_per_job']; r['solo_rss_delta_mib']=s['rss_delta_mib']; r['max_argon2_p']=max(x.get('p',1) for x in c['stages'] if x['kind'] in V)
        r['nominal_peak_stage_mib']=max(core.memory_mib(x) for x in c['stages'])
    for r in rows:
        cs=[x for x in rows if x['workers']==r['workers'] and x['family'] in CONTROL and x['matched'] and abs(r['solo_latency_ms']/x['solo_latency_ms']-1)<=tol/100]
        # For a resource-matched comparison, candidate cannot consume more solo CPU work or sampled RSS than the control beyond tolerance.
        eligible=[x for x in cs if r['solo_cpu_ms']>0 and x['solo_cpu_ms']>0 and r['solo_cpu_ms']<=x['solo_cpu_ms']*(1+resource_tol/100) and r['nominal_peak_stage_mib']<=x['nominal_peak_stage_mib']*(1+resource_tol/100) and r['solo_rss_delta_mib']<=x['solo_rss_delta_mib']*(1+resource_tol/100)+2]
        rb=min(eligible,key=lambda x:x['throughput_per_s']) if eligible else None
        gb=next(x for x in rows if x['workers']==r['workers'] and x['name']==r['best_global_standalone'])
        same_p=[x for x in cs if x['max_argon2_p']==r['max_argon2_p']]
        pb=min(same_p,key=lambda x:x['throughput_per_s']) if same_p else None
        r['best_same_p_control']=pb['name'] if pb else ''
        r['throughput_vs_same_p_pct']=100*(r['throughput_per_s']/pb['throughput_per_s']-1) if pb else ''
        r['resource_comparators']=len(eligible); r['best_resource_matched_control']=rb['name'] if rb else ''
        r['throughput_vs_resource_control_pct']=100*(r['throughput_per_s']/rb['throughput_per_s']-1) if rb else ''
        r['cpu_timing_valid']=r['solo_cpu_ms']>0 and gb['solo_cpu_ms']>0
        r['solo_cpu_vs_global_pct']=100*(r['solo_cpu_ms']/gb['solo_cpu_ms']-1) if r['cpu_timing_valid'] else ''
        r['nominal_memory_vs_global_pct']=100*(r['nominal_peak_stage_mib']/gb['nominal_peak_stage_mib']-1)
        r['resource_budget_vs_global_ok']=r['cpu_timing_valid'] and r['solo_cpu_ms']<=gb['solo_cpu_ms']*(1+resource_tol/100) and r['nominal_peak_stage_mib']<=gb['nominal_peak_stage_mib']*(1+resource_tol/100) and r['solo_rss_delta_mib']<=gb['solo_rss_delta_mib']*(1+resource_tol/100)+2
        r['candidate_with_resource_budget']=r['candidate'] and r['resource_budget_vs_global_ok']
        r['resource_control_all_variants']=all(any(byname[x['name']]['stages'][0]['kind']==v for x in eligible) for v in V)
        r['resource_candidate']=bool(r['matched'] and r['workers']>1 and r['family'] not in CONTROL and rb and r['resource_control_all_variants'] and r['throughput_vs_resource_control_pct']<=-gain and r['scaling']<rb['scaling'])
    return rows

def selftest(skip):
    prev.selftest(not skip)
    source=load(HERE/'source_5c_configs.json'); configs=configs_for(source,False,skip)
    assert len(configs)==(606 if not skip else 570)
    assert {s['p'] for c in configs if c['family'] not in CONTROL for s in c['stages'] if s['kind'] in V}=={1,2,4}
    assert len({c['name'] for c in configs})==len(configs)
    for v in V:
        for p in (1,2,4):
            a=prev.ar(v,1,1,p); from argon2 import PasswordHasher
            import base64
            pw,salt=core.fixture(3); salt=core.stage_salt(salt,0)
            enc=PasswordHasher(time_cost=1,memory_cost=1024,parallelism=p,hash_len=32,salt_len=16,type=core.VARIANTS[v]).hash(pw,salt=salt)
            assert prev.stage(a,pw,salt)==base64.b64decode(enc.split('$')[-1]+'==')
    # A hybrid winning on throughput but spending twice the defender CPU time must fail the global resource gate.
    toy=[core.config(core.LABELS[v]+' baseline',[prev.ar(v,8,1)],'baseline') for v in V]
    toy.append(core.config('toy hybrid',[prev.ar('argon2id',8,1),core.pb('sha256',1)],'PBKDF2 cascade'))
    raw=[]
    for c in toy:
        hybrid=c['family'] not in CONTROL
        for w in (1,4):
            raw.append(dict(name=c['name'],workers=w,repeat=1,throughput_per_s=10 if w==1 else 20 if hybrid else 30,median_task_ms=100,cpu_ms_per_job=200 if hybrid else 100,peak_rss_mib=20,rss_delta_mib=8))
    rr=next(r for r in summarize(toy,raw,[1,4],5,5,10) if r['name']=='toy hybrid' and r['workers']==4)
    assert rr['candidate'] and not rr['candidate_with_resource_budget'] and not rr['resource_candidate']
    # Regression: a coarse process timer reporting zero must not crash or
    # produce a resource-budget success.
    for sample in raw:
        sample['cpu_ms_per_job']=0
    zero_rows=summarize(toy,raw,[1,4],5,5,10)
    assert all(not r['cpu_timing_valid'] and r['solo_cpu_vs_global_pct']=='' and not r['candidate_with_resource_budget'] and not r['resource_candidate'] for r in zero_rows)
    print('PASS: zero CPU timer regression.')
    print('PASS: configuration coverage, nine Argon2 variant/lane reference checks, resource-budget regression.',flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for f in ('self-test','smoke','screen','skip-bcrypt'): ap.add_argument('--'+f,action='store_true')
    ap.add_argument('--source',type=Path,default=HERE/'source_5c_configs.json'); ap.add_argument('--out',type=Path,default=Path('results/exp5d_screen')); ap.add_argument('--confirm-from',type=Path); ap.add_argument('--max-workers',type=int,choices=(2,4,8,12,16,24),default=8); ap.add_argument('--max-memory-mib',type=int,default=192); ap.add_argument('--tolerance',type=float,default=5); ap.add_argument('--resource-tolerance',type=float,default=10); ap.add_argument('--min-gain',type=float,default=5); ap.add_argument('--top',type=int,default=6); ap.add_argument('--worker-json'); ap.add_argument('--workers',type=int,default=1); ap.add_argument('--jobs',type=int,default=2); ap.add_argument('--offset',type=int,default=0)
    a=ap.parse_args()
    if a.worker_json: print(json.dumps(core.worker(json.loads(a.worker_json),a.workers,a.jobs,a.offset))); return
    if core.bcrypt is None and not a.skip_bcrypt: ap.error('bcrypt required; install requirements or use --skip-bcrypt')
    if a.self_test: selftest(a.skip_bcrypt); return
    if not 0<a.tolerance<=20 or not 0<=a.resource_tolerance<=50 or not 0<a.min_gain<100 or not 8<=a.max_memory_mib<=768 or a.top<1: ap.error('Invalid settings')
    out=a.out
    if out.exists() and any(out.iterdir()): ap.error('Choose a fresh output directory')
    out.mkdir(parents=True,exist_ok=True)
    if a.confirm_from:
        old=load(a.confirm_from/'configs.json'); ranking=list(csv.DictReader((a.confirm_from/'ranking.csv').open(encoding='utf-8')))
        matched=[r for r in ranking if r['family'] not in CONTROL and r['matched']=='True']
        matched.sort(key=lambda r:(r['candidate_with_resource_budget']!='True',r['candidate']!='True',float(r['throughput_vs_best_pct'])))
        picked={r['name'] for r in matched[:a.top]}
        configs=[c for c in old if c['family'] in CONTROL or c['name'] in picked]
        # Direct controls at stage memory and p for all variants, preserving one-stage controls.
        existing={key(c['stages']) for c in configs if c['family'] in CONTROL}
        for c in [x for x in configs if x['name'] in picked]:
            for s in [x for x in c['stages'] if x['kind'] in V]:
                for v in V:
                    for t in (1,2,3,4):
                        z=[prev.ar(v,s['m'],t,s.get('p',1))]
                        if key(z) not in existing:
                            configs.append(core.config(f'{core.LABELS[v]} direct {s["m"]} MiB t={t} p={s.get("p",1)}',z,'fixed-memory standalone')); existing.add(key(z))
        target=load(a.confirm_from/'environment.json')['calibration_target_ms']/1000
        repeats=7; per=3; levels=[w for w in (1,2,4,8,12,16,24) if w<=a.max_workers]
        print(f'Confirming {len(picked)} hybrids and {len(configs)-len(picked)} standalone controls',flush=True)
    else:
        configs=configs_for(load(a.source),a.smoke,a.skip_bcrypt)
        maxstage=max(core.memory_mib(s) for c in configs for s in c['stages']); cap=8 if a.smoke else a.max_memory_mib
        if psutil.virtual_memory().available<(2*max(maxstage,cap)+256)*2**20: ap.error('Insufficient RAM for calibration')
        configs,target=calibrate(configs,cap,2 if a.smoke else 4,out)
        repeats=1 if a.smoke else 3; per=1 if a.smoke else 2
        levels=[1,2] if a.smoke else sorted({1,min(4,a.max_workers),a.max_workers})
    maxstage=max(core.memory_mib(s) for c in configs for s in c['stages'])
    if psutil.virtual_memory().available<(2*maxstage*max(levels)+256)*2**20: ap.error('Insufficient RAM; reduce --max-workers')
    dump(out/'configs.json',configs); rng=random.Random(53702 if a.confirm_from else 53701); raw=[]; total=len(configs)*len(levels)*repeats
    for repeat in range(repeats):
        plan=[(c,w) for c in configs for w in levels]; rng.shuffle(plan)
        for c,w in plan:
            child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker-json',json.dumps(c),'--workers',str(w),'--jobs',str(w*per),'--offset',str((400000 if a.confirm_from else 300000)+repeat*1000)],capture_output=True,text=True)
            if child.returncode: raise RuntimeError(child.stderr or child.stdout)
            raw.append(dict(name=c['name'],repeat=repeat+1,**json.loads(child.stdout)))
            if len(raw)%10==0 or len(raw)==total: print(f'Batch {len(raw)}/{total}',flush=True); core.csvwrite(out/'raw_batches.csv',raw)
    rows=summarize(configs,raw,levels,a.tolerance,a.min_gain,a.resource_tolerance); core.csvwrite(out/'summary.csv',rows)
    ranking=sorted([r for r in rows if r['workers']==max(levels)],key=lambda r:(not r['matched'],r['throughput_per_s'])); core.csvwrite(out/'ranking.csv',ranking); prev.plots(out,rows,levels)
    dump(out/'environment.json',dict(calibration_target_ms=target*1000,workers=levels,repeats=repeats,jobs_per_worker=per,batch_min_wall_s=.15,batch_min_cpu_s=.10,batch_extension_limit_s=2.0,configurations=len(configs),python=sys.version,platform=platform.platform(),processor=platform.processor(),logical_cpus=os.cpu_count(),tolerance_pct=a.tolerance,resource_tolerance_pct=a.resource_tolerance,min_gain_pct=a.min_gain,confirmation_from=str(a.confirm_from) if a.confirm_from else None,synthetic_only=True,backend='CPU native libraries'))
    if (out/'calibrated_partial.json').exists(): (out/'calibrated_partial.json').unlink()
    print(f'Finished: {out.resolve()} | latency candidates: {sum(r["candidate"] for r in ranking)} | also within global resource budget: {sum(r["candidate_with_resource_budget"] for r in ranking)}',flush=True)

if __name__=='__main__': main()
