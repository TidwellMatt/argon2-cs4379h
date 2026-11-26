"""Experiment 5C: synthetic KDF workload comparisons, not production cryptography.
No password recovery, real credentials, or security claims from CPU timings.
"""
import argparse, csv, hashlib, json, math, os, platform, random, statistics as st, subprocess, sys, time, ssl
from pathlib import Path
import psutil
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESCCM, ChaCha20Poly1305
from argon2.low_level import hash_secret_raw
import exp5b_core as core

CIPHERS=('AES-CTR','AES-CBC','AES-CFB','AES-OFB','AES-GCM','AES-CCM','Camellia-CBC','Camellia-CFB','ChaCha20','ChaCha20-Poly1305')
OLD_DIGESTS=('sha256','sha512','sha3_256')
NEW_DIGESTS=('sha224','sha384','sha3_224','sha3_384','sha3_512','blake2b','blake2s')
VARIANTS=tuple(core.VARIANTS)
ORIG_STAGE=core.stage
PAYLOAD=bytes(range(256))*1024  # 256 KiB synthetic public payload
CONTROL=('baseline','tuned standalone','fixed-memory standalone')

def ar(v,m,t,p=1): return dict(kind=v,m=int(m),t=int(t),p=int(p))
def conf(name,stages,family): return core.config(name,stages,family)
def cipher_spec(name,rounds): return dict(kind='cipher_workload',cipher=name,rounds=int(rounds))
def encrypt(name,key,nonce,data):
    if name=='AES-GCM': return AESGCM(key).encrypt(nonce[:12],data,None)
    if name=='AES-CCM': return AESCCM(key).encrypt(nonce[:12],data,None)
    if name=='ChaCha20-Poly1305': return ChaCha20Poly1305(key).encrypt(nonce[:12],data,None)
    if name=='ChaCha20': obj=Cipher(algorithms.ChaCha20(key,nonce),mode=None)
    else:
        alg,mode=name.split('-')
        if alg=='Camellia' or mode in ('CFB','OFB'):
            try:
                from cryptography.hazmat.decrepit.ciphers import algorithms as old_alg, modes as old_modes
            except ImportError: old_alg,old_modes=algorithms,modes
        else: old_alg,old_modes=algorithms,modes
        obj=Cipher(getattr(old_alg if alg=='Camellia' else algorithms,alg)(key),getattr(old_modes if mode in ('CFB','OFB') else modes,mode)(nonce))
    e=obj.encryptor(); return e.update(data)+e.finalize()

def stage(s,value,salt):
    k=s['kind']
    if k in core.VARIANTS:
        return hash_secret_raw(value,salt,s['t'],s['m']*1024,s.get('p',1),32,core.VARIANTS[k],version=19)
    if k=='cipher_workload':
        # Each iteration consumes all output and changes the next key. Public fixture only.
        # Cipher plus SHA256 workload, not an established password KDF.
        state=hashlib.sha256(b'exp5c/cipher/'+s['cipher'].encode()+salt+value).digest()
        for i in range(s['rounds']):
            nonce=hashlib.sha256(b'exp5c/nonce/'+salt+i.to_bytes(8,'big')).digest()[:16]
            state=hashlib.sha256(encrypt(s['cipher'],state,nonce,PAYLOAD)).digest()
        return state
    return ORIG_STAGE(s,value,salt)
core.stage=stage

def measure(c,n=3): return core.latency(c,n)
def single(s,n=3): return measure(conf('stage',[s],'stage'),n)
def fit(make,initial,lo,hi,target,steps=6):
    value=max(lo,min(hi,int(initial))); best=None; seen=set()
    for _ in range(steps):
        if value in seen: break
        seen.add(value); c=make(value); elapsed=measure(c,3)
        if best is None or abs(elapsed-target)<abs(best[1]-target): best=(c,elapsed)
        if abs(elapsed-target)/target<.015: break
        value=max(lo,min(hi,round(value*max(.25,min(4,target/max(elapsed,1e-9))))))
    return best

def fit_pair(first,make,initial,lo,hi,target,steps=6):
    # Match the mean of the two orderings without allowing different parameters.
    start=single(first); budget=max(target-start,target*.04)
    value=max(lo,min(hi,int(initial))); best=None; seen=set()
    for _ in range(steps):
        if value in seen: break
        seen.add(value); second=make(value)
        e1=measure(conf('cal',[first,second],'cal'),3); e2=measure(conf('cal',[second,first],'cal'),3); e=(e1+e2)/2
        score=max(abs(e1-target),abs(e2-target))
        if best is None or score<best[3]: best=(second,e1,e2,score)
        if score/target<.025: break
        # Adjust only the tunable second stage; avoid unstable jumps.
        second_est=max(target*.01,e-start)
        value=max(lo,min(hi,round(value*max(.25,min(4,budget/second_est)))))
    return best[:3]

