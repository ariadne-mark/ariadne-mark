"""Internal candidate build; dependencies are provisioned before offline tests."""
import json,subprocess,sys
from pathlib import Path
from ariadne_mark.bootstrap_c2pa import install
print(json.dumps(install(allow_system=True, wheel_dir='/opt/dist'),indent=2),flush=True)
subprocess.run([sys.executable,'scripts/build_release.py'],check=True)
