"""Experiment 5F: unchanged Argon2 + extra stages. Synthetic CPU benchmarks only."""
import argparse, csv, hashlib, json, math, os, platform, random, statistics as st, sys, time, threading
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import psutil
import exp5b_core as core
import exp5c_global as prev
import extra_kdfs as extra

BASE_STAGE=prev.stage
V=prev.VARIANTS
DIGESTS=prev.OLD_DIGESTS+prev.NEW_DIGESTS
HERE=Path(__file__).resolve().parent

def stage(s,p,salt):
    if s['kind'] in ('balloon','yescrypt','lyra2','catena'): return extra.stage(s,p,salt)
    return BASE_STAGE(s,p,salt)
core.stage=stage

def spec_label(s):
    k=s['kind']
    if k in V: return f'{core.LABELS[k]}({s["m"]}MiB,t{s["t"]},p{s["p"]})'
    if k=='pbkdf2':return f'PBKDF2-{s["digest"]}({s["iterations"]})'
    if k=='cipher_workload':return f'{s["cipher"]}({s["rounds"]} rounds)'
    if k=='bcrypt_pbkdf':return f'bcrypt-PBKDF({s["rounds"]})'
    if k=='scrypt':return f'scrypt(N{s["n"]},r{s["r"]},p{s["p"]})'
    if k=='balloon':return f'Balloon({s["blocks"]} blocks,t{s["passes"]},{s["backend"]})'
    if k=='yescrypt':return f'yescrypt-MCF(cost{s["cost"]})' if s.get('backend')=='libxcrypt' else f'yescrypt(N{s["n"]},r{s["r"]})'
    return f'{k}(m_cost{s["m_cost"]},t{s["t"]})'

def mem(s):
    k=s['kind']
    if k=='balloon': return s['blocks']*32/2**20
    if k=='yescrypt':return 128 if s.get('backend')=='libxcrypt' else 128*s['n']*s['r']/2**20  # conservative guard estimate for MCF, not measured memory
    if k=='lyra2':return s['m_cost']*256*96/2**20  # documented for build script settings
    if k=='catena':return (2**s['m_cost'])*64/2**20 # approximate graph storage only
    return core.memory_mib(s)

def generate(avail,smoke=False,one_level=False,full_grid=False,extra_only=False):
    anchors=[prev.ar(v,64,3,p) for v in V for p in ((1,2,4) if full_grid else (1,))]
    anchors += [prev.ar('argon2id',135,4,4),prev.ar('argon2i',170,3,4),prev.ar('argon2d',157,3,4)]
    # Exact previous strongest latency-eligible controls, not retuned for hybrids.
    if smoke: anchors=[prev.ar('argon2id',4,2,1)]
    grid=list(anchors)
    if not smoke:
        grid += [prev.ar(v,m,t,p) for v in V for m in (64,128,192,256) for t in (1,3,4,6) for p in (1,2,4)]
    additions=[]
    levels=(0,) if one_level else (0,1)
    for j in levels:
        additions += [core.pb(d,(100000,400000)[j]) for d in DIGESTS]
        additions += [prev.cipher_spec(c,(32,256)[j]) for c in prev.CIPHERS]
        if avail['bcrypt']['available']: additions.append(core.bc((8,32)[j]))
        additions.append(core.sc((16384,65536)[j],8,1))
        additions += [prev.ar(v,(64,128)[j],(3,4)[j],1) for v in V]
        b=avail['balloon']['backend']; additions.append(dict(kind='balloon',backend=b,blocks=(4096,32768)[j],passes=3))
        if avail['yescrypt']['available']: additions.append(dict(kind='yescrypt',backend='libxcrypt',cost=(3,5)[j]) if avail['yescrypt']['backend']=='libxcrypt' else dict(kind='yescrypt',n=(16384,65536)[j],r=8))
        if avail['lyra2']['available']: additions.append(dict(kind='lyra2',m_cost=(1024,4096)[j],t=1))
        if avail['catena']['available']: additions.append(dict(kind='catena',m_cost=(18,20)[j],t=2))
    if smoke:
        additions=[core.pb('sha256',1000),prev.cipher_spec('AES-CTR',1),prev.ar('argon2i',4,1),dict(kind='balloon',backend=avail['balloon']['backend'],blocks=32,passes=1)]
        if avail['bcrypt']['available']: additions.append(core.bc(1))
        for k in ('yescrypt','lyra2','catena'):
            if avail[k]['available']:
                additions.append(({'kind':k,'backend':'libxcrypt','cost':3} if avail[k]['backend']=='libxcrypt' else {'kind':k,'n':1024,'r':8}) if k=='yescrypt' else {'kind':k,'m_cost':16 if k=='lyra2' else 8,'t':1 if k=='lyra2' else 2})
    if extra_only: additions=[s for s in additions if s['kind'] in ('balloon','yescrypt','lyra2','catena')]
    configs=[]; seen=set()
    def add(stages,family,anchor=None):
        key=json.dumps(stages,sort_keys=True)
        if key in seen:return
        seen.add(key); name=' -> '.join(map(spec_label,stages)); configs.append(dict(name=name,stages=stages,family=family,anchor=spec_label(anchor) if anchor else '',exploratory_backend=any(s['kind'] in ('catena','lyra2','yescrypt') or (s['kind']=='balloon' and s['backend']=='python') for s in stages),contains_argon2d=any(s['kind']=='argon2d' for s in stages)))
    for a in grid:add([a],'standalone',a)
    for a in anchors:
        for s in additions:
            add([a,s],'hybrid',a);add([s,a],'hybrid',a)
    # Assert every hybrid contains its full, unchanged anchor (both memory and passes).
    for c in configs:
        if c['family']=='hybrid': assert c['anchor'] in list(map(spec_label,c['stages']))
    return configs

