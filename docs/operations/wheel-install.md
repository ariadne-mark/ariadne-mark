# Install media from a wheel

Qualified environment: Linux x86-64, Python 3.12, FFmpeg/ffprobe and Node.js/npm.
Use a new virtualenv. The Docker recipe provisions the system prerequisites.
Download the exact wheel and SHA256SUMS from [Release 0.7.2a1](https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.2a1); verify the downloaded wheel hash before installation.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --no-deps /path/to/ariadne_mark-0.7.2a1-py3-none-any.whl
ariadne setup media --fetch-models
ariadne runtime check
```

This works outside the source checkout: full media/video locks and checksums
are package resources. Explicit setup bootstraps c2pa-python 0.38.3 / native
0.91.11, installs the selected hash-pinned CPU dependencies, runs `pip check`
and checks native qualification in a fresh process. Optional model provisioning
then verifies the pinned engines. Only this explicit setup may download files;
requests never invoke it. Start/restart media processes after installation.

The full-media setup builds the source-only TrustMark 0.9.2 package from its
locked archive hash, with pinned setuptools/wheel and no build isolation.
All other dependency installs require binary wheels; no unpinned build
dependencies are fetched for TrustMark.

`ariadne setup video --fetch-models` omits Torch, NumPy, Python TrustMark and
legacy decoders. It supports all three current video modes; unknown legacy
content cannot receive a complete across-scheme negative in that installation.

The `media`/`video` extras list convenience Python packages, not the qualified
wrapper or provisioning policy. Extras alone are not the recommended setup
and do not qualify models/native binaries. Do not downgrade C2PA to satisfy
an available index version; use the explicit pinned bootstrap.

Advanced setup options: `--cache-dir` for C2PA source/native/bootstrap downloads,
`--wheelhouse` for local dependency wheels (pip index disabled), `--allow-system`
only in an isolated container build. A wheelhouse does not populate the separate
C2PA source/native cache. Supply both caches for a network-disabled setup.
The normal setup command may use the network; subsequent export/verification
can be offline except an explicitly configured production TSA request.
