"""Build distributable files and install the exact wheel with its media extra."""
from pathlib import Path
import subprocess
import sys
from setuptools.build_meta import build_sdist
out=Path('/opt/dist');out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','pip','wheel','--no-build-isolation','--no-deps','--wheel-dir',str(out),'.'],check=True)
wheel=next(out.glob('ariadne_mark-*.whl'))
subprocess.run([sys.executable,'-m','pip','install','--no-deps','--no-cache-dir',str(wheel)+'[media]'],check=True)
build_sdist(str(out))
