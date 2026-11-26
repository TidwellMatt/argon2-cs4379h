"""5E: one-sided latency ceiling and multi-target synthetic CPU performance study.
Uses the fixed 5D native-library benchmarks. No credential recovery or GPU cascade claims.
"""
import argparse, copy, csv, json, math, os, platform, random, statistics as st, subprocess, sys
from collections import defaultdict
from pathlib import Path
import psutil
import exp5d_balanced as d

core=d.core; prev=d.prev; V=d.V; CONTROL=d.CONTROL; HERE=Path(__file__).resolve().parent
DEFAULT_TARGETS=(50,75,90,100,110)

def targets_arg(value):
    try: vals=tuple(sorted(set(float(x) for x in value.split(','))))
    except ValueError: raise argparse.ArgumentTypeError('Use comma-separated percentages')
    if not vals or any(not math.isfinite(v) or not 10<=v<=150 for v in vals): raise argparse.ArgumentTypeError('Targets must be 10–150 percent')
    return vals

def label(p): return f'{p:g}%'

def calibration_plan(source,targets,smoke,skip):
    templates=d.configs_for(source,smoke,skip)
    if smoke:
        for v in V:
            c=next(c for c in source if c['family']=='tuned standalone' and c['stages'][0]['kind']==v and c['stages'][0]['p']==2)
            c=copy.deepcopy(c); c['stages'][0]['m']=max(1,round(c['stages'][0]['m']/16)); templates.append(c)
    plan=[]
    for c in templates:
        for p in ((None,) if c['family'] in ('baseline','fixed-memory standalone') else targets):
            plan.append((c,p))
    return plan

def calibrate(source,targets,smoke,skip,cap,steps,out):
    plan=calibration_plan(source,targets,smoke,skip)
    anchor=next(c for c,p in plan if c['name']=='Argon2id baseline')
    target=core.latency(anchor,7)
    print(f'Common calibration anchor: {target*1000:.2f} ms; targets: {targets}',flush=True)
    cache={}; logs=[]; configs=[]; signatures={}
    # Retain all fixed controls, including the named anchor, before deduplicating tuned trials.
    plan.sort(key=lambda x:x[1] is not None)
    for i,(c,p) in enumerate(plan,1):
        q=copy.deepcopy(c); ss=q['stages']; desired=target*(p/100 if p is not None else 1)
        if p is not None: q['name']+=f' [target={label(p)}]'
        if q['family']=='tuned standalone':
            start=ss[0]; q,e=prev.fit(lambda m:dict(q,stages=[dict(start,m=m)]),max(1,round(start['m']*p/100)),1,cap,desired,steps=steps)
        elif q['family'] in CONTROL: e=core.latency(q,3)
        else:
            canonical=sorted(ss,key=d.key); k=(p,d.key(canonical))
            if k not in cache:
                initial=[d.scale_stage(s,p/100,cap) for s in canonical]
                cache[k]=d.retune_pair(initial,desired,cap,steps)
            pair,times=cache[k]; reverse=d.key(ss)!=k[1]
            q['stages']=list(reversed(pair)) if reverse else pair; e=times[int(reverse)]
        q['target_pct']=p; sig=d.key(q['stages']); existing=signatures.get(sig)
        # Keep fixed controls as named; identical tuned configurations need only one benchmark.
        if existing is None or p is None:
            configs.append(q); signatures.setdefault(sig,q['name']); actual=q['name']
        else: actual=existing
        logs.append(dict(name=q['name'],benchmarked_as=actual,family=q['family'],target_pct='' if p is None else p,target_ms=desired*1000,calibration_ms=e*1000,error_pct=100*(e/desired-1),deduplicated=actual!=q['name']))
        if i%25==0 or i==len(plan):
            print(f'Calibration {i}/{len(plan)} | distinct benchmark entries {len(configs)}',flush=True)
            core.csvwrite(out/'calibration.csv',logs); d.dump(out/'calibrated_partial.json',configs)
    return configs,target,len(plan)

