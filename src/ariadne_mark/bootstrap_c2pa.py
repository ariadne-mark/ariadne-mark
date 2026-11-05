"""Explicit installation of an unmodified official C2PA release absent from PyPI.

Only Linux x86-64 is qualified. Models/runtime requests never call this module.
Upstream archives and the initial installer/CA-store wheels are SHA-256 pinned.
Build/runtime wheels use the packaged qualified-platform hash lock.
"""
import argparse
import ctypes
import hashlib
import importlib
import json
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'c2pa-bootstrap.json').read_text())

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def download(spec, directory, *, context=None):
    path = directory / spec['filename']
    if path.is_file() and digest(path) == spec['sha256']:
        return path
    fd, tmp = tempfile.mkstemp(prefix='.download-', dir=directory)
    import os
    try:
        with os.fdopen(fd, 'wb') as f, urllib.request.urlopen(spec['url'], context=context, timeout=90) as response:
            size = 0
            for block in iter(lambda: response.read(1024 * 1024), b''):
                size += len(block)
                if size > 128 * 1024 * 1024:
                    raise ValueError('Bootstrap download exceeded bound')
                f.write(block)
        if digest(Path(tmp)) != spec['sha256']:
            raise ValueError('Bootstrap checksum mismatch: ' + spec['filename'])
        Path(tmp).replace(path)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return path

def extract_source(archive, destination):
    with ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist()) > 512 * 1024 * 1024:
            raise ValueError('Oversized bootstrap source')
        for item in z.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Unsafe bootstrap archive member')
        z.extractall(destination)
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError('Unexpected upstream source layout')
    return roots[0]

def run(*args, cwd=None):
    subprocess.run([sys.executable, *map(str, args)], cwd=cwd, check=True)

def install(*, allow_system=False, cache=None, wheel_dir=None):
    if platform.system() != 'Linux' or platform.machine().lower() not in {'x86_64', 'amd64'}:
        raise RuntimeError('Qualified bootstrap is Linux x86-64; use the linux/amd64 Docker recipe')
    if sys.prefix == sys.base_prefix and not allow_system:
        raise RuntimeError('Activate a Python virtualenv first; --allow-system is for an isolated Docker build')
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Qualified hashed bootstrap requires Python 3.12; use the Docker recipe')
    lock = ROOT / 'bootstrap-linux-py312.lock'
    if digest(lock) != MANIFEST['bootstrap_lock_sha256']:
        raise ValueError('Bootstrap requirements lock checksum mismatch')
    cache = Path(cache or Path.home() / '.cache/ariadne-mark/c2pa-bootstrap-v1').resolve()
    cache.mkdir(parents=True, exist_ok=True)
    # Exact wheel digests protect the initial update even on an older TLS store.
    wheels = [download(MANIFEST[key], cache) for key in ['pip', 'certifi']]
    run('-m', 'pip', 'install', '--no-index', '--no-deps', '--upgrade', *wheels)
    importlib.invalidate_caches()
    import certifi
    tls = ssl.create_default_context(cafile=certifi.where())
    source = download(MANIFEST['source'], cache, context=tls)
    native = download(MANIFEST['native'], cache, context=tls)
    run('-m', 'pip', 'install', '--require-hashes', '--only-binary=:all:', '--no-deps', '-r', lock)
    with tempfile.TemporaryDirectory(prefix='ariadne-c2pa-build-') as folder:
        work = Path(folder)
        upstream = extract_source(source, work / 'source')
        artifacts = upstream / 'artifacts/x86_64-unknown-linux-gnu'
        artifacts.mkdir(parents=True, exist_ok=True)
        library = artifacts / 'libc2pa_c.so'
        with ZipFile(native) as z:
            with z.open('lib/libc2pa_c.so') as incoming, library.open('wb') as outgoing:
                shutil.copyfileobj(incoming, outgoing)
        if digest(library) != MANIFEST['native']['library_sha256']:
            raise ValueError('Unexpected native library bytes')
        # Verify compatibility before installing, while retaining only upstream code.
        ctypes.CDLL(str(library))
        for name in ['LICENSE-MIT', 'LICENSE-APACHE']:
            shutil.copyfile(upstream / name, artifacts / name)
        (artifacts / 'ARIADNE-BUILD-ORIGIN.json').write_text(json.dumps(MANIFEST, indent=2))
        out = work / 'dist'
        run('setup.py', 'bdist_wheel', '--plat-name', 'linux_x86_64', '--dist-dir', out, cwd=upstream)
        built = list(out.glob('c2pa_python-0.38.3-*.whl'))
        if len(built) != 1:
            raise ValueError('Unexpected C2PA wheel output')
        run('-m', 'pip', 'install', '--no-deps', '--upgrade', built[0])
        if wheel_dir:
            target = Path(wheel_dir); target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(built[0], target / built[0].name)
    from importlib.metadata import version
    if version('c2pa-python') != MANIFEST['python_version']:
        raise RuntimeError('Wrong installed C2PA version')
    import c2pa
    installed = Path(c2pa.__file__).parent / 'libs/libc2pa_c.so'
    if digest(installed) != MANIFEST['native']['library_sha256']:
        raise RuntimeError('Installed C2PA native library mismatch')
    return {'python_version': version('c2pa-python'), 'native_version': MANIFEST['native_version'],
            'native_sha256': digest(installed), 'python_code_modified': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-system', action='store_true')
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--wheel-dir', type=Path)
    args = parser.parse_args()
    print(json.dumps(install(allow_system=args.allow_system, cache=args.cache_dir, wheel_dir=args.wheel_dir), indent=2))

if __name__ == '__main__':
    main()
