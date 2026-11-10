"""Explicit maintainer-test setup of the official standalone C2PA validator."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import urllib.request

URL = 'https://github.com/contentauth/c2patool/releases/download/v0.28.6/v0.28.6-x86_64-unknown-linux-gnu.tar.gz'
SHA = 'e2dcd1cfcb872ee4f4cc4b353131615e09b608ed7cdea9f27a7f9d73d5d9af86'
root = Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=True)
archive = root / 'c2patool.tar.gz'
if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA:
    with urllib.request.urlopen(URL, timeout=120) as source:
        data = source.read(150 * 1024 * 1024 + 1)
    if len(data) > 150 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit('Official c2patool archive checksum/size mismatch')
    archive.write_bytes(data)
with tarfile.open(archive) as stream:
    members = [m for m in stream.getmembers() if m.isfile() and m.name == 'c2patool/c2patool']
    if len(members) != 1 or members[0].size > 150 * 1024 * 1024:
        raise SystemExit('Unexpected validator archive layout')
    # Extract the binary only, not upstream sample keys or arbitrary paths.
    binary = root / 'c2patool'
    binary.write_bytes(stream.extractfile(members[0]).read())
    binary.chmod(0o755)
print(json.dumps({'url': URL, 'archive_sha256': SHA, 'version': '0.28.6',
                  'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}))