def summarize(configs,raw,levels,tol,gain,resource_tol,equal_tol):
    by={c['name']:c for c in configs}; groups=defaultdict(list)
    for r in raw: groups[r['name'],r['workers']].append(r)
    def med(n,w,k): return st.median(x[k] for x in groups[n,w])
    anchor=med('Argon2id baseline',1,'median_task_ms'); limit=anchor*(1+tol/100)
    rows=[]; by_level=defaultdict(list); lookup={}
    for c in configs:
        n=c['name']; solo=med(n,1,'median_task_ms'); solo_rate=med(n,1,'throughput_per_s'); err=100*(solo/anchor-1)
        for w in levels:
            g=groups[n,w]; rate=med(n,w,'throughput_per_s')
            r=dict(name=n,family=c['family'],target_pct=c.get('target_pct') or '',workers=w,repeats=len(g),anchor_latency_ms=anchor,latency_ceiling_ms=limit,solo_latency_ms=solo,solo_error_pct=err,within_latency_ceiling=solo<=limit,matched=solo<=limit,equal_anchor_match=abs(err)<=equal_tol,throughput_per_s=rate,scaling=rate/solo_rate,throughput_min=min(x['throughput_per_s'] for x in g),throughput_max=max(x['throughput_per_s'] for x in g),solo_cpu_ms=med(n,1,'cpu_ms_per_job'),solo_rss_delta_mib=med(n,1,'rss_delta_mib'),max_argon2_p=max(s.get('p',1) for s in c['stages'] if s['kind'] in V),nominal_peak_stage_mib=max(core.memory_mib(s) for s in c['stages']),contains_argon2d=any(s['kind']=='argon2d' for s in c['stages']))
            for k in ('median_task_ms','cpu_ms_per_job','peak_rss_mib','rss_delta_mib'): r[k]=med(n,w,k)
            rows.append(r); by_level[w].append(r); lookup[n,w]=r
    def coverage(cs): return all(any(by[x['name']]['stages'][0]['kind']==v for x in cs) for v in V)
    def best(cs): return min(cs,key=lambda x:x['throughput_per_s']) if cs else None
    def pct(a,b): return 100*(a/b-1) if b>0 else ''
    def budget(r,b):
        f=1+resource_tol/100
        return bool(b and r['solo_cpu_ms']>0 and b['solo_cpu_ms']>0 and r['solo_cpu_ms']<=b['solo_cpu_ms']*f and r['nominal_peak_stage_mib']<=b['nominal_peak_stage_mib']*f and r['solo_rss_delta_mib']<=b['solo_rss_delta_mib']*f+2)
    def wins(r,b): return bool(b and pct(r['throughput_per_s'],b['throughput_per_s'])<=-gain and r['scaling']<b['scaling'])
    for w,rr in by_level.items():
        cs=[r for r in rr if r['within_latency_ceiling'] and r['family'] in CONTROL]; gb=best(cs); covered=coverage(cs)
        for r in rr:
            hybrid=r['family'] not in CONTROL; gate=bool(w>1 and hybrid and r['within_latency_ceiling'])
            eq=[x for x in cs if x['equal_anchor_match'] and abs(r['solo_latency_ms']/x['solo_latency_ms']-1)*100<=equal_tol]; eb=best(eq)
            rc=[x for x in cs if budget(r,x)]; rb=best(rc)
            pb=best([x for x in cs if x['max_argon2_p']==r['max_argon2_p']])
            r.update(best_global_standalone=gb['name'],best_standalone_ms=gb['solo_latency_ms'],best_standalone_throughput=gb['throughput_per_s'],latency_vs_best_pct=pct(r['solo_latency_ms'],gb['solo_latency_ms']),throughput_vs_best_pct=pct(r['throughput_per_s'],gb['throughput_per_s']),scaling_vs_best_pct=pct(r['scaling'],gb['scaling']),all_variants_eligible=covered,candidate=gate and covered and wins(r,gb),cpu_timing_valid=r['solo_cpu_ms']>0 and gb['solo_cpu_ms']>0,solo_cpu_vs_global_pct=pct(r['solo_cpu_ms'],gb['solo_cpu_ms']) if r['solo_cpu_ms']>0 else '',nominal_memory_vs_global_pct=pct(r['nominal_peak_stage_mib'],gb['nominal_peak_stage_mib']),resource_budget_vs_global_ok=budget(r,gb))
            r['candidate_with_resource_budget']=r['candidate'] and r['resource_budget_vs_global_ok']
            r.update(best_equal_latency_control=eb['name'] if eb else '',equal_latency_controls_all_variants=coverage(eq),throughput_vs_equal_control_pct=pct(r['throughput_per_s'],eb['throughput_per_s']) if eb else '',equal_latency_candidate=gate and r['equal_anchor_match'] and coverage(eq) and wins(r,eb),best_same_p_control=pb['name'] if pb else '',throughput_vs_same_p_pct=pct(r['throughput_per_s'],pb['throughput_per_s']) if pb else '',resource_comparators=len(rc),best_resource_matched_control=rb['name'] if rb else '',throughput_vs_resource_control_pct=pct(r['throughput_per_s'],rb['throughput_per_s']) if rb else '',resource_control_all_variants=coverage(rc),resource_candidate=gate and coverage(rc) and wins(r,rb))
            b={x['repeat']:x['throughput_per_s'] for x in groups[gb['name'],w]}; a={x['repeat']:x['throughput_per_s'] for x in groups[r['name'],w]}; r['paired_repeats_lower']=sum(a[k]<b[k] for k in a.keys()&b.keys())
    for r in rows:
        high=[lookup[r['name'],w] for w in levels if w>=4]
        r['passes_at_multiple_high_concurrency_levels']=len(high)>=2 and all(x['candidate_with_resource_budget'] for x in high)
    return rows

