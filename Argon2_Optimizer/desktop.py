"""Windows desktop front end for the Argon2id optimizer."""
import contextlib
import datetime
import json
import math
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from optimizer import MODES, TARGET_MODES
import gpu_profile_builder as gpu
import bundled_hashcat as engine
from profile_data import load_profiles

ROOT = Path(__file__).resolve().parent
FROZEN = getattr(sys, 'frozen', False)

MODE_NAMES = {"defense":"maximum_defense","balanced":"balanced","responsive":"responsiveness","efficient":"resource_efficiency","comprehensive":"comprehensive"}

def run_name(mode, now=None):
    return "argon2_run_"+MODE_NAMES[mode]+"_"+(now or datetime.datetime.now()).strftime("%Y%m%d_%H%M%S_%f")

def settings_file():
    base=Path(os.environ.get("LOCALAPPDATA", str(Path.home()/".config")))
    return base/"Argon2Optimizer"/"settings.json"

def read_parent():
    try:
        p=Path(json.loads(settings_file().read_text(encoding="utf8"))["results_parent"])
        return p if p.is_dir() else None
    except (OSError,ValueError,KeyError,TypeError): return None

def save_parent(p):
    f=settings_file(); f.parent.mkdir(parents=True,exist_ok=True); gpu.atomic_json(f,{"results_parent":str(p)})

def worker(gpu_job=False):
    # A windowed Windows executable has no console streams. Explicitly open a log.
    log = Path(sys.argv[2]); args = sys.argv[3:]
    with log.open('a' if gpu_job else 'w', encoding='utf8', buffering=1) as f, contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        try:
            if gpu_job:
                # PyInstaller alters the DLL search path; reset it only in the external GPU worker.
                if FROZEN and os.name=='nt':
                    import ctypes
                    ctypes.windll.kernel32.SetDllDirectoryW(None)
                sys.argv=['gpu_profile_builder']+args
                return gpu.main()
            import optimizer
            sys.argv = ['optimizer'] + args
            optimizer.main()
            return 0
        except SystemExit as e:
            return int(e.code or 0) if isinstance(e.code, (int, type(None))) else 1
        except Exception:
            traceback.print_exc(); return 1

def make_args(values, profiles, out, mode='defense', target=''):
    if mode not in MODES: raise ValueError('Unknown optimization mode.')
    args = ['optimize','--out',str(out),'--mode',mode]
    if mode in TARGET_MODES:
        try: cap=float(target)
        except ValueError: raise ValueError('Enter a maximum GPU H/s target.') from None
        if not math.isfinite(cap) or cap<=0: raise ValueError('Maximum GPU H/s must be positive and finite.')
        args += ['--max-gpu-hps',str(cap)]
    for key, (flag, typ, optional) in SPEC.items():
        text = values[key].strip()
        if not text and optional: continue
        try: v = typ(text)
        except ValueError: raise ValueError(f'{key}: enter a valid number.') from None
        if not math.isfinite(v) or v <= 0: raise ValueError(f'{key}: enter a positive number.')
        if key=='Concurrent requests' and not 1<=v<=32: raise ValueError('Concurrent requests must be 1–32.')
        if key=='Memory per request (MiB)' and not 64<=v<=2048: raise ValueError('Memory limit must be 64–2048 MiB.')
        if key=='Confirmation rounds' and not 3<=v<=100: raise ValueError('Confirmation rounds must be 3–100.')
        args += [flag, str(v)]
    if profiles:
        for p in [ROOT/'profiles'/'rtx4090.json', *profiles]: args += ['--profile',str(p)]
    return args

SPEC = {
    'Maximum login latency (ms)': ('--latency-ms',float,False),
    'Memory per request (MiB)': ('--max-memory',int,False),
    'Concurrent requests': ('--workers',int,False),
    'Confirmation rounds': ('--confirm-rounds',int,False),
    'Maximum CPU time (ms)': ('--max-cpu-ms',float,True),
    'Maximum concurrent p95 (ms)': ('--max-p95-ms',float,True),
    'Maximum process RAM (MiB)': ('--max-rss-mib',float,True),
    'Minimum authentications/sec': ('--min-throughput',float,True),
}
DEFAULTS = ['100','256','4','5','','','','']

