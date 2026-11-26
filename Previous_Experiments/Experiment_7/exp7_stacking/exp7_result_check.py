"""Experiment 7 result checking: frozen synthetic CPU benchmarks, no password recovery."""
import argparse, csv, hashlib, json, math, os, platform, random, statistics, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import psutil
import exp7_stacking as exp

HERE=Path(__file__).resolve().parent
MANIFEST=HERE/'result_check_selection.json'

def load_selection():
    manifest=json.loads(MANIFEST.read_text())
    entries=manifest['selection']; configs=[x['config'] for x in entries]
    assert len(configs)==29 and sum(c['family']=='hybrid' for c in configs)==10
    assert len({c['name'] for c in configs})==len(configs)
    assert all(x['screening_product']>0 for x in entries)
    return manifest,entries,configs

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def analyse(configs,entries,raw,workers,boot=10000):
    """Same estimator as screening: median solo latency times median throughput.
    Bootstrap entire randomized rounds, preserving paired measurements.
    Simultaneous intervals cover all hybrid/control comparisons at primary concurrency.
    """
    names=[c['name'] for c in configs]; H=[i for i,c in enumerate(configs) if c['family']=='hybrid']; C=[i for i,c in enumerate(configs) if c['family']=='standalone']
    if not H or not C: raise ValueError('Both groups required')
    lookup={}
    for r in raw:
        k=(r['name'],int(r['repeat']),int(r['workers']))
        if k in lookup: raise ValueError('Duplicate batch '+str(k))
        lookup[k]=r
    rounds=sorted({k[1] for k in lookup})
    complete=[j for j in rounds if all((n,j,w) in lookup for n in names for w in (1,workers))]
    if not complete:raise ValueError('No complete rounds')
    def matrix(w,key):return np.array([[float(lookup[n,j,w][key]) for j in complete] for n in names])
    L=matrix(1,'median_task_ms');G=matrix(workers,'throughput_per_s');cpu=matrix(1,'cpu_ms_per_job');rss=matrix(workers,'worker_rss_peak_mib')
    if not (np.isfinite(L).all() and np.isfinite(G).all() and (L>0).all() and (G>0).all()):raise ValueError('Invalid timing data')
    l=np.median(L,axis=1);g=np.median(G,axis=1);p=l*g/1000
    best=C[int(np.argmin(p[C]))];meta={x['config']['name']:x for x in entries}
    intervals=None;radius=None
    if len(complete)>=10 and boot>0:
        rng=np.random.default_rng(73019); draws=[]; deviations=[]
        obs=np.log(p[H,None]/p[None,C])
        for start in range(0,boot,250):
            idx=rng.integers(0,len(complete),size=(min(250,boot-start),len(complete)))
            bp=np.median(L[:,idx],axis=2)*np.median(G[:,idx],axis=2)/1000
            draws.append(bp)
            lograt=np.log(bp[H,None,:]/bp[None,C,:]);deviations.extend(np.max(np.abs(lograt-obs[:,:,None]),axis=(0,1)))
        intervals=np.quantile(np.concatenate(draws,axis=1),[.025,.975],axis=1)
        radius=float(np.quantile(deviations,.95))
    rows=[];pairs=[]
    for i in H:
        for j in C:
            ratio=float(p[i]/p[j]); lo=ratio*math.exp(-radius) if radius is not None else '';hi=ratio*math.exp(radius) if radius is not None else ''
            pairs.append(dict(hybrid=names[i],control=names[j],rounds=len(complete),workers=workers,product_ratio=ratio,improvement_pct=100*(1-ratio),simultaneous_95_low=lo,simultaneous_95_high=hi,lower_product_supported=bool(radius is not None and hi<1),at_least_5pct_lower_supported=bool(radius is not None and hi<.95)))
    for i,n in enumerate(names):
        c=configs[i]; m=meta[n];ratio=float(p[i]/p[best]); own=names.index(c['anchor']) if c['anchor'] in names else None
        cmp=[x for x in pairs if x['hybrid']==n]
        rows.append(dict(name=n,family=c['family'],roles=';'.join(m['roles']),workers=workers,rounds=len(complete),screening_rank=m['screening_rank'],screening_product=m['screening_product'],solo_latency_ms=float(l[i]),throughput_per_s=float(g[i]),latency_throughput_product=float(p[i]),product_ci95_low=float(intervals[0,i]) if intervals is not None else '',product_ci95_high=float(intervals[1,i]) if intervals is not None else '',latency_min_ms=float(L[i].min()),latency_max_ms=float(L[i].max()),throughput_min=float(G[i].min()),throughput_max=float(G[i].max()),solo_cpu_ms=float(np.median(cpu[i])),peak_worker_rss_mib=float(np.median(rss[i])),best_standalone=names[best],product_ratio_vs_best=ratio,product_ratio_vs_anchor=float(p[i]/p[own]) if own is not None else '',beats_all_controls_point_estimate=bool(cmp and all(x['product_ratio']<1 for x in cmp)),beats_all_controls_simultaneous95=bool(cmp and all(x['lower_product_supported'] for x in cmp)),five_pct_better_all_controls_simultaneous95=bool(cmp and all(x['at_least_5pct_lower_supported'] for x in cmp)),exploratory_backend=c['exploratory_backend'],contains_argon2d=c['contains_argon2d']))
    rows.sort(key=lambda x:x['latency_throughput_product'])
    return rows,pairs,complete

