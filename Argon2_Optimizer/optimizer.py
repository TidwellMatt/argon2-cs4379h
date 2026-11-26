#!/usr/bin/env python3
"""Offline defender-side Argon2id parameter optimizer. No GPU or real passwords required."""
import argparse,csv,hashlib,json,math,os,platform,statistics,sys,time,threading,random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from argon2.low_level import hash_secret_raw,verify_secret,Type
import psutil
from profile_data import load_profiles,candidates,import_source,merge_profiles,validate
ROOT=Path(__file__).resolve().parent
BASE='id_m64_t3_p4'; HIGH='id_m2048_t1_p4'
FIELDS=['latency_ms','cpu_ms','concurrent_hps','concurrent_p95_ms','rss_peak_mib']
MODES={
    'defense': ('Maximum defense','Minimize stored GPU H/s; stop at the first confirmed feasible configuration.'),
    'balanced': ('Balanced performance','Minimize confirmed median CPU latency (seconds) × stored maximum GPU H/s.'),
    'responsive': ('Maximum responsiveness','Minimize confirmed median CPU latency within the required GPU throughput ceiling.'),
    'efficient': ('Resource efficiency','Minimize confirmed median CPU time; break ties by Argon2 memory, then sampled RSS, within the required GPU throughput ceiling.'),
    'comprehensive': ('Comprehensive analysis','Test all eligible candidates; report tradeoffs and a Pareto frontier. Show the defense-first choice as a reference, not a universal winner.')
}
TARGET_MODES={'responsive','efficient'}

def objective(res, mode):
    c=res['configuration']; m=res['cpu_median']; g=rank(c)
    if mode=='balanced': return (m['latency_ms']/1000*g[0],*g)
    if mode=='responsive': return (m['latency_ms'],*g)
    if mode=='efficient': return (m['cpu_ms'],c['memory_mib'],m['rss_peak_mib'],*g)
    return g

def tradeoff_vector(res):
    c=res['configuration']; m=res['cpu_median']
    return (c['gpu_max_observed'],m['latency_ms'],m['cpu_ms'],c['memory_mib'],m['rss_peak_mib'],m['concurrent_p95_ms'],-m['concurrent_hps'])

def frontier(results):
    vectors=[tradeoff_vector(r) for r in results]
    return {r['configuration']['config'] for i,r in enumerate(results)
            if not any(all(a<=b for a,b in zip(v,vectors[i])) and any(a<b for a,b in zip(v,vectors[i])) for j,v in enumerate(vectors) if j!=i)}


def dump(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf8');tmp.replace(path)
def csvout(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r)) or ['config']
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def hashit(c,i):
    salt=hashlib.sha256(f'optimizer-public/{i}'.encode()).digest()[:16]
    return hash_secret_raw(b'public synthetic benchmark only',salt,c['t'],c['memory_mib']*1024,c['p'],32,Type.ID,version=19)
def selftest():
    h=b'$argon2id$v=19$m=65536,t=3,p=1$FBMjI4RJBhIykCgol1KEJA$2ky5GAdhT1kH4kIgPN/oERE3Taiy43vNN70a3HpiKQU'
    if not verify_secret(h,b'hashcat',Type.ID):raise RuntimeError('known answer failed')
    p=load_profiles([ROOT/'profiles/rtx4090.json'])[0]
    assert len(p['entries'])==579 and len(candidates([p]))==193 and len(p['entries'][BASE]['hps_rounds'])==20
    print('Known-answer and bundled profile checks passed.')
def percentile(xs,q):
    xs=sorted(xs);return xs[max(0,math.ceil(q*len(xs))-1)]
