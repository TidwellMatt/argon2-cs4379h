import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from bundled_hashcat import installed_engine, safe_extract, sha256
from build_windows import pack_engine, extract_release
from unittest.mock import patch
import subprocess

class TestBundle(unittest.TestCase):
    def fixture(self, root):
        p=root/'upstream';p.mkdir()
        (p/'hashcat.exe').write_bytes(b'synthetic executable fixture only')
        (p/'docs').mkdir();(p/'docs/license.txt').write_text('license fixture')
        (p/'OpenCL').mkdir();(p/'OpenCL/test.cl').write_text('fixture')
        (p/'modules').mkdir();(p/'modules/module_fixture.dll').write_bytes(b'fixture')
        return p
    def test_pack_extract_reuse_and_resume_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); upstream=self.fixture(root); archive=root/'engine.zip'; cache=root/'cache'
            meta=pack_engine(upstream,archive,'fixture-sha','test fixture')
            self.assertEqual(meta['hashcat_exe_sha256'],sha256(upstream/'hashcat.exe'))
            exe=installed_engine(archive,cache)
            self.assertEqual(exe.read_bytes(),(upstream/'hashcat.exe').read_bytes())
            self.assertTrue((exe.parent/'docs/license.txt').is_file())
            self.assertEqual(installed_engine(archive,cache),exe)
            self.assertEqual(installed_engine(archive,cache,sha256(exe)),exe)
            self.assertIsNone(installed_engine(archive,cache,'wrong-hash'))
            exe.write_bytes(b'changed')
            with self.assertRaises(ValueError): installed_engine(archive,cache)
    def test_extractor_fallback_clears_partial_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); target=root/'out'; archive=root/'engine.7z'
            commands=[['7z.exe','x'], ['tar.exe','-xf']]
            def fake_run(command, **kwargs):
                self.assertTrue(kwargs['check'])
                if command[0]=='7z.exe':
                    (target/'partial').write_text('bad')
                    raise subprocess.CalledProcessError(2,command)
                self.assertFalse((target/'partial').exists())
                self.fixture(target)
            with patch('build_windows.archive_extractors',return_value=iter(commands)), patch('build_windows.subprocess.run',side_effect=fake_run):
                self.assertEqual(extract_release(archive,target),target/'upstream')
    def test_extractor_no_tools(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch('build_windows.archive_extractors',return_value=iter([])):
                with self.assertRaisesRegex(RuntimeError,'Install current 64-bit 7-Zip'):
                    extract_release(root/'engine.7z',root/'out')

    def test_missing_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.assertIsNone(installed_engine(root/'missing.zip',root/'cache'))
            self.assertFalse((root/'cache').exists())
    def test_unsafe_member(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'unsafe.zip'
            with zipfile.ZipFile(path,'w') as z:z.writestr('../escape','bad')
            with zipfile.ZipFile(path) as z:
                with self.assertRaises(ValueError):safe_extract(z,root/'out')
    def test_missing_license(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=self.fixture(root);(p/'docs/license.txt').unlink()
            with self.assertRaises(ValueError):pack_engine(p,root/'bad.zip','fixture','fixture')

if __name__=='__main__':unittest.main()
