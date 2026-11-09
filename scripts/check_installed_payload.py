"""Run in the built image: source / wheel / installed / sdist package parity."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import zipfile
artifacts=Path(sys.argv[1]);source=Path(sys.argv[2])/'src'
installed=Path(importlib.util.find_spec('ariadne_mark').origin).parent
assert 'site-packages' in installed.parts,installed
wheel,=artifacts.glob('*.whl');sdist,=artifacts.glob('*.tar.gz')
payload={}
with zipfile.ZipFile(wheel) as stream:
    for name in stream.namelist():
        if name.startswith('ariadne_mark/') and not name.endswith('/'):
            data=stream.read(name)
            assert data==(source/name).read_bytes(),('source mismatch',name)
            assert data==(installed/Path(name).relative_to('ariadne_mark')).read_bytes(),('installed mismatch',name)
            payload[name]=data
with tarfile.open(sdist) as stream:
    members={m.name.split('/src/',1)[1]:m for m in stream.getmembers() if '/src/ariadne_mark/' in m.name and m.isfile()}
    for name,data in payload.items():assert stream.extractfile(members[name]).read()==data,('sdist mismatch',name)
print(json.dumps({'ok':True,'package_files_matched':len(payload),'installed_root':str(installed),
                  'payload_sha256':{n:hashlib.sha256(v).hexdigest() for n,v in payload.items()}},indent=2))