def selftest(include_bcrypt=True):
    # Independent checks for standard primitives inherited from 5B.
    cfg=[]
    for v in VARIANTS:
        for d in OLD_DIGESTS+NEW_DIGESTS: cfg.append(conf('test',[ar(v,1,1),core.pb(d,2)],'test'))
        for name in CIPHERS:
            c=cipher_spec(name,2); cfg.extend([conf('test',[ar(v,1,1),c],'test'),conf('test',[c,ar(v,1,1)],'test')])
        for w in VARIANTS: cfg.append(conf('test',[ar(v,1,1),ar(w,2,1)],'test'))
    cfg.append(conf('test',[ar('argon2id',1,1),core.sc(1024,8,1)],'test'))
    if include_bcrypt: cfg.append(conf('test',[core.bc(1),ar('argon2id',1,1)],'test'))
    # NIST AES-256 CBC single-block known answer (SP800-38A F.2.5).
    key=bytes.fromhex('603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4')
    iv=bytes.fromhex('000102030405060708090a0b0c0d0e0f'); pt=bytes.fromhex('6bc1bee22e409f96e93d7e117393172a')
    assert encrypt('AES-CBC',key,iv,pt).hex()=='f58c4c04d6e5f1ba779eabfb5f7bfbd6'
    core.verify(cfg)
    # Toy ranking fixture: hybrid beats d, but loses to tuned id. It must NOT be flagged.
    toy=[conf('Argon2id baseline',[ar('argon2id',1,1)],'baseline'),conf('Argon2i baseline',[ar('argon2i',1,1)],'baseline'),conf('Argon2d baseline',[ar('argon2d',1,1)],'baseline'),conf('Argon2id tuned',[ar('argon2id',2,1)],'tuned standalone'),conf('toy hybrid',[ar('argon2d',1,1),ar('argon2id',1,1)],'mixed Argon2')]
    rr=[]
    for c,rate in zip(toy,(30,32,34,25,28)):
        for w in (1,4): rr.append(dict(name=c['name'],workers=w,repeat=1,throughput_per_s=10 if w==1 else rate,median_task_ms=100,cpu_ms_per_job=100,peak_rss_mib=10,rss_delta_mib=1))
    row=next(x for x in summarize(toy,rr,[1,4],.1,5,5) if x['name']=='toy hybrid' and x['workers']==4)
    assert row['best_global_standalone']=='Argon2id tuned' and not row['candidate']
    print(f'PASS: {len(cfg)} cascade fixtures; AES-CBC known answer; all 10 cipher constructions supported; global ranking regression check.',flush=True)

