"""Interactive front end for the offline optimizer."""
from pathlib import Path
import sys, subprocess, datetime
ROOT=Path(__file__).resolve().parent

def ask(label,default=None):
    d=f' [{default}]' if default is not None else ' [optional, Enter to skip]'
    return input(label+d+': ').strip() or (str(default) if default is not None else '')

def main():
    print('\nARGON2ID PARAMETER OPTIMIZER\nLocal CPU tests + reusable GPU benchmark profiles.\nNo GPU, CUDA or actual passwords required.\n')
    vals=[('--latency-ms','Maximum median authentication latency (ms)',100),('--max-memory','Maximum Argon2 memory per request (MiB)',256),('--workers','Simultaneous authentication workers',4),('--max-cpu-ms','Maximum CPU milliseconds per authentication',None),('--max-p95-ms','Maximum concurrent p95 execution latency (ms)',None),('--max-rss-mib','Maximum sampled process RAM (MiB)',None),('--min-throughput','Minimum concurrent authentications per second',None)]
    args=[]
    for flag,label,default in vals:
        v=ask(label,default)
        if v:args.extend([flag,v])
    extra=ask('Additional GPU profile JSON paths (separate with semicolons)')
    if extra:
        args+=['--profile',str(ROOT/'profiles/rtx4090.json')]
        for path in extra.split(';'):
            if path.strip():args+=['--profile',path.strip().strip('"')]
    out=ROOT/'results'/('run_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    print('\nStarting local benchmark. The default policy requires Argon2id with at least 64 MiB and 3 passes, or the RFC 2 GiB configuration.\n')
    rc=subprocess.call([sys.executable,str(ROOT/'optimizer.py'),'optimize','--out',str(out),*args]);print('\nOutput:',out)
    return rc
if __name__=='__main__':
    try:sys.exit(main())
    except (KeyboardInterrupt,EOFError):sys.exit(130)
