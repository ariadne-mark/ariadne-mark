"""Inventory actual PyAV bundled binaries separately from system FFmpeg."""
import hashlib,importlib.metadata,json,subprocess
from pathlib import Path
import av,c2pa
packages=Path(av.__file__).parent
candidates=[packages.parent/'av.libs',packages/'.dylibs',packages/'libs',Path(c2pa.__file__).parent/'libs']
files={}
for directory in candidates:
 if directory.exists():
  for p in sorted(directory.rglob('*')):
   if p.is_file():files[str(p.relative_to(packages.parent))]={'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'bytes':p.stat().st_size}
print(json.dumps({'pyav':importlib.metadata.version('av'),'pyav_ffmpeg_libraries':{n:list(v) for n,v in av.library_versions.items()},'system_ffmpeg_version':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],'bundled_native_files':files,'note':'Binary inventory/hashes, not a complete native vulnerability scan or a zero-CVE claim.'},indent=2))
