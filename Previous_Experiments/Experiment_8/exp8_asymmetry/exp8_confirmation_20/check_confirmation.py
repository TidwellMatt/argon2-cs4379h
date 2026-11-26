"""Offline confirmation analysis of Experiment 8, no hashing or GPU access."""
import argparse, csv, json, math, statistics
from pathlib import Path

def sign_p(ratios):
    # Exact, conservative one-sided test: ties count as non-improvements.
    n=len(ratios); k=sum(x<1 for x in ratios)
    return sum(math.comb(n,i) for i in range(k,n+1))/2**n

def load_phase(path,n,keys):
    with path.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    seen={}
    for r in rows:
        k=(r['config'],int(r['round']))
        if k in seen:raise ValueError(f'Duplicate {path.name}: {k}')
        if k[0] not in keys or not 1<=k[1]<=n:raise ValueError(f'Unexpected row: {k}')
        seen[k]=r
    expected={(k,r) for k in keys for r in range(1,n+1)}
    if set(seen)!=expected or any(r['status']!='ok' for r in seen.values()):
        raise ValueError(f'{path.name}: incomplete or failed measurements; no final inference')
    return seen

def ratios(data,c,b,n,metric,reverse=False):
    a=[float(data[c,i][metric]) for i in range(1,n+1)]
    z=[float(data[b,i][metric]) for i in range(1,n+1)]
    if not all(math.isfinite(x) and x>0 for x in a+z):raise ValueError(f'Invalid {metric}')
    return [v/u if reverse else u/v for u,v in zip(a,z)]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('out',type=Path);a=p.parse_args();out=a.out
    sel=json.loads(Path(__file__).with_name('confirmation_selection.json').read_text()); m=json.loads((out/'manifest.json').read_text());n=sel['rounds_planned']
    assert m['stage']=='confirm' and m['rounds']==n and m['configs']==sel['configs'], 'Unexpected design'
    assert (m['workers'],m['cpu_inner'],m['gpu_seconds'],m['backend'])==(4,3,18,'cuda'), 'Unexpected benchmark settings'
    keys={'%s_m%s_t%s_p%s'%tuple(c) for c in sel['configs']};cpu=load_phase(out/'cpu_raw.csv',n,keys);gpu=load_phase(out/'gpu_raw.csv',n,keys)
    results=[]
    for i,pair in enumerate([sel['primary']]+sel['secondary']):
        c,b=pair['candidate'],pair['control']; L=ratios(cpu,c,b,n,'latency_ms');G=ratios(gpu,c,b,n,'gpu_hps'); pl,pg=sign_p(L),sign_p(G)
        r=dict(role='primary' if i==0 else 'secondary',candidate=c,control=b,rounds=n,latency_paired_median_ratio=statistics.median(L),gpu_paired_median_ratio=statistics.median(G),latency_improved_rounds=sum(x<1 for x in L),gpu_improved_rounds=sum(x<1 for x in G),latency_sign_p=pl,gpu_sign_p=pg,joint_p=max(pl,pg),adjusted_p=max(pl,pg))
        for field in ('cpu_ms','rss_peak_mib','concurrent_p95_ms','concurrent_hps'):
            rr=ratios(cpu,c,b,n,field,field=='concurrent_hps');r[field+'_oriented_paired_median_ratio']=statistics.median(rr)
        r['memory_ratio']=int(cpu[c,1]['memory_mib'])/int(cpu[b,1]['memory_mib']);results.append(r)
    # Primary is prespecified; secondary hypotheses adjusted within their own family.
    prev=0.; order=sorted(results[1:],key=lambda r:r['joint_p']); k=len(order)
    for i,r in enumerate(order):prev=max(prev,min(1.,(k-i)*r['joint_p']));r['adjusted_p']=prev
    for r in results:r['joint_improvement_supported']=r['adjusted_p']<.05 and r['latency_paired_median_ratio']<1 and r['gpu_paired_median_ratio']<1
    with (out/'focused_confirmation.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    print('Saved focused_confirmation.csv. Primary:',results[0]);print('Sign tests assume independent round pairs. Resource ratios are descriptive, not proof of non-inferiority. GPU throughput is hardware/backend-specific.')
if __name__=='__main__':main()
