"""Installed-wheel media integration in a fresh isolated venv, outside source."""
from datetime import datetime,timezone
import importlib.util
from importlib.metadata import distributions,version
import json
from pathlib import Path
import sys
import time
engine=sys.argv[1];root=Path(sys.argv[2]);fixtures=Path(sys.argv[3])
root.mkdir(parents=True,exist_ok=True)
import ariadne_mark
assert Path(ariadne_mark.__file__).resolve().is_relative_to(Path(sys.prefix))
if engine=='video':
    for name in ['torch','numpy','trustmark']:assert importlib.util.find_spec(name) is None,name
from ariadne_mark.pipeline import SDK
from ariadne_mark.provenance import ProvenanceRecord,GenerativeSystem,MediaKind,Action
from ariadne_mark.signing import create_development_identity,SigningIdentity
from ariadne_mark.isolated_verifier import IsolatedVerifier
create_development_identity(root/'identity')
identity=SigningIdentity.from_directory(root/'identity',allow_dev=True)
print(json.dumps({'kind':'environment','engine':engine,'sdk':version('ariadne-mark'),
    'python':sys.version,'prefix':sys.prefix,'packages':{d.metadata['Name']:d.version for d in distributions()}}),flush=True)
with SDK(identity=identity) as sdk:
    cases=([(None,'input.png','image')] if engine=='media' else [])+[(p,'input.mp4','video') for p in ['economy_5s','economy_2s','resilient']]
    for profile,name,kind in cases:
        record=ProvenanceRecord.create(publisher='Install smoke fixture',system=GenerativeSystem('Deterministic fixture','1'),
            media_kind=MediaKind(kind),action=Action.CREATED,created_at=datetime.now(timezone.utc))
        output=root/((profile or 'image')+Path(name).suffix);started=time.monotonic()
        receipt=sdk.mark(fixtures/name,output,record,video_profile=profile,audio_kind='none')
        report=sdk.verify(output)
        assert report['c2pa']['status']=='verified_claim',report
        assert report['watermark']['token']==receipt['token'],report
        print(json.dumps({'kind':'export_verify','engine':engine,'profile':profile,'ok':True,
                          'wall_s':time.monotonic()-started,'receipt':receipt,'report':report}),flush=True)
with IsolatedVerifier(timeout=120) as verifier:
    verifier.check_runtime()
    assert verifier._process is None
    report=verifier.verify(output)
    assert report['watermark']['token']==receipt['token']
if engine=='video':
    for name in ['torch','numpy','trustmark']:assert importlib.util.find_spec(name) is None,name
print(json.dumps({'kind':'complete','engine':engine,'ok':True}),flush=True)
