#!/bin/bash
set -euo pipefail
# Run in the build-stage system environment (FFmpeg, Node/npm present). The
# new venv cannot see its global Python media packages. Source isn't mounted.
engine=$1
python -m venv "/work/$engine-venv"
export PATH="/work/$engine-venv/bin:$PATH"
export PYTHONNOUSERSITE=1
unset PYTHONPATH
export ARIADNE_VIDEO_DATA="/work/$engine-video-runtime"
export npm_config_cache="/work/$engine-npm-cache"
cd /work
python -I -c 'import importlib.util; assert all(importlib.util.find_spec(x) is None for x in ["c2pa","torch","numpy","trustmark","av","PIL","cryptography"]); print("Fresh venv: no media packages")'
python -m pip install --no-index --no-deps /artifacts/*.whl
ariadne --help
ariadne setup "$engine" --cache-dir "/work/$engine-bootstrap-cache" --fetch-models
python /scripts/ci_install_smoke.py "$engine" "/work/$engine-smoke" /fixtures