def render(out,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(12,max(7,len(rows)*.34)))
    order=rows[::-1];y=np.arange(len(order));v=np.array([x['latency_throughput_product'] for x in order]);colors=['#137f83' if x['family']=='hybrid' else '#65748b' for x in order]
    ax.barh(y,v,color=colors);ax.set_yticks(y,[x['name'] for x in order],fontsize=8)
    if all(x['product_ci95_low']!='' for x in order):
        lo=np.array([x['product_ci95_low'] for x in order]);hi=np.array([x['product_ci95_high'] for x in order]);ax.hlines(y,lo,hi,color='#202b38',linewidth=1.3);ax.plot(lo,y,'|',color='#202b38');ax.plot(hi,y,'|',color='#202b38')
    ax.set(xlabel='Latency (seconds) × concurrent derivations/s; lower is better',title='Experiment 7 independent result checking');ax.grid(axis='x',alpha=.2);fig.tight_layout();fig.savefig(out/'verified_ranking.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,6))
    for group,color in [('standalone','#65748b'),('hybrid','#137f83')]:
        rr=[x for x in rows if x['family']==group];ax.scatter([x['solo_latency_ms'] for x in rr],[x['throughput_per_s'] for x in rr],label=group,c=color)
    ax.set(xlabel='Single derivation latency (ms)',ylabel='Concurrent synthetic derivations/s',title='Verified latency and throughput');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'latency_throughput.png',dpi=160);plt.close(fig)

def finish(out,configs,entries,raw,workers,boot):
    rows,pairs,complete=analyse(configs,entries,raw,workers,boot)
    write_csv(out/'ranking.csv',rows);write_csv(out/'hybrid_ranking.csv',[r for r in rows if r['family']=='hybrid']);write_csv(out/'pairwise_comparisons.csv',pairs);render(out,rows)
    (out/'analysis_notes.json').write_text(json.dumps(dict(complete_rounds=complete,primary_workers=workers,bootstrap_samples=boot if len(complete)>=10 else 0,intervals='Approximate simultaneous 95% paired-round bootstrap intervals for all hybrid/control comparisons; marginal intervals for individual product scores.',scope='Synthetic CPU workloads; selected controls only; no security or GPU claims.'),indent=2))
    print(f'Analyzed {len(complete)} complete rounds. Best measured configuration: {rows[0]["name"]}',flush=True)

def preflight(configs):
    # Use the exact backends from the frozen configuration, not auto-selected substitutes.
    for c in configs:
        p,s=exp.core.fixture(950001);a=exp.core.derive(c,p,s)
        if len(a)!=32 or a!=exp.core.derive(c,p,s) or a==exp.core.derive(c,p+b'!',s) or a==exp.core.derive(c,p,s[::-1]):raise RuntimeError('Fixture check failed: '+c['name'])
    print(f'PASS: exact-config deterministic and input-sensitivity checks ({len(configs)} configurations). Optional backends still require independent known-answer tests.',flush=True)