def plots(out,rows,levels):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    eligible=[r for r in rows if r['workers']==max(levels) and r['within_latency_ceiling']]
    selected=sorted(eligible,key=lambda r:r['throughput_per_s'])[:12]
    for group in ([r for r in eligible if r['family'] not in CONTROL], *[[r for r in eligible if r['family'] in CONTROL and r['name'].startswith(core.LABELS[v]+' ')] for v in V]):
        if group:
            x=min(group,key=lambda r:r['throughput_per_s'])
            if x not in selected: selected.append(x)
    for k,title,unit in [('throughput_per_s','Throughput under the one-sided latency ceiling','Derivations/s'),('solo_latency_ms','Individual authentication latency','ms'),('peak_rss_mib','Sampled peak process memory','MiB'),('scaling','Parallel scaling','Throughput / solo throughput')]:
        rr=sorted(selected,key=lambda r:r[k],reverse=True); fig,ax=plt.subplots(figsize=(13,max(5,len(rr)*.40)))
        ax.barh([r['name'] for r in rr],[r[k] for r in rr],color=['#355c91' if r['family'] in CONTROL else '#158477' for r in rr]); ax.set(title=title+f' ({max(levels)} workers)',xlabel=unit); ax.tick_params(axis='y',labelsize=8)
        if k=='solo_latency_ms': ax.axvline(rr[0]['latency_ceiling_ms'],ls='--',color='black',label='Latency ceiling'); ax.legend()
        fig.tight_layout(); fig.savefig(out/(k+'.png'),dpi=140); plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,6))
    for family,caption,color in [(True,'Standalone controls','#355c91'),(False,'Hybrids','#158477')]:
        rr=[r for r in rows if r['workers']==max(levels) and (r['family'] in CONTROL)==family]
        ax.scatter([r['solo_latency_ms'] for r in rr],[r['throughput_per_s'] for r in rr],s=14,alpha=.6,label=caption,color=color)
    ax.axvline(eligible[0]['latency_ceiling_ms'],ls='--',color='black',label='Latency ceiling'); ax.set(xlabel='Individual latency (ms)',ylabel='Derivations/s',title=f'Latency vs. concurrent throughput ({max(levels)} workers)'); ax.legend(); fig.tight_layout(); fig.savefig(out/'latency_throughput.png',dpi=140); plt.close(fig)

