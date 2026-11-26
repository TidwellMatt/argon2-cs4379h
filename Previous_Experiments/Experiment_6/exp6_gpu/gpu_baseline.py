"""Optional GPU baseline: run Hashcat's built-in synthetic benchmark only.
No hashes, password lists, recovery mode, or user-supplied benchmark arguments.
The custom cascades in 5D are not implemented in this GPU backend.
"""
import argparse,csv,json,os,re,shutil,subprocess,threading,time
from pathlib import Path

def capture(cmd,cwd=None,timeout=30):
    try:
        x=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,errors='replace',timeout=timeout)
        return x.returncode,x.stdout+x.stderr
    except (OSError,subprocess.TimeoutExpired) as e: return -1,str(e)

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--hashcat',type=Path); ap.add_argument('--out',type=Path,default=Path('results/gpu_baseline')); a=ap.parse_args()
    binary=str(a.hashcat.resolve()) if a.hashcat else shutil.which('hashcat') or shutil.which('hashcat.exe')
    if not binary or not Path(binary).is_file(): ap.error('Extract official Hashcat 7+ and provide --hashcat with its executable path.')
    out=a.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()): ap.error('Choose an empty --out directory')
    cwd=str(Path(binary).parent); version_rc,version=capture([binary,'--version'],cwd); rc,info=capture([binary,'-I'],cwd,120)
    (out/'devices.txt').write_text(info,encoding='utf-8'); (out/'version.txt').write_text(version,encoding='utf-8')
    if rc or version_rc: raise SystemExit('Device/version discovery failed; inspect devices.txt and version.txt.')
    smi=shutil.which('nvidia-smi'); stop=threading.Event(); samples=[]
    query=['index','name','utilization.gpu','utilization.memory','memory.used','memory.total','temperature.gpu','power.draw']
    def monitor():
        while not stop.is_set():
            rc,txt=capture([smi,'--query-gpu='+','.join(query),'--format=csv,noheader,nounits'],timeout=5)
            if rc==0:
                for row in csv.reader(txt.splitlines()):
                    if len(row)==len(query): samples.append([time.time()]+[x.strip() for x in row])
            stop.wait(.8)
    cmd=[binary,'-b','-m','34000','-D','2']
    (out/'command.json').write_text(json.dumps(cmd,indent=2),encoding='utf-8')
    t=threading.Thread(target=monitor,daemon=True) if smi else None
    if t: t.start()
    try:
        with (out/'benchmark.txt').open('w',encoding='utf-8') as f:
            p=subprocess.Popen(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
            try:
                for line in p.stdout: print(line,end='',flush=True); f.write(line); f.flush()
                rc=p.wait()
            except KeyboardInterrupt:
                p.terminate(); p.wait(); raise
    finally:
        stop.set()
        if t: t.join(timeout=6)
        with (out/'gpu_telemetry.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(['unix_time']+query); w.writerows(samples)
    # Keep raw speed lines; do not treat unknown CPU or mixed-device outputs as GPU measurements.
    txt=(out/'benchmark.txt').read_text(encoding='utf-8'); speeds=[x.strip() for x in txt.splitlines() if re.search(r'Speed\.#',x)]
    (out/'speed_lines.txt').write_text('\n'.join(speeds),encoding='utf-8')
    (out/'status.json').write_text(json.dumps(dict(returncode=rc,speed_lines=len(speeds),telemetry_samples=len(samples),mode=34000,scope='built-in standard Argon2 benchmark only; verify GPU identity and printed parameters in raw output',hybrid_gpu_measured=False),indent=2),encoding='utf-8')
    if rc or not speeds: raise SystemExit('GPU benchmark did not produce a usable speed. See benchmark.txt; no GPU result claimed.')
    print('Saved',out,'; inspect GPU device and parameters before citing results.')
if __name__=='__main__': main()
