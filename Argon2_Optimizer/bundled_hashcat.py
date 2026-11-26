"""Resolve a pinned bundled Hashcat release, unpacking it only on first GPU use.
Normal CPU optimization never needs to run this module's extraction routine.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'vendor' / 'hashcat-engine.zip'
VERSION = '8.0.0'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def cache_root():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.cache'))) / 'Argon2Optimizer' / 'gpu_engines'


def safe_extract(z, target):
    """Reject path traversal, links, and Windows path aliases before extraction."""
    seen = set()
    for item in z.infolist():
        name = item.filename
        path = PurePosixPath(name)
        if (not path.parts or path.is_absolute() or '\\' in name or ':' in name
                or any(p in ('..', '.') or p.rstrip(' .') != p or not p for p in path.parts)
                or stat.S_ISLNK(item.external_attr >> 16)):
            raise ValueError(f'Unsafe bundled engine member: {name}')
        norm = str(path).casefold()
        if norm in seen:
            raise ValueError(f'Duplicate bundled engine member: {name}')
        seen.add(norm)
    z.extractall(target)


def installed_engine(bundle=None, base=None, expected_exe_sha=None):
    """Return the stable path for the embedded engine, or None if not bundled.
    A mismatched expected binary (e.g. an older paused job) is not substituted.
    """
    bundle = Path(bundle if bundle is not None else BUNDLE)
    if not bundle.is_file():
        return None
    base = Path(base if base is not None else cache_root())
    archive_sha = sha256(bundle)
    with zipfile.ZipFile(bundle) as z:
        meta = json.loads(z.read('bundle_provenance.json'))
        if meta['version'] != VERSION:
            raise ValueError('Unexpected bundled Hashcat version.')
        exe_sha = meta['hashcat_exe_sha256']
        if expected_exe_sha is not None and expected_exe_sha != exe_sha:
            return None
        folder = base / ('hashcat-' + VERSION + '-' + archive_sha[:20])
        exe = folder / 'hashcat.exe'
        def ready():
            return (exe.is_file() and (folder/'docs'/'license.txt').is_file()
                    and (folder/'OpenCL').is_dir() and (folder/'modules').is_dir()
                    and (folder/'bundle_provenance.json').is_file()
                    and sha256(exe) == exe_sha)
        if ready():
            return exe
        if folder.exists():
            raise ValueError(f'Bundled engine cache is incomplete or modified: {folder}. Close the optimizer, remove that engine cache folder, and try again.')
        base.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.unpack-', dir=base))
        try:
            safe_extract(z, staging)
            if (not (staging/'hashcat.exe').is_file() or sha256(staging/'hashcat.exe') != exe_sha
                    or not (staging/'docs'/'license.txt').is_file()
                    or not (staging/'OpenCL').is_dir() or not (staging/'modules').is_dir()):
                raise ValueError('Bundled engine archive is incomplete or damaged.')
            try:
                staging.rename(folder)
            except OSError:
                # Another process may have finished extracting the same bundle.
                if not ready():
                    raise
            if not ready():
                raise ValueError('Bundled engine failed its cache integrity check.')
            return exe
        finally:
            if staging.exists():
                shutil.rmtree(staging)