def calibrate(args):
    m=args.memory_mib; cap=args.max_memory_mib; t=args.passes
    anchor=conf('Argon2id baseline',[ar('argon2id',m,t)],'baseline'); target=measure(anchor,7)
    print(f'Common latency target: {target*1000:.2f} ms',flush=True)
    configs=[]; logs=[]
    def add(c,e=None):
        if any(x['name']==c['name'] for x in configs): raise ValueError('Duplicate config '+c['name'])
        e=measure(c,3) if e is None else e
        configs.append(c); logs.append(dict(name=c['name'],family=c['family'],calibration_ms=e*1000,target_ms=target*1000,error_pct=100*(e/target-1)))
        print(f'{len(configs):3d} {c["name"]}: {e*1000:.2f} ms',flush=True)
    for v in VARIANTS:
        label=core.LABELS[v]; add(conf(f'{label} baseline',[ar(v,m,t)],'baseline'))
        if args.smoke: continue
        for p in (1,2,4):
            for passes in sorted({1,2,t,4}):
                c,e=fit(lambda mem:conf(f'{label} tuned t={passes} p={p}',[ar(v,mem,passes,p)],'tuned standalone'),m,8,cap,target)
                add(c,e)
        # Compare with the second stage of the earlier promising hybrid (92 MiB).
        if cap>=92:
            for passes in (1,2,3): add(conf(f'{label} 92 MiB t={passes}',[ar(v,92,passes)],'fixed-memory standalone'))
    for v in VARIANTS:
        label=core.LABELS[v]
        def pair(first,second,name,family,e1=None,e2=None):
            add(conf(f'{label} -> {name}',[first,second],family),e1)
            add(conf(f'{name} -> {label}',[second,first],family),e2)
        if args.smoke:
            first=ar(v,m,1); pair(first,cipher_spec('AES-CTR',1),'AES-CTR smoke','cipher workload'); continue
        # Previous families retained, with two Argon2 pass splits for the older KDFs.
        for passes in sorted({1,t-1}):
            first=ar(v,m,passes); start=single(first); budget=max(target-start,target*.04)
            for d in OLD_DIGESTS+(NEW_DIGESTS if passes==1 or args.deep else ()):
                init=max(1,round(10000*budget/max(single(core.pb(d,10000)),1e-9)))
                sec,e1,e2=fit_pair(first,lambda n:core.pb(d,n),init,1,4000000,target)
                pair(first,sec,f'PBKDF2-{d} ({label} t={passes})','PBKDF2 cascade',e1,e2)
            if not args.skip_bcrypt:
                init=max(1,round(budget/max(single(core.bc(1)),1e-9)))
                sec,e1,e2=fit_pair(first,core.bc,init,1,128,target)
                pair(first,sec,f'bcrypt-PBKDF ({label} t={passes})','bcrypt-PBKDF cascade',e1,e2)
            # Scrypt discrete settings; choose nearest stage time then measure both orders.
            grid=[]
            for n in (1024,2048,4096,8192,16384,32768,65536,131072):
                for r in (4,8,12):
                    for p in (1,2):
                        s=core.sc(n,r,p)
                        if core.memory_mib(s)<=cap and core.memory_mib(s)>=2:
                            grid.append((s,single(s,2)))
            sec=min(grid,key=lambda x:abs(x[1]-budget))[0]
            pair(first,sec,f'scrypt ({label} t={passes})','scrypt cascade')
            if passes==1 or args.deep:
                for name in CIPHERS:
                    init=max(1,round(budget/max(single(cipher_spec(name,2))/2,1e-9)))
                    sec,e1,e2=fit_pair(first,lambda n:cipher_spec(name,n),init,1,4096,target)
                    pair(first,sec,f'{name} workload ({label} t={passes})','cipher workload',e1,e2)
        # Same and mixed Argon2 variants, two primary memory sizes.
        for other in VARIANTS:
            for primary in (m,max(8,m//2)) if other==v else (m,):
                first=ar(v,primary,1); sec,e1,e2=fit_pair(first,lambda n:ar(other,n,1),m,8,cap,target)
                pair(first,sec,f'{core.LABELS[other]} {sec["m"]} MiB (primary {label} {primary} MiB)','double Argon2' if v==other else 'mixed Argon2',e1,e2)
    # Add a direct standalone comparator for the peak stage memory of the prior candidate.
    return configs,logs,target

def summarize(configs,raw,workers,target,tol,min_gain):
    rows=[]; grouped={}
    for r in raw: grouped.setdefault((r['name'],r['workers']),[]).append(r)
    def med(name,w,k): return st.median(x[k] for x in grouped[name,w])
    anchor='Argon2id baseline'; anchor_ms=med(anchor,1,'median_task_ms')
    for c in configs:
        name=c['name']; solo=med(name,1,'median_task_ms'); solo_rate=med(name,1,'throughput_per_s')
        err=100*(solo/anchor_ms-1)
        for w in workers:
            group=grouped[name,w]; rate=med(name,w,'throughput_per_s')
            row=dict(name=name,family=c['family'],workers=w,repeats=len(group),solo_latency_ms=solo,solo_error_pct=err,matched=abs(err)<=tol,throughput_per_s=rate,scaling=rate/solo_rate,throughput_min=min(r['throughput_per_s'] for r in group),throughput_max=max(r['throughput_per_s'] for r in group))
            for k in ('median_task_ms','cpu_ms_per_job','peak_rss_mib','rss_delta_mib'): row[k]=med(name,w,k)
            rows.append(row)
    for r in rows:
        controls=[x for x in rows if x['workers']==r['workers'] and x['matched'] and x['family'] in CONTROL]
        best=min(controls,key=lambda x:x['throughput_per_s'])
        direct=100*(r['solo_latency_ms']/best['solo_latency_ms']-1); change=100*(r['throughput_per_s']/best['throughput_per_s']-1); scaling=100*(r['scaling']/best['scaling']-1)
        r.update(best_global_standalone=best['name'],best_standalone_ms=best['solo_latency_ms'],best_standalone_throughput=best['throughput_per_s'],latency_vs_best_pct=direct,throughput_vs_best_pct=change,scaling_vs_best_pct=scaling,directly_matched=abs(direct)<=tol)
        covered=all(any(x['name'].startswith(core.LABELS[v]+' ') for x in controls) for v in VARIANTS)
        r['all_variants_matched']=covered
        r['candidate']=bool(r['workers']>1 and covered and r['family'] not in CONTROL and r['matched'] and r['directly_matched'] and change<=-min_gain and scaling<0)
        c=next(c for c in configs if c['name']==r['name'])
        r['contains_argon2d']=any(s['kind']=='argon2d' for s in c['stages'])
        b={x['repeat']:x['throughput_per_s'] for x in grouped[best['name'],r['workers']]}
        x={x['repeat']:x['throughput_per_s'] for x in grouped[r['name'],r['workers']]}
        r['paired_repeats_lower']=sum(x[k]<b[k] for k in x.keys()&b.keys())
    for r in rows:
        levels=[x for x in rows if x['name']==r['name'] and x['workers']>=4]
        r['passes_at_multiple_high_concurrency_levels']=len(levels)>=2 and all(x['candidate'] for x in levels)
    return rows

def plots(out,rows,workers):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    matched=[r for r in rows if r['workers']==max(workers) and r['matched']]
    selected=sorted(matched,key=lambda x:x['throughput_per_s'])[:18]
    # Show best controls even if not in top 18.
    for v in VARIANTS:
        cc=[r for r in matched if r['family'] in CONTROL and r['name'].startswith(core.LABELS[v]+' ')]
        if cc:
            best=min(cc,key=lambda x:x['throughput_per_s'])
            if best not in selected: selected.append(best)
    for key,title,unit in [('throughput_per_s','Global matched throughput (lowest 18 + variant controls)','Derivations/s'),('solo_latency_ms','Individual hashing latency','ms'),('peak_rss_mib','Sampled peak process memory','MiB'),('scaling','Parallel scaling','Throughput / solo throughput')]:
        rr=sorted(selected,key=lambda x:x[key],reverse=True); fig,ax=plt.subplots(figsize=(12,max(5,len(rr)*.36)))
        ax.barh([r['name'] for r in rr],[r[key] for r in rr],color=['#355c91' if r['family'] in CONTROL else '#158477' for r in rr]); ax.set(title=title,xlabel=unit); ax.tick_params(axis='y',labelsize=8); fig.tight_layout(); fig.savefig(out/(key+'.png'),dpi=140); plt.close(fig)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for flag in ('self-test','quick','screen','deep','skip-bcrypt','smoke'): ap.add_argument('--'+flag,action='store_true')
    ap.add_argument('--out',type=Path,default=Path('results/exp5c_screen')); ap.add_argument('--confirm-from',type=Path); ap.add_argument('--memory-mib',type=int); ap.add_argument('--max-memory-mib',type=int); ap.add_argument('--passes',type=int,default=3); ap.add_argument('--max-workers',type=int,choices=[2,4,8,16],default=4); ap.add_argument('--tolerance',type=float,default=5); ap.add_argument('--min-gain',type=float,default=5); ap.add_argument('--top',type=int,default=5); ap.add_argument('--worker-json'); ap.add_argument('--workers',type=int,default=1); ap.add_argument('--jobs',type=int,default=2); ap.add_argument('--offset',type=int,default=0)
    args=ap.parse_args()
    if args.worker_json:
        print(json.dumps(core.worker(json.loads(args.worker_json),args.workers,args.jobs,args.offset))); return
    if core.bcrypt is None and not args.skip_bcrypt: ap.error('bcrypt missing: install requirements or explicitly use --skip-bcrypt')
    if args.self_test: selftest(not args.skip_bcrypt); return
    if args.confirm_from and (args.quick or args.smoke or args.screen): ap.error('confirmation cannot use quick/smoke/screen')
    if not 0<args.tolerance<=20 or not 0<args.min_gain<100 or args.top<1: ap.error('Invalid tolerance/gain/top')
    args.memory_mib=args.memory_mib or (8 if args.smoke else 16 if args.quick else 64)
    args.max_memory_mib=args.max_memory_mib or args.memory_mib*3
    if not 8<=args.memory_mib<=256 or not args.memory_mib<=args.max_memory_mib<=768 or not 2<=args.passes<=6: ap.error('Invalid memory/pass settings')
    workers=[1,2] if args.quick or args.smoke else [w for w in (1,2,4,8,16) if w<=args.max_workers]
    out=args.out
    if out.exists() and any(out.iterdir()): ap.error('Output directory is not empty; choose a fresh --out path')
    out.mkdir(parents=True,exist_ok=True)
    if args.confirm_from:
        old=json.loads((args.confirm_from/'configs.json').read_text()); prev=list(csv.DictReader((args.confirm_from/'ranking.csv').open(newline='',encoding='utf-8')))
        # Retest all original standalone controls and top matched candidates, even if none passed the threshold.
        ranked=[r for r in prev if r['family'] not in CONTROL and r['matched']=='True']; ranked.sort(key=lambda r:(r['candidate']!='True',float(r['throughput_vs_best_pct'])))
        chosen={r['name'] for r in ranked[:args.top]}; configs=[c for c in old if c['family'] in CONTROL or c['name'] in chosen]
        # Direct control at candidate's largest Argon2 memory; passes 1..3. Deduplicate by parameters.
        existing={json.dumps(c['stages'],sort_keys=True) for c in configs if c['family'] in CONTROL}
        for c in [c for c in configs if c['name'] in chosen]:
            peak=max(s['m'] for s in c['stages'] if s['kind'] in VARIANTS)
            for v in VARIANTS:
                for t in (1,2,3):
                    s=[ar(v,peak,t)]; k=json.dumps(s,sort_keys=True)
                    if k not in existing: configs.append(conf(f'{core.LABELS[v]} matched-stage {peak} MiB t={t}',s,'fixed-memory standalone')); existing.add(k)
        logs=[]; target=json.loads((args.confirm_from/'environment.json').read_text())['calibration_target_ms']/1000; repeats=7; per=5
        print('Confirming',len(chosen),'hybrids and',len(configs)-len(chosen),'controls.',flush=True)
    else:
        if psutil.virtual_memory().available<(2*args.max_memory_mib+256)*2**20: ap.error('Not enough available RAM for calibration')
        configs,logs,target=calibrate(args); repeats=1 if args.smoke else 2 if args.quick else 3; per=1 if args.smoke else 2 if args.quick else 3
    maxstage=max(core.memory_mib(s) for c in configs for s in c['stages'])
    if psutil.virtual_memory().available<(2*maxstage*max(workers)+256)*2**20: ap.error('Not enough available RAM; lower --max-workers or memory settings')
    assert len({c['name'] for c in configs})==len(configs)
    (out/'configs.json').write_text(json.dumps(configs,indent=2)); core.csvwrite(out/'calibration.csv',logs)
    seed=87211 if args.confirm_from else 87210; rng=random.Random(seed); raw=[]
    # Randomize within repetition to spread thermal/time effects across configurations.
    total=len(configs)*len(workers)*repeats; counter=0
    for r in range(repeats):
        plan=[(c,w) for c in configs for w in workers]; rng.shuffle(plan)
        for c,w in plan:
            counter+=1
            if counter==1 or counter%10==0 or counter==total: print(f'Batch {counter}/{total}',flush=True)
            child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker-json',json.dumps(c),'--workers',str(w),'--jobs',str(w*per),'--offset',str((200000 if args.confirm_from else 1000)+r*100)],capture_output=True,text=True)
            if child.returncode: raise RuntimeError(child.stderr or child.stdout)
            raw.append(dict(name=c['name'],repeat=r+1,**json.loads(child.stdout)))
            if counter%10==0: core.csvwrite(out/'raw_batches.csv',raw)
    core.csvwrite(out/'raw_batches.csv',raw)
    rows=summarize(configs,raw,workers,target,args.tolerance,args.min_gain); core.csvwrite(out/'summary.csv',rows)
    ranking=sorted([r for r in rows if r['workers']==max(workers)],key=lambda r:(not r['matched'],r['throughput_per_s'])); core.csvwrite(out/'ranking.csv',ranking); plots(out,rows,workers)
    import cryptography, importlib.metadata as md
    meta=dict(calibration_target_ms=target*1000,python=sys.version,platform=platform.platform(),processor=platform.processor(),logical_cpus=os.cpu_count(),openssl=ssl.OPENSSL_VERSION,cryptography=cryptography.__version__,argon2_cffi=md.version('argon2-cffi'),bcrypt=md.version('bcrypt') if not args.skip_bcrypt else None,workers=workers,repeats=repeats,jobs_per_worker=per,tolerance_pct=args.tolerance,min_gain_pct=args.min_gain,seed=seed,confirmation_from=str(args.confirm_from) if args.confirm_from else None,configurations=len(configs),synthetic_only=True)
    (out/'environment.json').write_text(json.dumps(meta,indent=2)); print(f'Finished: {out.resolve()} | candidates: {sum(r["candidate"] for r in ranking)}',flush=True)
    print('Candidate means CPU performance signal only; no security or novelty proof.')

if __name__=='__main__': main()