def measure(c,workers,round_no):
    avail=psutil.virtual_memory().available/2**20
    if c['memory_mib']*workers>avail*.60:raise RuntimeError('memory guard: working memory exceeds 60% of available RAM')
    # One warm-up, then at least 0.20s of solo work to mitigate coarse Windows CPU timer resolution.
    hashit(c,-1);ls=[]; start=time.perf_counter(); cpu0=time.process_time(); i=0
    while i<3 or time.perf_counter()-start<.20:
        tick=time.perf_counter();hashit(c,round_no*100000+i);ls.append((time.perf_counter()-tick)*1000);i+=1
    cpu=(time.process_time()-cpu0)*1000/i
    if cpu<=0:raise RuntimeError('CPU timer returned nonpositive duration')
    proc=psutil.Process();peak=[proc.memory_info().rss];stop=threading.Event()
    def monitor():
        while not stop.is_set():
            peak[0]=max(peak[0],proc.memory_info().rss);stop.wait(.005)
    def task(i):
        tick=time.perf_counter();hashit(c,100000000+round_no*100000+i);return (time.perf_counter()-tick)*1000
    with ThreadPoolExecutor(max_workers=workers) as pool:
        mon=threading.Thread(target=monitor,daemon=True);mon.start();start=time.perf_counter()
        try:times=list(pool.map(task,range(workers*3)));elapsed=time.perf_counter()-start
        finally:stop.set();mon.join()
    return dict(latency_ms=statistics.median(ls),cpu_ms=cpu,concurrent_hps=len(times)/elapsed,concurrent_p95_ms=percentile(times,.95),rss_peak_mib=peak[0]/2**20,solo_samples=len(ls),concurrent_samples=len(times))
def summarize(rows):
    return {k:statistics.median(r[k] for r in rows) for k in FIELDS}
def bootstrap_medians(rows):
    if len(rows)<5:return None
    rng=random.Random(808);n=len(rows);draws=[[rng.randrange(n) for _ in range(n)] for _ in range(2000)]
    return {k:[percentile([statistics.median(rows[i][k] for i in ids) for ids in draws],q) for q in (.025,.975)] for k in FIELDS}
def policy(c,a):
    if c['memory_mib']>a.max_memory or c['memory_mib']<a.min_memory:return False
    if c['t']<a.min_passes and not (c['config']==HIGH and a.min_passes<=3):return False
    return True
def feasible(s,a):
    limits=[('latency_ms',a.latency_ms,False),('cpu_ms',a.max_cpu_ms,False),('concurrent_p95_ms',a.max_p95_ms,False),('rss_peak_mib',a.max_rss_mib,False),('concurrent_hps',a.min_throughput,True)]
    return all(lim is None or (s[k]>=lim if low else s[k]<=lim) for k,lim,low in limits)
def safe_summary(rows):
    # Conservative observed envelope, not a formal confidence or future SLA guarantee.
    return {k:(min if k=='concurrent_hps' else max)(r[k] for r in rows) for k in FIELDS}