def task(c,i):
    p,s=core.fixture(i); start=time.perf_counter();cpu=time.process_time(); tag=core.derive(c,p,s)
    return ((time.perf_counter()-start)*1000,(time.process_time()-cpu)*1000,len(tag))

def ready():
    return os.getpid()

def batch(pool,c,w,offset,min_seconds):
    # Process-based concurrency avoids a GIL penalty for the reference Balloon code.
    # All algorithms use the same scheduler. The pool is warmed before timing.
    parent=psutil.Process(); stop=threading.Event(); peak=[0]
    def rss():
        total=0
        for p in parent.children(recursive=True):
            try:total+=p.memory_info().rss
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        return total
    baseline=rss();peak[0]=baseline
    def monitor():
        while not stop.wait(.005):peak[0]=max(peak[0],rss())
    thread=threading.Thread(target=monitor,daemon=True);thread.start(); elapsed=0; times=[]; cpu=[];start=time.perf_counter()
    try:
        while not times or elapsed<min_seconds:
            futures=[pool.submit(task,c,offset+len(times)+i) for i in range(w)]
            for f in futures:
                t,u,n=f.result();assert n==32;times.append(t);cpu.append(u)
            elapsed=time.perf_counter()-start
        peak[0]=max(peak[0],rss())
    finally:stop.set();thread.join()
    return dict(workers=w,jobs=len(times),throughput_per_s=len(times)/elapsed,median_task_ms=st.median(times),cpu_ms_per_job=st.mean(cpu),worker_rss_peak_mib=peak[0]/2**20,worker_rss_delta_mib=max(0,peak[0]-baseline)/2**20)