class Desktop:
    def __init__(self, root):
        self.root=root; self.proc=None; self.log=None; self.out=None; self.profiles=[]; self.offset=0; self.parent=read_parent(); self.job_kind=None; self.profile_job=None; self.closing=False
        try:
            saved=Path(json.loads(settings_file().with_name('last_gpu_job.json').read_text(encoding='utf8'))['path'])
            if saved.is_dir(): self.profile_job=saved
        except (OSError,ValueError,KeyError,TypeError):pass
        root.title('Argon2id Parameter Optimizer'); root.geometry(f'1000x{min(900,max(700,root.winfo_screenheight()-80))}'); root.minsize(820,700)
        self.style=style=ttk.Style(root)
        style.theme_use('clam')
        style.configure('Heading.TLabel',font=('Segoe UI',19,'bold')); style.configure('Sub.TLabel',font=('Segoe UI',10)); style.configure('Result.TLabel',font=('Segoe UI',11,'bold'))
        outer=ttk.Frame(root,padding=14); outer.pack(fill='both',expand=True); outer.columnconfigure(0,weight=1); outer.rowconfigure(8,weight=1)
        head=ttk.Frame(outer); head.grid(row=0,column=0,sticky='ew')
        ttk.Label(head,text='Argon2id Parameter Optimizer',style='Heading.TLabel').pack(side='left')
        self.dark=tk.BooleanVar(value=True); ttk.Checkbutton(head,text='Dark mode',variable=self.dark,command=self.apply_theme).pack(side='right')
        ttk.Label(outer,text='Local CPU tests + stored GPU profiles  •  No CUDA or GPU required',style='Sub.TLabel').grid(row=1,column=0,sticky='w',pady=(3,12))
        self.tabs=ttk.Notebook(outer); self.tabs.grid(row=2,column=0,sticky='ew',pady=(0,10))
        self.tab_modes=list(MODES); self.targets={}; self.target_entries=[]
        labels=['Maximum defense','Balanced','Responsiveness','Resource efficiency','Comprehensive']
        for mode,label in zip(self.tab_modes,labels):
            tab=ttk.Frame(self.tabs,padding=8); self.tabs.add(tab,text=label)
            ttk.Label(tab,text=MODES[mode][1],wraplength=850).pack(anchor='w')
            if mode in TARGET_MODES:
                line=ttk.Frame(tab); line.pack(anchor='w',pady=(6,0)); ttk.Label(line,text='Maximum stored GPU H/s (required):').pack(side='left',padx=(0,8))
                var=tk.StringVar(value='1000'); self.targets[mode]=var; e=ttk.Entry(line,textvariable=var,width=12); e.pack(side='left'); self.target_entries.append(e)
            else:
                ttk.Label(tab,text='Fast guided search.' if mode=='defense' else 'Full CPU screening and confirmation of passing candidates; may take longer.',style='Sub.TLabel').pack(anchor='w',pady=(6,0))
        settings=ttk.LabelFrame(outer,text='Authentication constraints (shared across modes)',padding=10); settings.grid(row=3,column=0,sticky='ew'); settings.columnconfigure(1,weight=1); settings.columnconfigure(3,weight=1)
        self.vars={}; self.inputs=[]
        for i,(key,default) in enumerate(zip(SPEC,DEFAULTS)):
            r=i%4; col=(i//4)*2; ttk.Label(settings,text=key).grid(row=r,column=col,sticky='w',padx=(0,8),pady=4)
            v=tk.StringVar(value=default); e=ttk.Entry(settings,textvariable=v,width=12); e.grid(row=r,column=col+1,sticky='ew',padx=(0,14),pady=4); self.vars[key]=v; self.inputs.append(e)
        ttk.Label(settings,text='Blank optional limits are ignored. Default policy: Argon2id, ≥64 MiB, ≥3 passes (RFC high-memory exception).',wraplength=740).grid(row=4,column=0,columnspan=4,sticky='w',pady=(7,0))
        prof=ttk.LabelFrame(outer,text='Attacker hardware profiles',padding=10); prof.grid(row=4,column=0,sticky='ew',pady=10); prof.columnconfigure(0,weight=1)
        self.profiletext=tk.StringVar(value='Bundled NVIDIA RTX 4090 profile (always included)'); ttk.Label(prof,textvariable=self.profiletext,wraplength=570).grid(row=0,column=0,sticky='w')
        self.add=ttk.Button(prof,text='Add JSON profiles…',command=self.add_profiles); self.add.grid(row=0,column=1,padx=5); self.clear=ttk.Button(prof,text='Clear extras',command=self.clear_profiles); self.clear.grid(row=0,column=2)
        self.generate=ttk.Button(prof,text='Generate GPU profile…',command=self.new_profile); self.generate.grid(row=1,column=1,padx=5,pady=(6,0)); self.resume=ttk.Button(prof,text='Resume GPU profile…',command=self.resume_profile); self.resume.grid(row=1,column=2,pady=(6,0))
        ttk.Label(prof,text='Optional: build a reusable profile from one local GPU (benchmark engine bundled in release).',wraplength=570).grid(row=1,column=0,sticky='w',pady=(6,0))
        dest=ttk.Frame(outer); dest.grid(row=5,column=0,sticky='ew',pady=(0,8)); dest.columnconfigure(0,weight=1)
        self.parenttext=tk.StringVar(value=str(self.parent) if self.parent else 'Choose a results folder once for all modes.'); ttk.Label(dest,textvariable=self.parenttext,wraplength=740).grid(row=0,column=0,sticky='w'); self.choose=ttk.Button(dest,text='Change results folder…',command=self.choose_parent); self.choose.grid(row=0,column=1,sticky='e')
        row=ttk.Frame(outer); row.grid(row=6,column=0,sticky='ew'); self.start=ttk.Button(row,text='Start optimization',command=self.run); self.start.pack(side='left'); self.cancel=ttk.Button(row,text='Stop',command=self.stop,state='disabled'); self.cancel.pack(side='left',padx=6); self.openbtn=ttk.Button(row,text='Open results folder',command=self.open_folder,state='disabled'); self.openbtn.pack(side='right'); self.pause=ttk.Button(row,text='Pause GPU collection',command=self.pause_profile,state='disabled'); self.pause.pack(side='left',padx=6)
        self.status=tk.StringVar(value='Ready.'); ttk.Label(outer,textvariable=self.status,style='Result.TLabel',wraplength=760).grid(row=7,column=0,sticky='w',pady=10)
        logframe=ttk.LabelFrame(outer,text='Progress and results',padding=5); logframe.grid(row=8,column=0,sticky='nsew'); logframe.columnconfigure(0,weight=1); logframe.rowconfigure(0,weight=1)
        self.text=tk.Text(logframe,wrap='word',height=10,font=('Consolas',10),state='disabled'); self.text.grid(row=0,column=0,sticky='nsew'); sb=ttk.Scrollbar(logframe,command=self.text.yview); sb.grid(row=0,column=1,sticky='ns'); self.text.configure(yscrollcommand=sb.set)
        ttk.Label(outer,text='Recommendations are limited to measured profiles and tested configurations; not a universal security guarantee.',wraplength=760).grid(row=9,column=0,sticky='w',pady=(8,0)); root.protocol('WM_DELETE_WINDOW',self.close); self.apply_theme()
    def apply_theme(self):
        dark=self.dark.get(); bg='#17212d' if dark else '#f3f5f8'; panel='#243142' if dark else '#ffffff'; fg='#e8eef5' if dark else '#182433'; muted='#b2c0d0' if dark else '#526175'; accent='#315f93' if dark else '#cfe3fa'; border='#435369' if dark else '#bac6d4'; disabled='#748194' if dark else '#a0a9b5'
        st=self.style; self.root.configure(bg=bg)
        st.configure('.',background=bg,foreground=fg,fieldbackground=panel,bordercolor=border,lightcolor=border,darkcolor=border,focuscolor=accent)
        st.configure('TFrame',background=bg); st.configure('TLabel',background=bg,foreground=fg); st.configure('Sub.TLabel',foreground=muted)
        st.configure('TLabelframe',background=bg,bordercolor=border); st.configure('TLabelframe.Label',background=bg,foreground=fg)
        st.configure('TNotebook',background=bg,bordercolor=border); st.configure('TNotebook.Tab',background=panel,foreground=fg,padding=(11,8)); st.map('TNotebook.Tab',background=[('selected',accent),('active',accent)],foreground=[('disabled',disabled)])
        st.configure('TEntry',fieldbackground=panel,foreground=fg,insertcolor=fg); st.map('TEntry',fieldbackground=[('disabled',bg)],foreground=[('disabled',disabled)])
        for name in ('TButton','TCheckbutton'):
            st.configure(name,background=panel if name=='TButton' else bg,foreground=fg); st.map(name,background=[('active',accent)],foreground=[('disabled',disabled)])
        st.configure('TScrollbar',background=panel,troughcolor=bg,arrowcolor=fg)
        self.text.configure(bg=panel,fg=fg,insertbackground=fg,selectbackground=accent,highlightbackground=border,highlightcolor=accent,relief='flat')
    def selected_mode(self):
        return self.tab_modes[self.tabs.index(self.tabs.select())]
    def add_profiles(self):
        for p in filedialog.askopenfilenames(title='Select GPU profile JSON files',filetypes=[('JSON files','*.json')]):
            if Path(p) not in self.profiles:
                try: load_profiles([ROOT/'profiles'/'rtx4090.json',*self.profiles,Path(p)])
                except Exception as e: messagebox.showerror('Invalid GPU profile',str(e));continue
                self.profiles.append(Path(p))
        self.refresh_profiles()
    def clear_profiles(self): self.profiles=[]; self.refresh_profiles()
    def refresh_profiles(self): self.profiletext.set('Bundled RTX 4090'+ (' + '+', '.join(p.name for p in self.profiles) if self.profiles else ' (always included)'))
    def append(self,s):
        self.text.configure(state='normal'); self.text.insert('end',s); self.text.see('end'); self.text.configure(state='disabled')
    def choose_parent(self):
        parent=filedialog.askdirectory(title='Choose a shared results folder',initialdir=str(self.parent or Path.home()))
        if not parent: return False
        self.parent=Path(parent); self.parenttext.set(str(self.parent))
        try: save_parent(self.parent)
        except OSError as e: self.append(f'Could not remember folder across launches: {e}\n')
        return True
    def ensure_parent(self):
        return (self.parent is not None and self.parent.is_dir()) or self.choose_parent()
    def new_profile(self):
        if not messagebox.askyesno('Generate a new attacker profile?', 'This optional benchmark runs 193 Argon2id configurations twice (386 GPU runs). Estimated 2–4 hours on an RTX 4090-class system; other GPUs may take much longer. It uses synthetic data only and may sustain high GPU load. The Windows release includes Hashcat 8.0.0; macOS/Linux source editions need a compatible local Hashcat binary. Compatible GPU drivers and runtime are still required. Temperature abort is set to 85°C; missing telemetry pauses collection. You can pause between measurements and resume later. Continue?'):
            return
        if not self.ensure_parent(): return
        try:
            self.status.set('Preparing bundled GPU benchmark engine…'); self.root.update_idletasks()
            exe=engine.installed_engine() if os.name=='nt' else None
        except Exception as e:
            messagebox.showerror('GPU benchmark engine unavailable',str(e)); self.status.set('Ready.'); return
        self.status.set('Ready.')
        if exe is None:
            if not messagebox.askyesno('Source edition','This source build has no bundled engine. Select an existing official Hashcat 8.x executable?'):
                return
            exe=filedialog.askopenfilename(title='Select Hashcat executable',filetypes=[('Hashcat executable','hashcat.exe'),('All files','*.*')])
        if not exe:return
        # Ask for a backend and a specific device rather than accidentally aggregating multiple GPUs.
        dialog=tk.Toplevel(self.root); dialog.title('GPU selection'); dialog.transient(self.root); dialog.grab_set(); frame=ttk.Frame(dialog,padding=16); frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=f'Detected operating system: {platform.system()} (automatic)\nChoose CUDA (NVIDIA), HIP (AMD), Metal (macOS), or OpenCL where offered.\nSelect one backend device ID using View devices.',wraplength=500).pack(anchor='w')
        backends=gpu.available_backends(); backend=tk.StringVar(value=backends[0]); device=tk.StringVar(value='1'); ttk.Combobox(frame,values=backends,textvariable=backend,state='readonly').pack(anchor='w',pady=6); ttk.Entry(frame,textvariable=device,width=10).pack(anchor='w')
        def view():
            try:
                # A separate plain subprocess avoids blocking an optimization worker; this is an info query, not a benchmark.
                if FROZEN and os.name=='nt':
                    import ctypes
                    ctypes.windll.kernel32.SetDllDirectoryW(None)
                try: info=gpu.query_device_info(Path(exe).resolve(),backend.get())
                finally:
                    if FROZEN and os.name=='nt':ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
                win=tk.Toplevel(dialog); win.title('Hashcat device information'); txt=tk.Text(win,width=90,height=24,wrap='word'); txt.pack(fill='both',expand=True); txt.insert('1.0',info); txt.configure(state='disabled'); win.transient(dialog)
            except Exception as e: messagebox.showerror('Device information',str(e),parent=dialog)
        def launch():
            try:
                did=int(device.get()); assert 1<=did<=128
            except (ValueError,AssertionError): messagebox.showerror('Invalid device','Enter a backend device ID from 1 to 128.',parent=dialog); return
            be=backend.get();dialog.destroy()
            folder=self.parent/('argon2_gpu_profile_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            self.start_profile(folder,Path(exe),be,did)
        ttk.Button(frame,text='View devices',command=view).pack(anchor='w',pady=6);ttk.Button(frame,text='Start GPU collection',command=launch).pack(anchor='w')
    def start_profile(self,folder,exe,backend,device_id):
        try:
            folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
            # Refuse to clear another running collector's pause signal.
            lock=folder/'active.lock'
            if lock.exists():
                import psutil
                owner=gpu.read(lock)
                try: active=abs(psutil.Process(owner['pid']).create_time()-owner['created'])<.01
                except psutil.NoSuchProcess: active=False
                if active: raise ValueError('A collector is already running in that folder.')
            (folder/'pause.request').unlink(missing_ok=True)
            self.out=folder; self.profile_job=folder; self.job_kind='gpu';
            try:
                prefs=settings_file().with_name('last_gpu_job.json');prefs.parent.mkdir(parents=True,exist_ok=True);gpu.atomic_json(prefs,{'path':str(folder)})
            except OSError:pass
            self.log=folder/'gpu_desktop_log.txt'; self.offset=0
            cmd=[sys.executable]+([] if FROZEN else [str(ROOT/'desktop.py')])+['--gpu-worker',str(self.log),'--out',str(folder),'--hashcat',str(exe),'--backend',backend,'--device-id',str(device_id)]
            self.proc=subprocess.Popen(cmd,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception as e: messagebox.showerror('Unable to start GPU collection',str(e));self.proc=None;return
        self.text.configure(state='normal'); self.text.delete('1.0','end'); self.text.configure(state='disabled'); self.append(f'GPU profile job: {folder}\n\n');self.status.set('Starting GPU profile collection…');self.busy(True);self.root.after(250,self.poll)
    def resume_profile(self):
        folder=str(self.profile_job) if self.profile_job and (self.profile_job/'manifest.json').exists() and messagebox.askyesno('Resume last profile?',f'Resume or open the last GPU job?\n{self.profile_job}\nChoose No to select another folder.') else filedialog.askdirectory(title='Select an existing GPU profile job folder',initialdir=str(self.profile_job or self.parent or Path.home()))
        if not folder:return
        folder=Path(folder)
        try:
            m=gpu.read(folder/'manifest.json'); exe=Path(m['hashcat_path']); done=gpu.checkpoint_count(folder); total=len(m['configs'])*m['rounds']
            if done>=total and (folder/'gpu_profile.json').exists():
                self.offer_profile(folder);return
            if not exe.is_file() or gpu.digest(exe)!=m['hashcat_sha256']:
                recovered=engine.installed_engine(expected_exe_sha=m['hashcat_sha256']) if os.name=='nt' else None
                if recovered is not None: exe=recovered
                else:
                    x=filedialog.askopenfilename(title='Locate the same Hashcat executable');
                    if not x:return
                    exe=Path(x)
                    if gpu.digest(exe)!=m['hashcat_sha256']:raise ValueError('This binary differs from the original job. Start a new profile or use the original engine.')
            if not messagebox.askyesno('Resume GPU profile?',f'{done}/{total} measurements saved. Continue on the same GPU, driver, backend and Hashcat version? Estimated remaining time depends on your hardware.'):return
            self.start_profile(folder,exe,m['backend'],m['device_id'])
        except Exception as e: messagebox.showerror('Cannot resume',str(e))
    def pause_profile(self):
        if self.proc and self.job_kind=='gpu' and self.proc.poll() is None:
            (self.out/'pause.request').touch();self.pause.configure(state='disabled');self.status.set('Pausing after the current GPU measurement…')
    def offer_profile(self,folder):
        path=Path(folder)/'gpu_profile.json'; p=gpu.read(path); n=len(p['entries']); total=len(gpu.grid())
        msg=f'Profile created: {p["device"]} ({n}/{total} configurations).\n{path}\n\nAdd to the attacker profiles now? Adding a profile restricts recommendations to configurations measured by all selected profiles.'
        if messagebox.askyesno('GPU profile ready',msg):
            if path not in self.profiles:
                load_profiles([ROOT/'profiles'/'rtx4090.json',*self.profiles,path]);self.profiles.append(path)
            self.refresh_profiles()
    def run(self):
        try:
            # Validate before selecting a destination.
            values={k:v.get() for k,v in self.vars.items()}; mode=self.selected_mode(); target=self.targets[mode].get() if mode in TARGET_MODES else ''; make_args(values,self.profiles,Path('.'),mode,target)
        except ValueError as e: messagebox.showerror('Invalid settings',str(e)); return
        if not self.ensure_parent(): return
        self.out=self.parent/run_name(mode); self.job_kind='cpu'
        try:
            self.out.mkdir(parents=True,exist_ok=False); self.log=self.out/'desktop_log.txt'; self.log.touch(); self.offset=0
            args=make_args(values,self.profiles,self.out,mode,target)
            cmd=[sys.executable]+([] if FROZEN else [str(ROOT/'desktop.py')])+['--worker',str(self.log),*args]
            self.proc=subprocess.Popen(cmd,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception as e: messagebox.showerror('Unable to start',str(e)); self.proc=None; return
        self.text.configure(state='normal'); self.text.delete('1.0','end'); self.text.configure(state='disabled'); self.append(f'Results: {self.out}\n\n')
        self.status.set(f'Running {MODES[mode][0]}…'); self.busy(True); self.root.after(200,self.poll)
    def busy(self,on):
        for w in [self.start,self.add,self.clear,self.generate,self.resume,self.choose,*self.inputs,*self.target_entries]: w.configure(state='disabled' if on else 'normal')
        for i in range(len(self.tab_modes)): self.tabs.tab(i,state='disabled' if on and i!=self.tabs.index(self.tabs.select()) else 'normal')
        self.cancel.configure(state='normal' if on and self.job_kind=='cpu' else 'disabled'); self.pause.configure(state='normal' if on and self.job_kind=='gpu' else 'disabled'); self.openbtn.configure(state='normal' if self.out else 'disabled')
    def poll(self):
        if self.proc is None: return
        try:
            with self.log.open('r',encoding='utf8',errors='replace') as f:
                f.seek(self.offset); data=f.read(); self.offset=f.tell()
            if data: self.append(data)
        except OSError: pass
        rc=self.proc.poll()
        if rc is None: self.root.after(250,self.poll); return
        self.proc=None; self.busy(False)
        if self.job_kind=='gpu':
            if rc==0:
                self.status.set('GPU profile complete.');
                if not self.closing:
                    try:self.offer_profile(self.out)
                    except Exception as e:messagebox.showerror('Profile error',str(e))
            elif rc in (10,11,12,13,14):
                reasons={10:'Paused by user',11:'Actual GPU temperature limit reached',12:'GPU temperature readings unavailable (not overheating)',13:'Hashcat timeout (not a temperature warning)',14:'Benchmark/verification failed'}
                self.status.set(reasons[rc]+'. Check logs; resume from saved checkpoints.')
            else: self.status.set(f'GPU collection failed (exit {rc}). Saved measurements can be resumed.')
            if self.closing:self.root.destroy()
            return
        if rc!=0: self.status.set(f'Stopped or failed (exit {rc}). Partial files may remain.'); return
        try:
            report=json.loads((self.out/'recommendation.json').read_text(encoding='utf8')); winner=report['recommendation']
            if winner:
                c=winner['configuration']; self.status.set(f'{MODES[report["mode"]][0]}: {c["memory_mib"]} MiB · t={c["t"]} · p={c["p"]} | profile max {c["gpu_max_observed"]:.1f} H/s')
            else: self.status.set('Finished: no tested configuration met all constraints.')
            self.append('\n'+(self.out/'REPORT.md').read_text(encoding='utf8'))
        except Exception as e: self.status.set('Finished, but could not display report.'); self.append('\n'+str(e))
    def stop(self):
        if self.proc and self.proc.poll() is None and messagebox.askyesno('Stop benchmark?','The current run will end. Partial files are not a completed recommendation. Continue?'):
            self.proc.terminate()
    def open_folder(self):
        if not self.out: return
        try:
            if os.name=='nt': os.startfile(self.out)
            else: subprocess.Popen(['open' if platform.system()=='Darwin' else 'xdg-open',str(self.out)])
        except OSError as e: messagebox.showerror('Cannot open folder',str(e))
    def close(self):
        if self.proc and self.proc.poll() is None:
            if self.job_kind=='gpu':
                if not messagebox.askyesno('Pause and exit?', 'Wait for the current GPU measurement to finish, save its checkpoint, then close?'):return
                self.closing=True;self.pause_profile();return
            if not messagebox.askyesno('Exit?','A benchmark is running. Stop it and close?'): return
            self.proc.terminate()
        self.root.destroy()

def package_selftest(log):
    with Path(log).open('w',encoding='utf8',buffering=1) as f, contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        try:
            import optimizer
            optimizer.selftest()
            load_profiles([ROOT/'profiles'/'rtx4090.json'])
            exe=engine.installed_engine()
            if exe is None: raise ValueError('Missing bundled benchmark engine.')
            if FROZEN and os.name=='nt':
                import ctypes
                ctypes.windll.kernel32.SetDllDirectoryW(None)
            result=gpu.invoke(exe,['--version'],45)
            print(result.stdout)
            if result.returncode!=0 or result.stdout.strip() not in (engine.VERSION,'v'+engine.VERSION):
                raise ValueError('Bundled benchmark engine version check failed.')
            print('PACKAGED SELF-TEST PASSED (no GPU workload).'); return 0
        except Exception:
            traceback.print_exc(); return 1

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--package-self-test': return package_selftest(sys.argv[2])
    if len(sys.argv)>1 and sys.argv[1]=='--worker': return worker()
    if len(sys.argv)>1 and sys.argv[1]=='--gpu-worker': return worker(True)
    root=tk.Tk(); Desktop(root); root.mainloop(); return 0

if __name__=='__main__': sys.exit(main())
