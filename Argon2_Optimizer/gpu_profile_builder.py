"""Optional synthetic Argon2id GPU profile collection, with durable checkpoints.
No user passwords or hash inputs are accepted. Uses a compatible Hashcat 8.x engine (bundled by the Windows release).
"""
import argparse, hashlib, json, math, os, platform, random, re, statistics, subprocess, sys, time, uuid
from pathlib import Path
import psutil
from argon2.low_level import hash_secret, Type
from profile_data import config_key, validate

SECRET=b'EXP8-synthetic-public!'
REFERENCE='id_m64_t3_p4'
ROUNDS=2
SECONDS=18

def atomic_json(p, obj):
    p=Path(p); tmp=p.with_suffix(p.suffix+'.tmp')
    with tmp.open('w',encoding='utf8') as f:
        json.dump(obj,f,indent=2,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,p)

def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def grid():
    # Match the bundled database exactly, including the non-grid tuned Argon2id control.
    cs=[('id',m,t,p) for m in (16,32,64,128,256,512,1024,2048) for t in range(1,7) for p in (1,2,4,8)]
    return sorted(cs+[('id',135,4,4)])

def invoke(exe,args,timeout):
    return subprocess.run([str(exe),*map(str,args)],cwd=exe.parent,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def available_backends(system=None):
    system=system or platform.system()
    if system=='Darwin': return ('metal','opencl')
    if system in ('Windows','Linux'): return ('cuda','hip','opencl')
    return ('opencl',)

def backend_flags(backend):
    system=platform.system()
    if backend not in available_backends(system): raise ValueError(f'{backend} is not supported by this collector on {system}.')
    # Hashcat exposes the Metal-ignore flag only in Apple builds.
    apis=['hip','cuda','opencl']+(['metal'] if system=='Darwin' else [])
    return [f'--backend-ignore-{api}' for api in apis if api!=backend]+(['-D','2'] if backend=='opencl' else [])

def query_device_info(exe,backend):
    result=invoke(exe,['-I',*backend_flags(backend)],60)
    if result.returncode!=0:
        raise ValueError(f'Hashcat device query failed (exit {result.returncode}):\n{result.stdout.strip()}')
    return result.stdout

def device_info(text,backend,device_id):
    section=None; found=[]; current=None
    for line in text.splitlines():
        s=line.strip()
        if s in ('CUDA Info:','OpenCL Info:','HIP Info:','Metal Info:'):
            section=s.split()[0].lower(); current=None
        # Platform metadata is not device metadata. End the current device
        # record before parsing a new platform (e.g. NVIDIA followed by Intel).
        if re.match(r'(?:OpenCL|CUDA|HIP|Metal) Platform ID #\d+',s,re.I):
            current=None
            continue
        match=re.match(r'Backend Device ID #(\d+)',s)
        if match:
            current={} if section==backend and int(match.group(1))==device_id else None
            if current is not None: found.append(current)
        elif current is not None:
            m=re.match(r'([\w.()]+)\s*:\s*(.*)',s)
            if m:
                key=m.group(1).rstrip('.')
                if key in current: raise ValueError(f'Duplicate device metadata field {key}; refusing ambiguous device identity.')
                current[key]=m.group(2)
    if len(found)!=1 or not found[0].get('Name'): raise ValueError('Selected GPU ID not found for this backend. Use Hashcat -I to find its backend device ID.')
    d=found[0]
    if backend=='opencl' and d.get('Type','').upper()!='GPU': raise ValueError('Selected OpenCL device is not a GPU.')
    result={k:v for k,v in d.items() if k in ('Name','Type','Memory.Total','Processor(s)','PCI.Addr.BDF','PCI.Addr.BDFe','Driver.Version','Version','Vendor')}
    version=re.search(r'CUDA\.Version\.*:\s*(.+)',text)
    if version and backend=='cuda':result['CUDA.Version']=version.group(1).strip()
    return result

def parse_status(text,name,device_id):
    samples=[]; terminal=None
    for line in text.splitlines():
        try: o=json.loads(line.strip())
        except ValueError: continue
        if not isinstance(o,dict) or 'status' not in o: continue
        terminal=o['status']
        if terminal!=3: continue
        ds=o.get('devices',[])
        if len(ds)!=1 or ds[0].get('device_type')!='GPU' or ds[0].get('device_id')!=device_id or ds[0].get('device_name')!=name:
            raise ValueError('GPU status device does not match selected GPU; refusing measurement.')
        d=ds[0]; h=d.get('speed',0)
        if isinstance(h,(float,int)) and math.isfinite(h) and h>0: samples.append(d)
    return samples,terminal

def setup_inputs(out):
    p=out/'synthetic_inputs';p.mkdir(exist_ok=True)
    (p/'known.txt').write_bytes(SECRET+b'\n'); w=p/'workload.txt'
    if not w.exists():
        tmp=w.with_suffix('.tmp')
        with tmp.open('wb') as f:
            for i in range(1_000_000): f.write(f'EXP8-synthetic-{i:07d}\n'.encode())
        tmp.replace(w)
    return p

def measure(c,r,exe,out,inputs,manifest):
    k=config_key(*c); _,m,t,p=c; name=manifest['device']['Name']; device_id=manifest['device_id']; backend=manifest['backend']; logs=out/'gpu_logs'; logs.mkdir(exist_ok=True)
    flags=['-m','34000','-a','0','-d',str(device_id),'--potfile-disable','--restore-disable','--logfile-disable','--hwmon-temp-abort','85']
    flags+=backend_flags(backend)
    target=inputs/(k+'.phc'); known=inputs/(k+'.verified.json'); answer=inputs/(k+'.answer'); start=time.perf_counter()
    def fail(msg,**kw): return dict(status='failed',error=msg,elapsed_s=time.perf_counter()-start,**kw)
    if not known.exists():
        if m>psutil.virtual_memory().available/2**20*.60: return fail('Insufficient available RAM for synthetic input generation.')
        salt=hashlib.sha256(f'exp8-public-salt/{k}/0'.encode()).digest()[:16]
        target.write_bytes(hash_secret(SECRET,salt,t,m*1024,p,32,Type.ID,version=19)+b'\n'); answer.unlink(missing_ok=True)
        result=invoke(exe,flags+['--outfile',answer,'--outfile-format','2',target,inputs/'known.txt'],180)
        (logs/(k+'_verify.txt')).write_text(result.stdout,encoding='utf8')
        if thermal(result.stdout): return fail('GPU temperature watchdog reported an actual thermal abort.',thermal=True)
        if result.returncode!=0 or not answer.exists() or answer.read_bytes().strip()!=SECRET:
            return fail(f'GPU known-input verification failed (exit {result.returncode}); inspect {k}_verify.txt.',reason='verification')
        atomic_json(known,{'target_sha256':digest(target),'backend':backend,'device_id':device_id,'device':name}); answer.unlink(missing_ok=True)
    elif read(known)!={'target_sha256':digest(target),'backend':backend,'device_id':device_id,'device':name}:
        raise ValueError('Cached verification does not match device/target.')
    result=invoke(exe,flags+['-w','3','--status','--status-json','--status-timer','2','--runtime',str(SECONDS),target,inputs/'workload.txt'],SECONDS+180)
    (logs/f'{k}_r{r:03d}.txt').write_text(result.stdout,encoding='utf8')
    if thermal(result.stdout): return fail('GPU temperature watchdog reported an actual thermal abort; allow hardware to cool before resuming.',thermal=True)
    temps=temperature_samples(result.stdout,name,device_id)
    if temps and max(temps)>=85: return fail(f'GPU reported {max(temps):g}°C, at or above the 85°C safety threshold.',thermal=True)
    samples,terminal=parse_status(result.stdout,name,device_id)
    if terminal not in (5,11) or result.returncode not in (0,1,4) or len(samples)<3:
        return fail(f'No valid sustained benchmark (status {terminal}, exit {result.returncode}, samples {len(samples)}). Inspect {k}_r{r:03d}.txt for GPU/runtime errors.',reason='benchmark')
    samples=samples[1:]
    if not temps: return fail('GPU temperature telemetry unavailable; cannot verify safe temperatures. This is not an overheating report. Check driver/backend monitoring support.',reason='telemetry')
    return dict(status='ok',gpu_hps=statistics.median(d['speed'] for d in samples),samples=len(samples),gpu_temp_max_c=max(temps),elapsed_s=time.perf_counter()-start)

def thermal(text):
    # Match actual v8 watchdog events, NOT its normal "Temperature abort trigger set to 85c" banner.
    clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
    return any(re.search(r'\bTemperature limit on (?:GPU #\d+|Bridge unit #\d+|the candidate generator) reached, aborting\b',line,re.I) for line in clean.splitlines())

def temperature_samples(text,name,device_id):
    # Safety checks include startup and terminal samples, even if speed is zero.
    temps=[]
    for line in text.splitlines():
        try: o=json.loads(line.strip())
        except ValueError: continue
        if not isinstance(o,dict) or 'status' not in o: continue
        for d in o.get('devices',[]):
            if d.get('device_id')!=device_id or d.get('device_name')!=name or d.get('device_type')!='GPU': continue
            v=d.get('temp')
            if type(v) in (int,float) and math.isfinite(v) and v>=0: temps.append(v)
    return temps

def checkpoint_count(out):
    p=Path(out)/'checkpoints'; return len(list(p.glob('*.json'))) if p.exists() else 0

def ordered_jobs(cs):
    for r in range(1,ROUNDS+1):
        order=list(cs);random.Random(10808+r).shuffle(order)
        if r==1:
            ref=next(c for c in order if config_key(*c)==REFERENCE);order.remove(ref);order.insert(0,ref)
        for c in order: yield c,r

def export(out,manifest):
    cs=manifest['configs']; entries={};rejected={}
    for c in cs:
        k=config_key(*c); paths=[out/'checkpoints'/f'{k}_r{r:03d}.json' for r in range(1,ROUNDS+1)]
        if not all(p.exists() for p in paths): continue
        rows=[read(p) for p in paths]
        if not all(x['status']=='ok' for x in rows): rejected[k]=[x.get('error','') for x in rows if x['status']!='ok']; continue
        entries[k]=dict(variant=c[0],memory_mib=c[1],t=c[2],p=c[3],hps_rounds=[x['gpu_hps'] for x in rows],stage='profile',source_manifest_sha256=digest(out/'manifest.json'),verified_input=True)
    if not entries: raise ValueError('No complete verified configurations; no profile exported.')
    source={k:manifest[k] for k in ('backend','hashcat_version','hashcat_sha256','created')}; source.update(stage='profile',rounds=ROUNDS,gpu_seconds=SECONDS,entries=len(entries),rejected=rejected,manifest_sha256=digest(out/'manifest.json'),protocol='exp8-compatible-synthetic-v1',device_details=manifest['device'],platform=manifest['platform'])
    p=dict(schema_version=1,profile_id=manifest['profile_id'],device=manifest['device']['Name'],argon2_version=19,hash_bytes=32,salt_bytes=16,sources=[source],entries=entries)
    validate(p); atomic_json(out/'gpu_profile.json',p); print(f'Exported {len(entries)}/{len(cs)} complete configurations to gpu_profile.json; {len(rejected)} rejected.',flush=True)
    return p

def run(out,exe,backend,device_id):
    out=Path(out).resolve(); exe=Path(exe).resolve(); out.mkdir(parents=True,exist_ok=True)
    if not exe.is_file(): raise ValueError('Hashcat executable not found.')
    if not 1<=device_id<=128: raise ValueError('Invalid device ID.')
    # Prevent concurrent writers; reclaim only a demonstrably stale lock.
    lock=out/'active.lock'; proc=psutil.Process(); owner={'pid':proc.pid,'created':proc.create_time()}
    try:
        with lock.open('x',encoding='utf8') as f: json.dump(owner,f)
    except FileExistsError:
        old=read(lock)
        try: alive=abs(psutil.Process(old['pid']).create_time()-old['created'])<.01
        except psutil.NoSuchProcess: alive=False
        if alive: raise ValueError('Another profile collector is active in this folder.')
        lock.unlink()
        with lock.open('x',encoding='utf8') as f: json.dump(owner,f)
    try:
        version=invoke(exe,['--version'],30).stdout.strip()
        if not re.search(r'\bv?8\.\d+\.\d+\b',version): raise ValueError('Hashcat 8.x is required (tested protocol: 8.0.0).')
        info=query_device_info(exe,backend); device=device_info(info,backend,device_id)
        cs=[list(c) for c in grid()]; identity=dict(configs=cs,rounds=ROUNDS,gpu_seconds=SECONDS,backend=backend,device_id=device_id,device=device,hashcat_sha256=digest(exe),hashcat_version=version,platform=platform.platform(),machine_fingerprint=hashlib.sha256(platform.node().encode()).hexdigest(),protocol='exp8-compatible-synthetic-v1')
        mf=out/'manifest.json'
        if mf.exists():
            manifest=read(mf)
            if any(manifest.get(k)!=v for k,v in identity.items()): raise ValueError('Hardware, Hashcat, backend, or protocol changed. Start a new profile rather than mixing results.')
        else:
            manifest=dict(identity,profile_id='gpu_'+uuid.uuid4().hex,created=time.strftime('%Y-%m-%dT%H:%M:%S%z'),hashcat_path=str(exe));atomic_json(mf,manifest)
        (out/'hashcat_info.txt').write_text(info,encoding='utf8'); inputs=setup_inputs(out); cp=out/'checkpoints';cp.mkdir(exist_ok=True)
        total=len(cs)*ROUNDS; done=checkpoint_count(out); print(f'{device["Name"]} | {done}/{total} saved GPU measurements.\nPause takes effect after the current measurement.',flush=True)
        start=time.monotonic(); completed=0
        for c,r in ordered_jobs(cs):
            if (out/'pause.request').exists(): print('Paused. All committed measurements preserved.',flush=True); return 10
            k=config_key(*c); path=cp/f'{k}_r{r:03d}.json'
            if path.exists(): continue
            try: result=measure(c,r,exe,out,inputs,manifest)
            except subprocess.TimeoutExpired as e:
                logdir=out/'gpu_logs';logdir.mkdir(exist_ok=True)
                partial=e.stdout or ''
                if isinstance(partial,bytes): partial=partial.decode('utf8',errors='replace')
                (logdir/f'{k}_r{r:03d}_timeout.txt').write_text(partial,encoding='utf8')
                result=dict(status='failed',error='Hashcat timed out (possible driver stall or slow initialization); not a thermal abort unless the watchdog reported one. Inspect the timeout log before retrying.',reason='timeout',thermal=thermal(partial))
            if result.get('thermal') or result.get('reason') in ('telemetry','timeout') or (k==REFERENCE and r==1 and result['status']!='ok'):
                rc=11 if result.get('thermal') else {'telemetry':12,'timeout':13}.get(result.get('reason'),14)
                print(f'Paused: {result["error"]} No measurement committed. Check logs and resume after resolving.',flush=True); return rc
            atomic_json(path,dict(result,config=k,round=r));done+=1;completed+=1
            remaining=(time.monotonic()-start)/completed*(total-done)/60
            print(f'{done}/{total} {k} round {r}: {result["status"]} {result.get("gpu_hps",result.get("error",""))} | approx {remaining:.0f} min remaining (current pace)',flush=True)
        export(out,manifest);return 0
    finally: lock.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);p.add_argument('--hashcat',required=True,type=Path);p.add_argument('--backend',choices=available_backends(),default=available_backends()[0]);p.add_argument('--device-id',type=int,default=1);a=p.parse_args()
    return run(a.out,a.hashcat,a.backend,a.device_id)

if __name__=='__main__': sys.exit(main())
