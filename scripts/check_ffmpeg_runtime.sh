#!/bin/bash
# Container build gate. Check actual binaries and Python wheel libraries.
set -euo pipefail

ffmpeg -version
ffprobe -version
python - <<'PY'
from pathlib import Path
import ctypes
import subprocess

import av

wheel_libraries = sorted((Path(av.__file__).parent.parent / 'av.libs').glob('*.so*'))
if not wheel_libraries:
    raise SystemExit('The qualified runtime requires the pinned PyAV binary wheel')
avutil = next(path for path in wheel_libraries if path.name.startswith('libavutil-'))
version = ctypes.CDLL(str(avutil)).av_version_info
version.restype = ctypes.c_char_p
actual = version().decode('ascii')
print(f'PyAV {av.__version__}, bundled FFmpeg {actual}')
if (av.__version__, actual) != ('19.0.2', '9.0.2'):
    raise SystemExit('Unexpected PyAV/FFmpeg runtime pair')

for binary in ('/usr/local/bin/ffmpeg', '/usr/local/bin/ffprobe', *wheel_libraries):
    links = subprocess.check_output(['ldd', str(binary)], text=True).lower()
    if 'libxml2' in str(binary).lower() or 'libxml2' in links or 'not found' in links:
        raise SystemExit(f'Unexpected XML or unresolved dependency in {binary}')
PY

if dpkg-query -W -f='${binary:Package}\t${db:Status-Status}\n' |
    awk '$1 ~ /^libxml2($|[-0-9.:])/ && $2 == "installed" { present=1 } END { exit !present }'; then
    echo 'The qualified media container must not include a Debian libxml2 package' >&2
    exit 1
fi
