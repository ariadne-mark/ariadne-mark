"""Static source/package lock consistency; no SDK import or provisioning."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
package=root/'src/ariadne_mark'
pins=json.loads((package/'runtime-locks.json').read_text())['locks']
for name,entry in pins.items():
    raw=(package/entry['filename']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==entry['sha256'],name
assert (package/pins['media']['filename']).read_bytes()==(root/'requirements/media-linux-py312.lock').read_bytes()
def requirements(path):
    return {line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')}
assert requirements(package/pins['video']['filename']) == (
    requirements(package/'bootstrap-linux-py312.lock') | requirements(root/'requirements/video-linux-py312.lock'))
print('OK: packaged media/video hash locks match their manifests and source policy')
