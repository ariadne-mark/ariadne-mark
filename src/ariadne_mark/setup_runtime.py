"""Explicit, hash-pinned media setup from an installed wheel (never on requests)."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from ariadne_mark.errors import AriadneError

ROOT = Path(__file__).resolve().parent


def install(engine='media', *, allow_system=False, cache=None, wheelhouse=None, fetch_models=False):
    if engine not in {'media', 'video'}:
        raise ValueError('Choose media or video')
    if (platform.system() != 'Linux' or platform.machine().lower() not in {'x86_64', 'amd64'}
            or sys.version_info[:2] != (3, 12)):
        raise ValueError('Media setup requires Linux x86-64 / Python 3.12; use the Docker recipe')
    if sys.prefix == sys.base_prefix and not allow_system:
        raise ValueError('Activate a virtualenv; --allow-system is for isolated container builds')
    pins = json.loads((ROOT / 'runtime-locks.json').read_text())['locks'][engine]
    lock = ROOT / pins['filename']
    if hashlib.sha256(lock.read_bytes()).hexdigest() != pins['sha256']:
        raise ValueError('Runtime dependency lock checksum mismatch')
    env = dict(os.environ)
    if wheelhouse is not None:
        directory = Path(wheelhouse).resolve(strict=True)
        if not directory.is_dir():
            raise ValueError('Wheelhouse must be a directory')
        env.update(PIP_NO_INDEX='1', PIP_FIND_LINKS=str(directory))
    bootstrap = [sys.executable, '-m', 'ariadne_mark.bootstrap_c2pa']
    if allow_system:
        bootstrap.append('--allow-system')
    if cache is not None:
        bootstrap += ['--cache-dir', str(Path(cache).resolve())]
    commands = [bootstrap,
        [sys.executable, '-m', 'pip', 'install', '--require-hashes', '--only-binary=:all:',
         '--no-deps', '--no-build-isolation', '-r', str(lock)],
        [sys.executable, '-m', 'pip', 'check'],
        [sys.executable, '-m', 'ariadne_mark.cli', 'runtime', 'check']]
    if fetch_models:
        missing = [name for name in ['ffmpeg', 'ffprobe', 'node', 'npm'] if shutil.which(name) is None]
        if missing:
            raise ValueError('Install system prerequisites before setup: ' + ', '.join(missing))
        commands.append([sys.executable, '-m', 'ariadne_mark.cli', 'models', 'fetch',
                         '--engine', 'all' if engine == 'media' else 'video'])
    for command in commands:
        try:
            # Keep final stdout JSON parseable; installer output goes to stderr.
            subprocess.run(command, env=env, check=True, stdout=sys.stderr)
        except subprocess.CalledProcessError as exc:
            raise AriadneError('Explicit runtime setup failed; inspect installer output and retry setup') from exc
    return {'status': 'installed', 'engine': engine, 'models_provisioned': fetch_models,
            'dependency_lock_sha256': pins['sha256'], 'native_qualification': 'checked_in_fresh_process',
            'legacy_decoders_included': engine == 'media',
            'note': 'Start/restart media processes after explicit installation'}