def selftest(skip):
    d.selftest(skip)
    source=d.load(HERE/'source_5c_configs.json'); plan=calibration_plan(source,DEFAULT_TARGETS,False,skip)
    assert {p for c,p in plan if c['family']=='tuned standalone'}==set(DEFAULT_TARGETS)
    assert {p for c,p in plan if c['family'] not in CONTROL}==set(DEFAULT_TARGETS)
    assert sum(c['name']=='Argon2id baseline' for c,p in plan)==1
    # Regression fixtures: faster hybrid must be eligible; slow hybrid rejected;
    # a fast standalone must participate in global ranking; zero timing cannot pass budget.
    configs=[core.config(core.LABELS[v]+' baseline',[prev.ar(v,8,1)],'baseline') for v in V]
    configs += [core.config('fast hybrid',[prev.ar('argon2id',8,1),core.pb('sha256',1)],'PBKDF2 cascade'),core.config('slow hybrid',[prev.ar('argon2id',8,1),core.pb('sha256',2)],'PBKDF2 cascade'),core.config('fast standalone',[prev.ar('argon2id',8,2)],'tuned standalone')]
    raw=[]
    for c in configs:
        n=c['name']; ms=60 if n=='fast hybrid' else 111 if n=='slow hybrid' else 70 if n=='fast standalone' else 100
        for w in (1,4):
            rate=(1000/ms if w==1 else 15 if 'hybrid' in n else 25 if n=='fast standalone' else 30)
            raw.append(dict(name=n,workers=w,repeat=1,throughput_per_s=rate,median_task_ms=ms,cpu_ms_per_job=100,peak_rss_mib=20,rss_delta_mib=8))
    rows=summarize(configs,raw,[1,4],10,5,10,5); rr={r['name']:r for r in rows if r['workers']==4}
    assert rr['fast hybrid']['candidate_with_resource_budget'] and not rr['fast hybrid']['equal_latency_candidate']
    assert not rr['slow hybrid']['candidate'] and not rr['slow hybrid']['within_latency_ceiling']
    assert rr['fast hybrid']['best_global_standalone']=='fast standalone'
    for r in raw: r['cpu_ms_per_job']=0
    assert not any(r['candidate_with_resource_budget'] or r['resource_candidate'] for r in summarize(configs,raw,[1,4],10,5,10,5))
    print(f'PASS: one-sided latency, fast control eligibility, equal-latency separation, zero CPU timer; {len(plan)} planned calibrations.')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for f in ('self-test','smoke','screen','skip-bcrypt'): ap.add_argument('--'+f,action='store_true')
    ap.add_argument('--source',type=Path,default=HERE/'source_5c_configs.json'); ap.add_argument('--out',type=Path,default=Path('results/exp5e_screen')); ap.add_argument('--confirm-from',type=Path); ap.add_argument('--max-workers',type=int,choices=(2,4,8,12,16,24),default=8); ap.add_argument('--max-memory-mib',type=int,default=192); ap.add_argument('--tolerance',type=float,default=10); ap.add_argument('--equal-tolerance',type=float,default=5); ap.add_argument('--resource-tolerance',type=float,default=10); ap.add_argument('--min-gain',type=float,default=5); ap.add_argument('--targets',type=targets_arg,default=DEFAULT_TARGETS); ap.add_argument('--screen-repeats',type=int,default=2); ap.add_argument('--top',type=int,default=6); ap.add_argument('--worker-json'); ap.add_argument('--workers',type=int,default=1); ap.add_argument('--jobs',type=int,default=2); ap.add_argument('--offset',type=int,default=0)
    a=ap.parse_args()
    if a.worker_json: print(json.dumps(core.worker(json.loads(a.worker_json),a.workers,a.jobs,a.offset))); return
    if core.bcrypt is None and not a.skip_bcrypt: ap.error('bcrypt required; install requirements or use --skip-bcrypt')
    if a.self_test: selftest(a.skip_bcrypt); return
    if not (0<a.tolerance<=30 and 0<a.equal_tolerance<=20 and 0<=a.resource_tolerance<=50 and 0<a.min_gain<100 and 8<=a.max_memory_mib<=768 and a.top>=1 and 1<=a.screen_repeats<=7): ap.error('Invalid settings')
    if a.confirm_from and (a.smoke or a.screen): ap.error('Confirmation cannot use smoke or screen')
    out=a.out
    if out.exists() and any(out.iterdir()): ap.error('Choose a fresh output directory')
    out.mkdir(parents=True,exist_ok=True)
    if a.confirm_from:
        meta=d.load(a.confirm_from/'environment.json')
        if meta.get('version')!='5E': ap.error('Use a completed 5E screening directory, not 5D')
        for k,v in [('tolerance_pct',a.tolerance),('equal_tolerance_pct',a.equal_tolerance),('resource_tolerance_pct',a.resource_tolerance),('min_gain_pct',a.min_gain)]:
            if meta[k]!=v: ap.error(f'Confirmation must retain screening {k}={meta[k]}')
        old=d.load(a.confirm_from/'configs.json'); ranking=list(csv.DictReader((a.confirm_from/'ranking.csv').open(encoding='utf-8')))
        matched=[r for r in ranking if r['family'] not in CONTROL and r['within_latency_ceiling']=='True']
        matched.sort(key=lambda r:(r['candidate_with_resource_budget']!='True',r['candidate']!='True',float(r['throughput_vs_best_pct'])))
        picked={r['name'] for r in matched[:a.top]}; configs=[c for c in old if c['family'] in CONTROL or c['name'] in picked]
        existing={d.key(c['stages']) for c in configs if c['family'] in CONTROL}
        for c in [x for x in configs if x['name'] in picked]:
            for s in [x for x in c['stages'] if x['kind'] in V]:
                for v in V:
                    for t in (1,2,3,4):
                        z=[prev.ar(v,s['m'],t,s.get('p',1))]
                        if d.key(z) not in existing:
                            configs.append(core.config(f'{core.LABELS[v]} direct {s["m"]} MiB t={t} p={s.get("p",1)}',z,'fixed-memory standalone')); existing.add(d.key(z))
        target=meta['calibration_target_ms']/1000; planned=len(configs); targets=meta['targets_pct']; repeats=7; per=3; levels=[w for w in (1,2,4,8,12,16,24) if w<=a.max_workers]
        print(f'Confirming {len(picked)} hybrids and {len(configs)-len(picked)} controls (fixed parameters)',flush=True)
    else:
        cap=8 if a.smoke else a.max_memory_mib; targets=(50,110) if a.smoke else a.targets
        if psutil.virtual_memory().available<(2*cap+256)*2**20: ap.error('Insufficient RAM for calibration')
        configs,target,planned=calibrate(d.load(a.source),targets,a.smoke,a.skip_bcrypt,cap,2 if a.smoke else 4,out)
        repeats=1 if a.smoke else a.screen_repeats; per=1 if a.smoke else 2; levels=[1,2] if a.smoke else sorted({1,min(4,a.max_workers),a.max_workers})
    maxstage=max(core.memory_mib(s) for c in configs for s in c['stages'])
    if psutil.virtual_memory().available<(2*maxstage*max(levels)+256)*2**20: ap.error('Insufficient RAM; reduce --max-workers')
    assert len({c['name'] for c in configs})==len(configs)
    d.dump(out/'configs.json',configs); rng=random.Random(53802 if a.confirm_from else 53801); raw=[]; total=len(configs)*len(levels)*repeats
    # Append completed batches; avoid repeatedly rewriting large CSV files.
    with (out/'raw_batches.csv').open('w',newline='',encoding='utf-8') as f:
        writer=None
        for repeat in range(repeats):
            plan=[(c,w) for c in configs for w in levels]; rng.shuffle(plan)
            for c,w in plan:
                child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker-json',json.dumps(c),'--workers',str(w),'--jobs',str(w*per),'--offset',str((600000 if a.confirm_from else 500000)+repeat*1000)],capture_output=True,text=True)
                if child.returncode: raise RuntimeError(child.stderr or child.stdout)
                row=dict(name=c['name'],repeat=repeat+1,**json.loads(child.stdout)); raw.append(row)
                if writer is None: writer=csv.DictWriter(f,fieldnames=list(row)); writer.writeheader()
                writer.writerow(row)
                if len(raw)%10==0 or len(raw)==total: f.flush(); print(f'Batch {len(raw)}/{total}',flush=True)
    rows=summarize(configs,raw,levels,a.tolerance,a.min_gain,a.resource_tolerance,a.equal_tolerance); core.csvwrite(out/'summary.csv',rows)
    ranking=sorted([r for r in rows if r['workers']==max(levels)],key=lambda r:(not r['within_latency_ceiling'],r['throughput_per_s'])); core.csvwrite(out/'ranking.csv',ranking)
    core.csvwrite(out/'equal_latency_ranking.csv',sorted([r for r in ranking if r['equal_anchor_match']],key=lambda r:r['throughput_per_s']))
    plots(out,rows,levels)
    d.dump(out/'environment.json',dict(version='5E',calibration_target_ms=target*1000,measured_anchor_ms=ranking[0]['anchor_latency_ms'],latency_ceiling_ms=ranking[0]['latency_ceiling_ms'],targets_pct=targets,planned_calibrations=planned,workers=levels,repeats=repeats,jobs_per_worker=per,configurations=len(configs),python=sys.version,platform=platform.platform(),processor=platform.processor(),logical_cpus=os.cpu_count(),tolerance_pct=a.tolerance,equal_tolerance_pct=a.equal_tolerance,resource_tolerance_pct=a.resource_tolerance,min_gain_pct=a.min_gain,confirmation_from=str(a.confirm_from) if a.confirm_from else None,synthetic_only=True,backend='CPU native libraries'))
    if (out/'calibrated_partial.json').exists(): (out/'calibrated_partial.json').unlink()
    print(f'Finished: {out.resolve()} | latency candidates: {sum(r["candidate"] for r in ranking)} | strict resource candidates: {sum(r["candidate_with_resource_budget"] for r in ranking)}',flush=True)

if __name__=='__main__': main()