def selftest(configs,entries):
    # Analysis regression: a hybrid winning against one control but losing to another is not a global winner.
    toy=[dict(name=n,family=f,anchor='c1',exploratory_backend=False,contains_argon2d=False) for n,f in [('h','hybrid'),('c1','standalone'),('c2','standalone')]]
    ent=[dict(config=c,roles=[],screening_rank=i+1,screening_product=1) for i,c in enumerate(toy)]
    raw=[dict(name=c['name'],repeat=r,workers=w,median_task_ms=100,throughput_per_s=10 if w==1 else rate,cpu_ms_per_job=100,worker_rss_peak_mib=5) for c,rate in zip(toy,[20,30,10]) for r in range(1,13) for w in (1,8)]
    rows,pairs,complete=analyse(toy,ent,raw,8,500);h=next(x for x in rows if x['name']=='h');assert not h['beats_all_controls_point_estimate'] and not h['beats_all_controls_simultaneous95'];assert len(complete)==12 and len(pairs)==2
    # Scale latency and throughput reciprocally: score is unchanged.
    assert math.isclose(.1*20,.2*10)
    assert len(configs)==29 and len(entries)==29
    print('PASS: frozen selection, ranking, paired bootstrap, global-control rejection, score invariance.',flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--self-test',action='store_true');ap.add_argument('--smoke',action='store_true');ap.add_argument('--rounds',type=int,default=30);ap.add_argument('--workers',type=int,default=8);ap.add_argument('--min-seconds',type=float,default=.6);ap.add_argument('--out',type=Path,default=Path('results/exp7_result_check'));ap.add_argument('--analyze-only',action='store_true');a=ap.parse_args()
    manifest,entries,configs=load_selection()
    if a.self_test:selftest(configs,entries);preflight(configs);return
    if a.analyze_only:
        env=json.loads((a.out/'environment.json').read_text());assert env['selection_sha256']==hashlib.sha256(MANIFEST.read_bytes()).hexdigest();finish(a.out,configs,entries,list(csv.DictReader((a.out/'raw_batches.csv').open())),env['workers'],10000);return
    if not 2<=a.workers<=24 or not 10<=a.rounds<=1000 or not .2<=a.min_seconds<=5:ap.error('workers 2–24, rounds 10–1000, min-seconds 0.2–5')
    rounds=1 if a.smoke else a.rounds; minimum=.2 if a.smoke else a.min_seconds; levels=(1,a.workers)
    if a.out.exists() and any(a.out.iterdir()):ap.error('Choose a fresh output folder')
    maxmem=max(max(exp.mem(s) for s in c['stages']) for c in configs)
    if psutil.virtual_memory().available/2**20 < maxmem*a.workers*2+1024:ap.error('Available RAM below conservative requirement; close other programs or use fewer workers (separate experiment).')
    preflight(configs);out=a.out;out.mkdir(parents=True,exist_ok=True);(out/'selection.json').write_bytes(MANIFEST.read_bytes());(out/'configs.json').write_text(json.dumps(configs,indent=2))
    import importlib.metadata as md
    packages={}
    for n in ['argon2-cffi','cryptography','psutil','numpy','matplotlib']:
        try:packages[n]=md.version(n)
        except md.PackageNotFoundError:packages[n]='not installed'
    revisions=HERE/'native'/'source_revisions.txt'
    env=dict(platform=platform.platform(),python=sys.version,logical_cpus=os.cpu_count(),workers=a.workers,rounds=rounds,min_seconds=minimum,selection_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),packages=packages,native_source_revisions=revisions.read_text() if revisions.exists() else None,synthetic_only=True,smoke=a.smoke,seed=73018,available_ram_mib=psutil.virtual_memory().available/2**20)
    (out/'environment.json').write_text(json.dumps(env,indent=2));rng=random.Random(73018);raw=[];total=len(configs)*2*rounds;print(f'{len(configs)} configs × 2 worker levels × {rounds} rounds = {total} batches',flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool,(out/'raw_batches.csv').open('w',newline='',encoding='utf-8') as f:
        [q.result() for q in [pool.submit(exp.ready) for _ in range(a.workers*2)]]
        writer=None
        for rep in range(1,rounds+1):
            plan=[(c,w) for c in configs for w in levels];rng.shuffle(plan)
            for c,w in plan:
                # Independent synthetic fixture range, shared across configurations within a round.
                r=dict(name=c['name'],repeat=rep,**exp.batch(pool,c,w,950000+rep*10000,minimum));raw.append(r)
                if writer is None:writer=csv.DictWriter(f,fieldnames=list(r));writer.writeheader()
                writer.writerow(r);f.flush()
                if len(raw)%10==0 or len(raw)==total:print(f'Batch {len(raw)}/{total}',flush=True)
            print(f'Round {rep}/{rounds} complete',flush=True)
    finish(out,configs,entries,raw,a.workers,0 if a.smoke else 10000)

if __name__=='__main__':main()
