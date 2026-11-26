"""Import Experiment 8 benchmark results; never runs GPU workloads."""
import csv, io, json, math, hashlib, statistics, zipfile
from pathlib import Path

def config_key(v,m,t,p): return f'{v}_m{m}_t{t}_p{p}'
def sha(data): return hashlib.sha256(data).hexdigest()
def finite(x):
    x=float(x)
    if not math.isfinite(x) or x<=0: raise ValueError('expected positive finite measurement')
    return x

def read_source(path):
    path=Path(path)
    if path.is_dir():
        return lambda n:(path/n).read_bytes(),lambda:None
    z=zipfile.ZipFile(path); matches=[n for n in z.namelist() if n.endswith('manifest.json') and n.split('/')[-1]=='manifest.json']
    if len(matches)!=1: z.close();raise ValueError('archive must contain exactly one manifest.json')
    prefix=matches[0][:-len('manifest.json')]
    return lambda n:z.read(prefix+n),z.close

def import_source(path,device,profile_id):
    read,close=read_source(path)
    try:
        mb=read('manifest.json'); gb=read('gpu_raw.csv'); eb=read('environment.json')
        m=json.loads(mb);env=json.loads(eb); n=int(m['rounds']); stage=m['stage']
        if n<1 or n>10000:raise ValueError('invalid round count')
        groups={}; configs={config_key(*c):tuple(c) for c in m['configs']}
        if len(configs)!=len(m['configs']):raise ValueError('duplicate configuration in manifest')
        for r in csv.DictReader(io.StringIO(gb.decode('utf-8-sig'))):
            k=r['config']; c=(r['variant'],int(r['memory_mib']),int(r['t']),int(r['p']))
            if configs.get(k)!=c:raise ValueError(f'configuration mismatch: {k}')
            if r['status']=='ok':groups.setdefault(k,[]).append(r)
        entries={}; rejected={}
        for k,c in configs.items():
            rs=groups.get(k,[])
            try:
                if len(rs)!=n or {int(r['round']) for r in rs}!=set(range(1,n+1)):raise ValueError('incomplete or duplicated rounds')
                verified=json.loads(read(f'synthetic_inputs/{k}.verified.json'))
                if verified['backend']!=m['backend'] or len(verified['target_sha256'])!=64:raise ValueError('verification record mismatch')
                speeds=[]
                for r in sorted(rs,key=lambda r:int(r['round'])):
                    if int(r['samples'])<2:raise ValueError('insufficient status samples')
                    # Verify actual device attribution in each corresponding run log.
                    log=read(f'gpu_logs/{k}_r{int(r["round"]):03d}.txt').decode('utf8',errors='replace')
                    names=set(); log_speeds=[]
                    for line in log.splitlines():
                        try:o=json.loads(line.strip())
                        except ValueError:continue
                        if isinstance(o,dict) and o.get('status')==3:
                            ds=o.get('devices',[])
                            if len(ds)!=1 or ds[0].get('device_type')!='GPU':raise ValueError('expected exactly one active GPU')
                            for d in ds:
                                if float(d.get('speed',0))>0:
                                    names.add(d.get('device_name',''));log_speeds.append(finite(d['speed']))
                    if not names or any(device.lower() not in name.lower() for name in names):raise ValueError(f'device mismatch: {names}')
                    if len(log_speeds[1:])!=int(r['samples']) or not math.isclose(statistics.median(log_speeds[1:]),finite(r['gpu_hps']),rel_tol=1e-9):raise ValueError('raw throughput does not match run log')
                    speeds.append(finite(r['gpu_hps']))
                entries[k]={'variant':c[0],'memory_mib':c[1],'t':c[2],'p':c[3],'hps_rounds':speeds,'stage':stage,'source_manifest_sha256':sha(mb),'verified_input':True}
            except (ValueError,KeyError,FileNotFoundError) as e:rejected[k]=str(e)
        if not entries:raise ValueError(f'no usable results; examples: {list(rejected.items())[:3]}')
        # Deliberately omit machine-specific paths and account names.
        meta={'stage':stage,'rounds':n,'backend':m['backend'],'gpu_seconds':m['gpu_seconds'],'hashcat_version':env['hashcat_version'],'hashcat_sha256':m['hashcat_sha256'],'benchmark_script_sha256':m['script_sha256'],'manifest_sha256':sha(mb),'gpu_raw_sha256':sha(gb),'created':env.get('created'),'platform':env.get('platform'),'entries':len(entries),'rejected':rejected}
        return {'schema_version':1,'profile_id':profile_id,'device':device,'argon2_version':19,'hash_bytes':32,'salt_bytes':16,'sources':[meta],'entries':entries}
    finally:close()

def merge_profiles(a,b):
    for key in ('schema_version','profile_id','device','argon2_version','hash_bytes','salt_bytes'):
        if a[key]!=b[key]:raise ValueError(f'incompatible profile {key}')
    # Same device/profile and software backend only; do not mix different implementations.
    for k in ('backend','hashcat_version','hashcat_sha256','benchmark_script_sha256','gpu_seconds'):
        if {s[k] for s in a['sources']+b['sources']}.__len__()!=1:raise ValueError(f'incompatible source {k}')
    out=dict(a);out['sources']=a['sources']+b['sources'];out['entries']=dict(a['entries'])
    for k,e in b['entries'].items():
        old=out['entries'].get(k)
        if old is None or (len(e['hps_rounds']),e['stage']=='confirm')>(len(old['hps_rounds']),old['stage']=='confirm'):out['entries'][k]=e
    return out

def validate(p):
    if (p['schema_version'],p['argon2_version'],p['hash_bytes'],p['salt_bytes'])!=(1,19,32,16):raise ValueError('unsupported profile schema or hash parameters')
    if not isinstance(p['profile_id'],str) or not p['profile_id'] or not p['entries']:raise ValueError('empty profile')
    for k,e in p['entries'].items():
        c=(e['variant'],e['memory_mib'],e['t'],e['p'])
        if c[0] not in ('id','i','d') or any(type(x)!=int or x<1 for x in c[1:]) or k!=config_key(*c) or c[1]*1024<8*c[3] or e['verified_input'] is not True:raise ValueError(f'invalid profile entry {k}')
        if not e['hps_rounds']:raise ValueError('empty measurements')
        for x in e['hps_rounds']:finite(x)
    return p

def load_profiles(paths):
    ps=[validate(json.loads(Path(p).read_text(encoding='utf8'))) for p in paths]
    if len({p['profile_id'] for p in ps})!=len(ps):raise ValueError('duplicate profile IDs; merge same-device data first')
    return ps

def candidates(ps):
    # Common coverage only: absence must not be interpreted as low attacker throughput.
    common=set.intersection(*(set(p['entries']) for p in ps)); result=[]
    for k in sorted(common):
        es=[p['entries'][k] for p in ps];e=es[0]
        if e['variant']!='id':continue
        details=[{'profile_id':p['profile_id'],'device':p['device'],'rounds':len(x['hps_rounds']),'median_hps':statistics.median(x['hps_rounds']),'max_observed_hps':max(x['hps_rounds']),'stage':x['stage']} for p,x in zip(ps,es)]
        result.append({'config':k,'memory_mib':e['memory_mib'],'t':e['t'],'p':e['p'],'gpu_median_worst':max(x['median_hps'] for x in details),'gpu_max_observed':max(x['max_observed_hps'] for x in details),'gpu_min_rounds':min(x['rounds'] for x in details),'gpu_details':details})
    return result
