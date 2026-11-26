"""Build the distributable Windows x64 executable, including the pinned GPU engine.
Run on Windows only. A local official archive can be supplied for offline/reviewed builds.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from bundled_hashcat import VERSION, sha256

ROOT = Path(__file__).resolve().parent
URL = f'https://hashcat.net/files/hashcat-{VERSION}.7z'


def check_layout(root):
    root = Path(root)
    if not ((root/'hashcat.exe').is_file() and (root/'docs'/'license.txt').is_file()
            and (root/'OpenCL').is_dir() and (root/'modules').is_dir()):
        raise ValueError('Expected official Hashcat distribution layout, including executable, license, kernels and modules.')
    return root


def pack_engine(root, destination, upstream_sha, acquisition):
    root = check_layout(root)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    metadata = {'version': VERSION, 'upstream_url': URL, 'upstream_archive_sha256': upstream_sha,
                'hashcat_exe_sha256': sha256(root/'hashcat.exe'), 'acquisition': acquisition,
                'license': 'See original docs/license.txt and accompanying upstream notices.'}
    temp = destination.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for path in sorted(root.rglob('*')):
                if path.is_symlink():
                    raise ValueError(f'Unexpected symbolic link in engine release: {path}')
                if path.is_file():
                    name = path.relative_to(root).as_posix()
                    if name == 'bundle_provenance.json':
                        raise ValueError('Unexpected provenance filename in upstream release.')
                    z.write(path, name)
            z.writestr('bundle_provenance.json', json.dumps(metadata, indent=2) + '\n')
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return metadata


def archive_extractors(archive, destination):
    """Use external BCJ2-capable extractors; no py7zr dependency."""
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    paths = [shutil.which('7z.exe'), shutil.which('7zz.exe')]
    for name in ('ProgramW6432', 'ProgramFiles', 'ProgramFiles(x86)'):
        if os.environ.get(name):
            paths.append(str(Path(os.environ[name]) / '7-Zip' / '7z.exe'))
    seen = set()
    for path in paths:
        if path and Path(path).is_file() and str(Path(path).resolve()).casefold() not in seen:
            seen.add(str(Path(path).resolve()).casefold())
            yield [str(Path(path).resolve()), 'x', str(archive), '-o'+str(destination), '-y']
    # Windows ships bsdtar, based on libarchive, which supports 7z/BCJ2.
    # Prefer the system executable rather than an unrelated tar from Git/MSYS.
    system_tar = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'tar.exe'
    if system_tar.is_file():
        yield [str(system_tar), '-xf', str(archive), '-C', str(destination)]


def extract_release(archive, destination):
    destination = Path(destination)
    failures = []
    for command in archive_extractors(archive, destination):
        # A failed extractor may leave partial files; never merge them.
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        print(f'Extracting official release with {command[0]}', flush=True)
        try:
            subprocess.run(command, check=True, timeout=600, stdin=subprocess.DEVNULL)
            exes = list(destination.rglob('hashcat.exe'))
            if len(exes) != 1:
                raise ValueError('Expected exactly one hashcat.exe after extraction.')
            return check_layout(exes[0].parent)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            failures.append(f'{command[0]}: {exc}')
            print(f'Extractor failed: {exc}', flush=True)
    detail = '\n'.join(failures) or 'No supported extractor found.'
    raise RuntimeError('Could not extract the Hashcat release. Install current 64-bit 7-Zip from https://www.7-zip.org/ and rerun the build.\n'+detail)


def prepare_engine(archive, expected_sha=None):
    with tempfile.TemporaryDirectory(prefix='argon2-build-', ignore_cleanup_errors=True) as td:
        td = Path(td)
        if archive is None:
            archive = td / f'hashcat-{VERSION}.7z'
            print(f'Downloading pinned upstream release: {URL}', flush=True)
            with urllib.request.urlopen(URL, timeout=90) as response, archive.open('wb') as out:
                shutil.copyfileobj(response, out)
            acquisition = 'official HTTPS download'
        else:
            archive = Path(archive).resolve(strict=True)
            acquisition = 'builder-supplied upstream archive'
        archive_sha = sha256(archive)
        print(f'Upstream archive SHA-256: {archive_sha}', flush=True)
        if expected_sha and archive_sha.lower() != expected_sha.lower():
            raise ValueError('Supplied SHA-256 does not match Hashcat archive.')
        if not expected_sha:
            print('No independent expected SHA-256 supplied; publisher signature has not been verified by this script.', flush=True)
        root = extract_release(archive, td/'extracted')
        result = subprocess.run([str(root/'hashcat.exe'), '--version'], cwd=root, check=True, capture_output=True, text=True, timeout=45)
        if result.stdout.strip() not in (VERSION, 'v'+VERSION):
            raise ValueError(f'Expected Hashcat {VERSION}, got {result.stdout.strip()!r}.')
        metadata = pack_engine(root, ROOT/'vendor'/'hashcat-engine.zip', archive_sha, acquisition)
        print('Engine packaged; upstream licenses retained.', flush=True)
        return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hashcat-archive', type=Path, help='Optional local official Hashcat 8.0.0 .7z release archive')
    p.add_argument('--sha256', help='Optional independently verified upstream archive SHA-256')
    a = p.parse_args()
    if os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64') or sys.maxsize <= 2**32:
        p.error('Use 64-bit Python on Windows x64, or the included Windows GitHub Actions workflow.')
    os.chdir(ROOT)
    local = ROOT/f'hashcat-{VERSION}.7z'
    metadata = prepare_engine(a.hashcat_archive or (local if local.is_file() else None), a.sha256)
    def run(*args): subprocess.run([sys.executable, *args], check=True)
    run('optimizer.py','self-test')
    run('-m','unittest','-q','test_optimizer','test_modes','test_desktop_v3','test_bundle_v4')
    run('-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name','Argon2Optimizer',
        '--add-data','profiles;profiles','--add-data','vendor/hashcat-engine.zip;vendor',
        '--copy-metadata','argon2-cffi','--collect-all','_argon2_cffi_bindings',
        '--hidden-import','optimizer','--hidden-import','profile_data','--hidden-import','gpu_profile_builder',
        '--hidden-import','bundled_hashcat','desktop.py')
    exe = ROOT/'dist'/'Argon2Optimizer.exe'
    log = ROOT/'dist'/'package_selftest.txt'; log.unlink(missing_ok=True)
    subprocess.run([str(exe),'--package-self-test',str(log)], check=True, timeout=300)
    if not log.is_file() or 'PACKAGED SELF-TEST PASSED' not in log.read_text(encoding='utf8'):
        raise RuntimeError('Packaged self-test did not finish successfully; inspect dist/package_selftest.txt.')
    (ROOT/'dist'/'release_provenance.json').write_text(json.dumps({**metadata,'optimizer_exe_sha256':sha256(exe)},indent=2)+'\n',encoding='utf8')
    print(f'Windows release ready: {exe}\nCPU known-answer test and bundled engine version check passed. No GPU benchmark was run by the build.', flush=True)


if __name__ == '__main__':
    main()