def rank(c):return (c['gpu_max_observed'],c['gpu_median_worst'],c['config'])
def environment():return {'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'ram_mib':psutil.virtual_memory().total/2**20,'python':sys.version,'argon2_cffi':__import__('importlib.metadata',fromlist=['version']).version('argon2-cffi')}
def optimize(a):
    started=time.perf_counter()
    ps=load_profiles(a.profile or [ROOT/'profiles/rtx4090.json']);allc=candidates(ps)
    mode=a.mode; full_search=a.exhaustive or mode!='defense'
    cs=sorted([c for c in allc if policy(c,a) and (a.max_gpu_hps is None or c['gpu_max_observed']<=a.max_gpu_hps)],key=rank)
    print(f'{MODES[mode][0]}: {MODES[mode][1]}',flush=True)
    print(f'{len(cs)} eligible configurations. '+('All eligible candidates will be screened.' if full_search else 'GPU-ordered early stopping enabled.'),flush=True)
    if not cs:raise ValueError('No common-profile configurations meet the parameter policy and GPU ceiling. Check memory, passes and GPU target.')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    if (out/'run.json').exists():raise ValueError('Output already contains a run; choose a new folder to preserve results.')
    cfg={k:v for k,v in vars(a).items() if k not in ('profile','out','command')};dump(out/'run.json',{'settings':cfg,'environment':environment(),'profile_ids':[p['profile_id'] for p in ps],'profile_sha256':[hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (a.profile or [ROOT/'profiles/rtx4090.json'])],'eligible_count':len(cs),'common_argon2id_count':len(allc)})
    raw=[];summary=[];winner=None; tested=0; confirmed=[]
    def bench(c,phase,n):
        rows=[]
        for j in range(1,n+1):
            m=measure(c,a.workers,j+(1000 if phase=='confirm' else 0));rows.append(m);raw.append({'config':c['config'],'phase':phase,'round':j,**m});csvout(out/'cpu_rounds.csv',raw)
        return rows
    def entry(c,phase,rows,ok):
        med=summarize(rows);env=safe_summary(rows)
        summary.append({**{k:v for k,v in c.items() if k!='gpu_details'},'phase':phase,'status':'pass' if ok else 'constraint_failed','rounds':len(rows),**med,**{'observed_bound_'+k:v for k,v in env.items()}});csvout(out/'tested.csv',summary)
    def check(c):
        print(f'[{tested}/{len(cs)}] {c["config"]}  profile maximum {c["gpu_max_observed"]:g} H/s',flush=True)
        try:
            s=bench(c,'screen',a.screen_rounds);ok=feasible(safe_summary(s),a);entry(c,'screen',s,ok)
            if not ok:return None
            rs=bench(c,'confirm',a.confirm_rounds);ok=feasible(safe_summary(rs),a);entry(c,'confirm',rs,ok)
            if ok:return {'configuration':c,'cpu_median':summarize(rs),'cpu_observed_bounds':safe_summary(rs),'confirmation_rounds':len(rs),'median_bootstrap_95_exploratory':bootstrap_medians(rs)}
        except (Exception,) as e:
            summary.append({'config':c['config'],'phase':'measurement','status':'error','error':str(e)});csvout(out/'tested.csv',summary);print('  skipped:',e,flush=True)
        return None
    # Sorted by a fixed empirical attacker objective. No CPU-only monotonicity assumption.
    for c in cs:
        if a.max_tests and tested>=a.max_tests:break
        tested+=1;res=check(c)
        if res:
            confirmed.append(res)
            if winner is None or objective(res,mode)<objective(winner,mode):winner=res
            print(f'  confirmed; objective = {objective(res,mode)[0]:.4g}',flush=True)
        if winner and not full_search:break
    confirmed.sort(key=lambda r:objective(r,mode))
    pareto=frontier(confirmed)
    ranking=[]
    for i,r in enumerate(confirmed,1):
        c=r['configuration']; m=r['cpu_median']
        ranking.append({'rank':i,'config':c['config'],'memory_mib':c['memory_mib'],'t':c['t'],'p':c['p'],'gpu_max_observed':c['gpu_max_observed'],**m,'latency_gpu_product':m['latency_ms']/1000*c['gpu_max_observed'],'objective_value':objective(r,mode)[0],'pareto':c['config'] in pareto})
    csvout(out/'confirmed_ranking.csv',ranking)
    csvout(out/'pareto_frontier.csv',[r for r in ranking if r['pareto']])
    # Independent reference measurement even if it was screened out or not reached.
    baseline=next((c for c in allc if c['config']==BASE),None);ref=None
    if baseline and baseline['memory_mib']<=a.max_memory:
        try:
            rs=bench(baseline,'reference',a.confirm_rounds);ref={'configuration':baseline,'cpu_median':summarize(rs),'cpu_observed_bounds':safe_summary(rs),'meets_constraints':feasible(safe_summary(rs),a) and (a.max_gpu_hps is None or baseline['gpu_max_observed']<=a.max_gpu_hps),'median_bootstrap_95_exploratory':bootstrap_medians(rs)};entry(baseline,'reference',rs,ref['meets_constraints'])
        except Exception as e:ref={'error':str(e)}
    report={'recommendation':winner,'reference':ref,'tested_candidates':tested,'eligible_candidates':len(cs),'search_complete':tested==len(cs),'stopped_after_first_confirmed':bool(winner and not full_search),'mode':mode,'objective':MODES[mode][1],'max_gpu_hps':a.max_gpu_hps,'confirmed_candidates':len(confirmed),'pareto_count':len(pareto),'elapsed_seconds':time.perf_counter()-started,'profile_ids':[p['profile_id'] for p in ps],'research_relaxed':a.research_relaxed,'warning':'Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.'}
    dump(out/'recommendation.json',report)
    lines=['# Argon2id parameter recommendation','',f'**Mode: {MODES[mode][0]}**',MODES[mode][1],f'Tested {tested} of {len(cs)} eligible configurations; {len(confirmed)} independently confirmed.',f'Elapsed time: {report["elapsed_seconds"]:.1f} seconds.']
    if a.max_gpu_hps is not None:lines.append(f'Maximum stored GPU throughput: {a.max_gpu_hps:g} H/s.')
    if full_search and tested<len(cs):lines.append('Search incomplete: ranking is limited to the candidates actually tested.')
    if mode=='comprehensive':lines.append('The highlighted recommendation is the defense-first choice; review the frontier for other tradeoffs.')
    if ranking:
        lines+=['', '## Confirmed candidates (top 10 by selected objective)', '', '| Rank | Configuration | CPU ms (latency) | GPU H/s | Latency × H/s (seconds) | Pareto |','|---:|---|---:|---:|---:|---|']
        for r in ranking[:10]:lines.append(f'| {r["rank"]} | {r["config"]} | {r["latency_ms"]:.2f} | {r["gpu_max_observed"]:.2f} | {r["latency_gpu_product"]:.3f} | {"yes" if r["pareto"] else "no"} |')
        lines.append(f'Full confirmed ranking and {len(pareto)} non-dominated candidates among confirmed results are in confirmed_ranking.csv and pareto_frontier.csv.')
    if winner:
        c=winner['configuration'];lines+=['',f'**{c["memory_mib"]} MiB, t={c["t"]}, p={c["p"]}**',f'PHC parameters: `m={c["memory_mib"]*1024},t={c["t"]},p={c["p"]}`',f'Profile maximum observed: {c["gpu_max_observed"]:.2f} H/s; minimum profile repetitions: {c["gpu_min_rounds"]}.','', '| CPU metric | Median | Conservative observed bound |','|---|---:|---:|']
        for k in FIELDS:lines.append(f'| {k} | {winner["cpu_median"][k]:.2f} | {winner["cpu_observed_bounds"][k]:.2f} |')
        print(f'Recommendation: {c["config"]}',flush=True)
    else:lines+=['','No recommendation: no tested configuration passed all constraints. No automatic weakening of security policy.'];print('No recommendation; review tested.csv.',flush=True)
    if winner and ref and 'cpu_median' in ref:
        lines+=['','## RFC low-memory reference (measured locally)','', '| Metric | Recommendation | Reference |','|---|---:|---:|']
        for k in FIELDS:lines.append(f'| {k} | {winner["cpu_median"][k]:.2f} | {ref["cpu_median"][k]:.2f} |')
        lines.append(f'| GPU profile maximum H/s | {winner["configuration"]["gpu_max_observed"]:.2f} | {ref["configuration"]["gpu_max_observed"]:.2f} |')
    if a.research_relaxed:lines+=['','**Research-only relaxed policy: not a deployment recommendation.**']
    lines+=['','## Limitations',report['warning'],'','See recommendation.json for profile provenance, reference comparison and complete numeric results.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8');print('Results:',out.resolve())
def replay(a):
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    # Same dataset replay only. Use matching GPU stage to avoid silently mixing confirmation and screening.
    records=[]
    for dataset in ('full','confirm_20'):
        with (ROOT/'validation'/f'{dataset}_ranking.csv').open(newline='') as f: historical={r['config']:r for r in csv.DictReader(f) if r['variant']=='id'}
        with (ROOT/'validation'/f'{dataset}_gpu_raw.csv').open(newline='') as f:
            speeds={}
            for r in csv.DictReader(f):
                if r['status']=='ok':speeds.setdefault(r['config'],[]).append(float(r['gpu_hps']))
        for budget in (25,50,75,100,150,250,500,1000):
            for mem in (64,128,256,512,2048):
                pool=[]
                for k,r in historical.items():
                    c={'config':k,'memory_mib':int(r['memory_mib']),'t':int(r['t']),'p':int(r['p'])}
                    if c['memory_mib']>mem or c['memory_mib']<64 or (c['t']<3 and k!=HIGH) or k not in speeds:continue
                    pool.append({**c,'gpu_max_observed':max(speeds[k]),'gpu_median_worst':statistics.median(speeds[k]),'latency_ms':float(r['latency_ms'])})
                ordered=sorted(pool,key=rank);eligible=[c for c in pool if c['latency_ms']<=budget];best=min(eligible,key=rank) if eligible else None
                found=None;checks=0
                for c in ordered:
                    checks+=1
                    if c['latency_ms']<=budget:found=c;break
                cpu_only=max(eligible,key=lambda c:(c['memory_mib'],c['t'],-c['latency_ms'],c['config'])) if eligible else None
                records.append(dict(dataset=dataset,latency_budget_ms=budget,memory_budget_mib=mem,exhaustive_tests=len(pool),guided_tests=checks,tests_saved=len(pool)-checks,exhaustive_winner=best['config'] if best else '',guided_winner=found['config'] if found else '',matches_oracle=found==best,guided_gpu_max=found['gpu_max_observed'] if found else '',cpu_only_heuristic=cpu_only['config'] if cpu_only else '',cpu_only_gpu_max=cpu_only['gpu_max_observed'] if cpu_only else ''))
    csvout(out/'replay.csv',records);valid=[r for r in records if r['guided_winner']];stats={'scenarios':len(records),'feasible_scenarios':len(valid),'matching_scenarios':sum(r['matches_oracle'] for r in records),'strictly_better_than_cpu_only_heuristic':sum(r['guided_gpu_max']<r['cpu_only_gpu_max'] for r in valid),'total_exhaustive_tests':sum(r['exhaustive_tests'] for r in valid),'total_guided_tests':sum(r['guided_tests'] for r in valid),'warning':'In-sample deterministic replay of stored point estimates (latency and memory constraints only); not an independent CPU experiment or evidence of cross-hardware generalization. Matching the exhaustive oracle is expected by construction. CPU-only heuristic is an illustrative comparator, not an implementation of Cryptsetup or Multifactor.'};dump(out/'replay_summary.json',stats);print(json.dumps(stats,indent=2))
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('self-test');o=sub.add_parser('optimize');o.add_argument('--profile',action='append');o.add_argument('--out',default='results/local_optimization');o.add_argument('--latency-ms',type=float,default=100);o.add_argument('--max-memory',type=int,default=256);o.add_argument('--min-memory',type=int,default=64);o.add_argument('--min-passes',type=int,default=3);o.add_argument('--workers',type=int,default=4);o.add_argument('--max-cpu-ms',type=float);o.add_argument('--max-p95-ms',type=float);o.add_argument('--max-rss-mib',type=float);o.add_argument('--min-throughput',type=float);o.add_argument('--screen-rounds',type=int,default=2);o.add_argument('--confirm-rounds',type=int,default=5);o.add_argument('--max-tests',type=int,default=0,help='0 = no limit');o.add_argument('--exhaustive',action='store_true');o.add_argument('--mode',choices=list(MODES),default='defense');o.add_argument('--max-gpu-hps',type=float,help='Maximum stored GPU H/s; required in responsive and efficient modes');o.add_argument('--research-relaxed',action='store_true',help='Allow lower policy floors for research, not deployment advice')
    r=sub.add_parser('replay');r.add_argument('--out',default='results/replay');# historical replay always uses bundled datasets
    i=sub.add_parser('import-profile');i.add_argument('--source',action='append',required=True);i.add_argument('--device',required=True);i.add_argument('--id',required=True);i.add_argument('--out',required=True)
    a=p.parse_args()
    try:
        if a.command=='self-test':selftest()
        elif a.command=='replay':replay(a)
        elif a.command=='import-profile':
            ps=[import_source(x,a.device,a.id) for x in a.source];profile=ps[0]
            for q in ps[1:]:profile=merge_profiles(profile,q)
            path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():raise ValueError('Profile output already exists')
            dump(path,validate(profile));print(f'Imported {len(profile["entries"])} configurations to {path}')
        else:
            if not 1<=a.workers<=32 or not 1<=a.screen_rounds<=20 or not 3<=a.confirm_rounds<=100 or a.max_tests<0:raise ValueError('workers 1–32; screen rounds 1–20; confirmation 3–100; max tests >=0')
            if a.min_memory<(19 if a.research_relaxed else 64) or a.min_passes<(2 if a.research_relaxed else 3):raise ValueError('Parameter policy floor violated; no automatic weakening')
            if a.max_memory<a.min_memory or a.max_memory>2048:raise ValueError('Memory limit must be between minimum and 2048 MiB')
            if a.mode in TARGET_MODES and a.max_gpu_hps is None:raise ValueError('This mode requires a maximum GPU H/s target')
            for k in ('latency_ms','max_cpu_ms','max_p95_ms','max_rss_mib','min_throughput','max_gpu_hps'):
                x=getattr(a,k)
                if x is not None and (not math.isfinite(x) or x<=0):raise ValueError(f'{k} must be positive finite')
            optimize(a)
    except (ValueError,KeyError,OSError,RuntimeError) as e:p.exit(2,f'Error: {e}\n')
if __name__=='__main__':main()