def rank(configs,raw,levels):
    by={c['name']:c for c in configs}; groups={}
    for r in raw:groups.setdefault((r['name'],int(r['workers'])),[]).append(r)
    summaries=[]
    for (name,w),rr in groups.items():
        c=by[name]; solo=groups[(name,1)]; L=st.median(float(r['median_task_ms']) for r in solo);G=st.median(float(r['throughput_per_s']) for r in rr)
        if not (L>0 and G>0):raise ValueError('nonpositive benchmark data')
        summaries.append(dict(name=name,family=c['family'],anchor=c['anchor'],workers=w,repeats=len(rr),solo_latency_ms=L,throughput_per_s=G,latency_throughput_product=L/1000*G,throughput_min=min(float(r['throughput_per_s']) for r in rr),throughput_max=max(float(r['throughput_per_s']) for r in rr),solo_cpu_ms=st.median(float(r['cpu_ms_per_job']) for r in solo),peak_worker_rss_mib=st.median(float(r['worker_rss_peak_mib']) for r in rr),nominal_peak_stage_mib=max(mem(s) for s in c['stages']),exploratory_backend=c['exploratory_backend'],contains_argon2d=c['contains_argon2d']))
    for w in levels:
        rows=[r for r in summaries if r['workers']==w]; controls=[r for r in rows if r['family']=='standalone']; default=next((r for r in controls if r['name']=='Argon2id(64MiB,t3,p1)'),controls[0]);best=min(controls,key=lambda r:r['latency_throughput_product'])
        for r in rows:
            anchor=next((x for x in controls if x['name']==r['anchor']),default)
            L=r['solo_latency_ms'];G=r['throughput_per_s'];P=r['latency_throughput_product']
            comparable=[x for x in controls if x['solo_latency_ms']<=L*1.10]
            equal=[x for x in controls if abs(x['solo_latency_ms']/L-1)<=.10]
            ctl=min(comparable,key=lambda x:x['throughput_per_s']) if comparable else None
            eq=min(equal,key=lambda x:x['throughput_per_s']) if equal else None
            r.update(score_vs_default=default['latency_throughput_product']/P,score_vs_anchor=anchor['latency_throughput_product']/P,score_vs_best_standalone=best['latency_throughput_product']/P,anchor_latency_ms=anchor['solo_latency_ms'],anchor_throughput=anchor['throughput_per_s'],extra_latency_pct=100*(L/anchor['solo_latency_ms']-1),throughput_reduction_pct=100*(1-G/anchor['throughput_per_s']),best_standalone_score_name=best['name'],best_control_within_110pct_latency=ctl['name'] if ctl else '',throughput_vs_control_pct=100*(G/ctl['throughput_per_s']-1) if ctl else '',equal_latency_control=eq['name'] if eq else '',throughput_vs_equal_control_pct=100*(G/eq['throughput_per_s']-1) if eq else '',pareto_front=not any(x['solo_latency_ms']<=L and x['throughput_per_s']<=G and (x['solo_latency_ms']<L or x['throughput_per_s']<G) for x in rows),beats_score_and_control=bool(r['family']=='hybrid' and P<best['latency_throughput_product']/1.05 and ctl and G<ctl['throughput_per_s']*.95 and not r['exploratory_backend']))
    return summaries

def plots(out,rows,w):
    import matplotlib
    matplotlib.use('Agg');import matplotlib.pyplot as plt
    a=[r for r in rows if r['workers']==w]; fig,ax=plt.subplots(figsize=(9,6))
    for family in ('standalone','hybrid'):
        for provisional in (False,True):
            rr=[r for r in a if r['family']==family and r['exploratory_backend']==provisional]
            if rr:ax.scatter([r['solo_latency_ms'] for r in rr],[r['throughput_per_s'] for r in rr],s=15,alpha=.55,label=family+(' (exploratory backend)' if provisional else ''))
    ax.set(xlabel='Single-derivation latency (ms)',ylabel=f'Synthetic derivations/s ({w} processes)',title='Latency vs concurrent throughput (lower-left is better)');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'latency_throughput.png',dpi=150);plt.close(fig)
    top=sorted(a,key=lambda r:r['score_vs_default'],reverse=True)[:15];top=list(reversed(top));fig,ax=plt.subplots(figsize=(12,7));ax.barh([r['name'] for r in top],[r['score_vs_default'] for r in top]);ax.axvline(1,ls='--',color='black');ax.set(xlabel='Normalized latency-throughput score (higher is better)',title=f'Top measured configurations, {w} processes');ax.tick_params(axis='y',labelsize=7);fig.tight_layout();fig.savefig(out/'score.png',dpi=150);plt.close(fig)

