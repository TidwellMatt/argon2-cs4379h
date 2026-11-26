import datetime, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import desktop as d
import gpu_profile_builder as g
from profile_data import candidates, load_profiles

INFO='''CUDA Info:\nCUDA.Version.: 13.5\nBackend Device ID #01 (Alias: #02)\n  Name...........: NVIDIA GeForce RTX 4090\n  Memory.Total...: 24563 MB\n  Memory.Free....: 23036 MB\nOpenCL Info:\n  Backend Device ID #02 (Alias: #01)\n    Type...........: GPU\n    Name...........: NVIDIA GeForce RTX 4090\n'''
class DesktopV3(unittest.TestCase):
    def test_names(self):
        now=datetime.datetime(2026,11,26,0,10,22,4559)
        self.assertEqual(d.run_name('balanced',now),'argon2_run_balanced_20261126_001022_004559')
        for mode in d.MODES:self.assertTrue(d.run_name(mode,now).startswith('argon2_run_'+d.MODE_NAMES[mode]+'_'))
    def test_shared_folder(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); settings=p/'preferences'/'settings.json'; destination=p/'Results';destination.mkdir()
            with patch.object(d,'settings_file',return_value=settings):
                self.assertIsNone(d.read_parent());d.save_parent(destination);self.assertEqual(d.read_parent(),destination);destination.rmdir();self.assertIsNone(d.read_parent())
    def test_grid_and_device(self):
        bundled=load_profiles([d.ROOT/'profiles/rtx4090.json'])[0]
        self.assertEqual({g.config_key(*c) for c in g.grid()},{c['config'] for c in candidates([bundled])})
        self.assertEqual(g.device_info(INFO,'cuda',1)['Name'],'NVIDIA GeForce RTX 4090')
        self.assertEqual(g.device_info(INFO,'opencl',2)['Type'],'GPU')
        with self.assertRaises(ValueError):g.device_info(INFO,'cuda',2)
        with self.assertRaises(ValueError):g.device_info(INFO.replace('Type...........: GPU','Type...........: CPU'),'opencl',2)
    def test_laptop_multiple_opencl_platforms(self):
        # Real device metadata and status records, excluding paths and inputs.
        info='hashcat (v8.0.0) starting in backend information mode\r\n\r\nnvmlDeviceGetFanSpeed(): Not Supported\r\n\r\nBridge units are selected by the hash mode, so none are listed here.\r\nAdd -m <hash mode> to list the units that mode would use.\r\n\r\nOpenCL Info:\r\n============\r\n\r\nOpenCL Platform ID #1\r\n  Vendor..: NVIDIA Corporation\r\n  Name....: NVIDIA CUDA\r\n  Version.: OpenCL 3.0 CUDA 13.3.71\r\n\r\n  Backend Device ID #01\r\n    Type...........: GPU\r\n    Vendor.ID......: 32\r\n    Vendor.........: NVIDIA Corporation\r\n    Name...........: NVIDIA GeForce RTX 3070 Laptop GPU\r\n    Version........: OpenCL 3.0 CUDA\r\n    Processor(s)...: 40\r\n    Preferred.Thrd.: 32\r\n    Clock..........: 1620\r\n    Memory.Total...: 8191 MB (limited to 2047 MB allocatable in one block)\r\n    Memory.Free....: 8064 MB\r\n    Memory.Unified.: 0\r\n    Local.Memory...: 48 KB\r\n    OpenCL.Version.: OpenCL C 1.2 \r\n    Driver.Version.: 610.60\r\n    PCI.Addr.BDF...: 01:00.0\r\n\r\nOpenCL Platform ID #2\r\n  Vendor..: Intel(R) Corporation\r\n  Name....: Intel(R) OpenCL HD Graphics\r\n  Version.: OpenCL 3.0 \r\n\r\n  Backend Device ID #02\r\n    Type...........: GPU\r\n    Vendor.ID......: 8\r\n    Vendor.........: Intel(R) Corporation\r\n    Name...........: Intel(R) UHD Graphics\r\n    Version........: OpenCL 3.0 NEO \r\n    Processor(s)...: 8\r\n    Preferred.Thrd.: 7\r\n    Clock..........: 1150\r\n    Memory.Total...: 6456 MB (limited to 1614 MB allocatable in one block)\r\n    Memory.Free....: 6392 MB\r\n    Memory.Unified.: 1\r\n    Local.Memory...: 64 KB\r\n    OpenCL.Version.: OpenCL C 1.2 \r\n    Driver.Version.: 31.0.101.2137\r\n\r\n'
        status='{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 719, "temp": 61, "util": 97, "fanspeed": -1, "corespeed": 1470, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 713, "temp": 63, "util": 94, "fanspeed": -1, "corespeed": 1605, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 63, "util": 97, "fanspeed": -1, "corespeed": 1710, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 64, "util": 94, "fanspeed": -1, "corespeed": 1590, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 64, "util": 97, "fanspeed": -1, "corespeed": 1545, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 65, "util": 94, "fanspeed": -1, "corespeed": 1575, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 65, "util": 97, "fanspeed": -1, "corespeed": 1545, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 3, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 65, "util": 94, "fanspeed": -1, "corespeed": 1560, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 11, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 66, "util": 97, "fanspeed": -1, "corespeed": 1545, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}\n{"status": 11, "devices": [{"device_id": 1, "device_name": "NVIDIA GeForce RTX 3070 Laptop GPU", "device_type": "GPU", "speed": 712, "temp": 66, "util": 97, "fanspeed": -1, "corespeed": 1545, "memoryspeed": 7001, "buslanes": 8, "power": -1}]}'
        gpu=g.device_info(info,'opencl',1)
        self.assertEqual(gpu['Name'],'NVIDIA GeForce RTX 3070 Laptop GPU')
        self.assertEqual(gpu['Vendor'],'NVIDIA Corporation')
        self.assertEqual(g.device_info(info,'opencl',2)['Name'],'Intel(R) UHD Graphics')
        measurements,terminal=g.parse_status(status,gpu['Name'],1)
        self.assertGreaterEqual(len(measurements),3)
        self.assertTrue(g.temperature_samples(status,gpu['Name'],1))
        self.assertFalse(g.thermal(status))
        with self.assertRaises(ValueError):g.parse_status(status,'Intel(R) UHD Graphics',1)
    def test_platform_backend_flags(self):
        for platform_name in ('Windows','Linux'):
            with patch.object(g.platform,'system',return_value=platform_name):
                self.assertEqual(g.backend_flags('cuda'),['--backend-ignore-hip','--backend-ignore-opencl'])
                self.assertEqual(g.backend_flags('opencl'),['--backend-ignore-hip','--backend-ignore-cuda','-D','2'])
        with patch.object(g.platform,'system',return_value='Darwin'):
            self.assertIn('--backend-ignore-metal',g.backend_flags('opencl'))
    def test_platform_options(self):
        for name in ('Windows','Linux'):
            with patch.object(g.platform,'system',return_value=name):
                self.assertEqual(g.available_backends(),('cuda','hip','opencl'))
                self.assertEqual(g.backend_flags('hip'),['--backend-ignore-cuda','--backend-ignore-opencl'])
                with self.assertRaises(ValueError):g.backend_flags('metal')
        with patch.object(g.platform,'system',return_value='Darwin'):
            self.assertEqual(g.available_backends(),('metal','opencl'))
            self.assertEqual(g.backend_flags('metal'),['--backend-ignore-hip','--backend-ignore-cuda','--backend-ignore-opencl'])
            with self.assertRaises(ValueError):g.backend_flags('cuda')
    def test_temperature_messages(self):
        self.assertFalse(g.thermal('Watchdog: Temperature abort trigger set to 85c\nRuntime limit reached, aborting'))
        self.assertTrue(g.thermal('\x1b[31mTemperature limit on GPU #1 reached, aborting\x1b[0m'))
        self.assertFalse(g.thermal('GPU utilization 100%\nRuntime limit reached, aborting'))
        def line(status,temp,speed):
            return json.dumps({'status':status,'devices':[dict(device_id=1,device_name='GPU A',device_type='GPU',temp=temp,speed=speed)]})
        self.assertEqual(g.temperature_samples(line(3,86,0)+'\n'+line(11,60,100),'GPU A',1),[86,60])
        self.assertEqual(g.temperature_samples(line(3,-1,100),'GPU A',1),[])
    def test_measure_distinguishes_thermal_telemetry_and_normal_runtime(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);inputs=out/'inputs';inputs.mkdir();k=g.REFERENCE
            target=inputs/(k+'.phc');target.write_bytes(b'synthetic fixture')
            g.atomic_json(inputs/(k+'.verified.json'),dict(target_sha256=g.digest(target),backend='cuda',device_id=1,device='GPU A'))
            manifest=dict(device={'Name':'GPU A'},device_id=1,backend='cuda')
            def text(temp):
                def line(st): return json.dumps(dict(status=st,devices=[dict(device_id=1,device_name='GPU A',device_type='GPU',speed=123,temp=temp,util=100)]))
                return 'Watchdog: Temperature abort trigger set to 85c\n'+'\n'.join([line(3)]*4+['Runtime limit reached, aborting',line(11)])
            for temp,expected in [(60,'ok'),(85,'thermal'),(-1,'telemetry')]:
                with patch.object(g,'invoke',return_value=SimpleNamespace(stdout=text(temp),returncode=4)):
                    result=g.measure(('id',64,3,4),1,Path('hashcat'),out,inputs,manifest)
                    self.assertEqual('thermal' if result.get('thermal') else result.get('reason',result['status']),expected)
    def test_failed_device_query_reports_actual_error(self):
        from types import SimpleNamespace
        with patch.object(g,'invoke',return_value=SimpleNamespace(returncode=1,stdout='unsupported option')):
            with self.assertRaisesRegex(ValueError,'unsupported option'):
                g.query_device_info(Path('hashcat.exe'),'cuda')
    def test_parser(self):
        s={'status':3,'devices':[{'device_id':1,'device_name':'GPU A','device_type':'GPU','speed':123,'temp':61}]}
        text=json.dumps(s)+'\n'+json.dumps({'status':11})
        self.assertEqual(g.parse_status(text,'GPU A',1)[1],11)
        with self.assertRaises(ValueError):g.parse_status(text,'GPU B',1)
        with self.assertRaises(ValueError):g.parse_status(text,'GPU A',2)
    def test_pause_resume_export(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'job';exe=Path(td)/'fake_hashcat';exe.write_bytes(b'fake'); cs=[('id',64,3,4),('id',64,4,4)];calls=[]
            def invoke(exe,args,timeout):return SimpleNamespace(returncode=0,stdout='v8.0.0' if '--version' in args else INFO)
            def setup(out):return out
            def measure(c,r,exe,out,inputs,manifest):
                calls.append((tuple(c),r))
                if len(calls)==1:(out/'pause.request').touch()
                return dict(status='ok',gpu_hps=100+r,samples=5,gpu_temp_max_c=60,elapsed_s=20)
            with patch.object(g,'grid',return_value=cs),patch.object(g,'invoke',side_effect=invoke),patch.object(g,'setup_inputs',side_effect=setup),patch.object(g,'measure',side_effect=measure):
                self.assertEqual(g.run(out,exe,'cuda',1),10);self.assertEqual(g.checkpoint_count(out),1);self.assertFalse((out/'gpu_profile.json').exists())
                (out/'pause.request').unlink();self.assertEqual(g.run(out,exe,'cuda',1),0);self.assertEqual(g.checkpoint_count(out),4);self.assertEqual(len(calls),4);self.assertEqual(len(set(calls)),4)
                p=load_profiles([out/'gpu_profile.json'])[0];self.assertEqual(len(p['entries']),2);self.assertEqual(p['entries'][g.REFERENCE]['hps_rounds'],[101,102]);self.assertEqual(len(candidates([p])),2)
                exe.write_bytes(b'changed')
                with self.assertRaises(ValueError):g.run(out,exe,'cuda',1)
    def test_thermal_pause(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'job';exe=Path(td)/'fake';exe.write_bytes(b'fake')
            def invoke(exe,args,timeout):return SimpleNamespace(returncode=0,stdout='v8.0.0' if '--version' in args else INFO)
            with patch.object(g,'grid',return_value=[('id',64,3,4)]),patch.object(g,'invoke',side_effect=invoke),patch.object(g,'setup_inputs',side_effect=lambda p:p),patch.object(g,'measure',return_value={'status':'failed','thermal':True,'error':'temperature'}):
                self.assertEqual(g.run(out,exe,'cuda',1),11);self.assertEqual(g.checkpoint_count(out),0)
if __name__=='__main__':unittest.main()
