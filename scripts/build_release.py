"""Build distributable files; install the exact wheel in a provisioned runtime."""
from pathlib import Path
import subprocess
import os
import tomllib
import sys
from setuptools.build_meta import build_sdist
expected = tomllib.loads(Path('pyproject.toml').read_text())['project']['version']
subprocess.run([sys.executable, 'scripts/check_runtime_locks.py'], check=True)
out=Path('/opt/dist');out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','pip','wheel','--no-build-isolation','--no-deps','--wheel-dir',str(out),'.'],check=True)
wheels=list(out.glob(f'ariadne_mark-{expected}-*.whl'))
if len(wheels) != 1:
    raise RuntimeError('Expected exactly one wheel for the current SDK version')
wheel=wheels[0]
# Source PYTHONPATH/egg-info can make pip believe an uninstalled wheel already
# exists. Install outside the checkout and verify in an isolated interpreter.
install_env = dict(os.environ)
install_env.pop('PYTHONPATH', None)
subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps',
                '--force-reinstall','--no-cache-dir',str(wheel.resolve())],
               check=True, env=install_env, cwd='/tmp')
actual = subprocess.check_output([sys.executable, '-I', '-c',
    'from importlib.metadata import version; print(version("ariadne-mark"))'], text=True).strip()
if actual != expected:
    raise RuntimeError(f'Installed SDK version mismatch: {actual} != {expected}')
build_sdist(str(out))