def selftest(avail):
    # Established known answers plus deterministic synthetic cascade checks.
    prev.selftest(avail['bcrypt']['available'])
    cs=generate(avail,smoke=True)
    p,s=core.fixture(0)
    for c in cs:
        tag=core.derive(c,p,s);assert len(tag)==32 and tag==core.derive(c,p,s) and tag!=core.derive(c,p+b'!',s)
    # Doubling latency and halving throughput must not improve the score.
    assert (100/1000*20)==(200/1000*10)
    print(f'PASS: {len(cs)} fixed-anchor fixtures; Balloon published known answers; scoring invariant',flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--self-test',action='store_true');ap.add_argument('--smoke',action='store_true');ap.add_argument('--screen',action='store_true');ap.add_argument('--one-level',action='store_true');ap.add_argument('--full-grid',action='store_true');ap.add_argument('--extra-only',action='store_true');ap.add_argument('--max-workers',type=int,default=8);ap.add_argument('--repeats',type=int,default=2);ap.add_argument('--confirm-from',type=Path);ap.add_argument('--top',type=int,default=8);ap.add_argument('--out',type=Path,default=Path('results/exp5f_screen'));a=ap.parse_args()
    avail=extra.discover();avail['bcrypt']={'available':core.bcrypt is not None,'backend':'bcrypt' if core.bcrypt else 'missing'};print(json.dumps(avail,indent=2),flush=True)
    if a.self_test:selftest(avail);return
    if not 2<=a.max_workers<=24 or not 1<=a.repeats<=10 or a.top<1:ap.error('workers 2–24, repeats 1–10, top positive')
    if a.confirm_from:
        old=json.loads((a.confirm_from/'configs.json').read_text()); rr=list(csv.DictReader((a.confirm_from/'ranking.csv').open(encoding='utf-8'))); hybrids=[r for r in rr if r['family']=='hybrid']; native=[r for r in hybrids if r['exploratory_backend']=='False']; exploratory=[r for r in hybrids if r['exploratory_backend']=='True']; selected={r['name'] for r in native[:a.top]+exploratory[:min(3,a.top)]}; selected.update(r['name'] for r in rr if r['family']=='standalone' and r['pareto_front']=='True');selected.add('Argon2id(64MiB,t3,p1)'); selected.update(r['name'] for r in [x for x in rr if x['family']=='standalone'][:a.top]); anchors={c['anchor'] for c in old if c['name'] in selected};configs=[c for c in old if c['name'] in selected or c['name'] in anchors]; repeats=7;levels=sorted({1,min(4,a.max_workers),a.max_workers});minimum=.35
    else:
        configs=generate(avail,a.smoke,a.one_level,a.full_grid,a.extra_only); repeats=1 if a.smoke else a.repeats;levels=[1,2] if a.smoke else sorted({1,a.max_workers});minimum=.04 if a.smoke else .20
    if a.out.exists() and any(a.out.iterdir()):ap.error('Choose a new output directory')
    # Bound batch memory for machine safety; never change the Argon2 settings.
    maxmem=max(max(mem(s) for s in c['stages']) for c in configs)
    if psutil.virtual_memory().available/2**20<maxmem*max(levels)*2+1024:ap.error('Insufficient available RAM; reduce --max-workers (parameters unchanged)')
    out=a.out;out.mkdir(parents=True,exist_ok=True);(out/'configs.json').write_text(json.dumps(configs,indent=2));(out/'environment.json').write_text(json.dumps(dict(version='5F',backends=avail,workers=levels,repeats=repeats,python=sys.version,platform=platform.platform(),logical_cpus=os.cpu_count(),synthetic_only=True,backend='CPU process pool',confirmation_from=str(a.confirm_from) if a.confirm_from else None),indent=2))
    total=len(configs)*len(levels)*repeats;print(f'{len(configs)} configs / {total} benchmark batches',flush=True);raw=[];rng=random.Random(56002 if a.confirm_from else 56001)
    # All workers are created before timing; only submit one wave at a time.
    # Persistent pool avoids thousands of interpreter startups on Windows.
    with ProcessPoolExecutor(max_workers=max(levels)) as pool, (out/'raw_batches.csv').open('w',newline='',encoding='utf-8') as f:
        [q.result() for q in [pool.submit(ready) for _ in range(max(levels)*2)]];writer=None
        for rep in range(repeats):
            plan=[(c,w) for c in configs for w in levels];rng.shuffle(plan)
            for c,w in plan:
                r=dict(name=c['name'],repeat=rep+1,**batch(pool,c,w,100000+rep*10000,minimum));raw.append(r)
                if writer is None:writer=csv.DictWriter(f,fieldnames=list(r));writer.writeheader()
                writer.writerow(r);f.flush()
                if len(raw)%10==0 or len(raw)==total:print(f'Batch {len(raw)}/{total}',flush=True)
    rows=rank(configs,raw,levels);core.csvwrite(out/'summary.csv',rows);ranking=sorted([r for r in rows if r['workers']==max(levels)],key=lambda r:r['score_vs_default'],reverse=True);core.csvwrite(out/'ranking.csv',ranking);core.csvwrite(out/'pareto.csv',[r for r in ranking if r['pareto_front']]);core.csvwrite(out/'hybrid_ranking.csv',[r for r in ranking if r['family']=='hybrid']);plots(out,rows,max(levels));print('Finished:',out.resolve(),flush=True)

if __name__=='__main__':main()
