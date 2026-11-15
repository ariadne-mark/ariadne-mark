"""Post-run metadata only. Never runs alongside timed workloads."""
import json,subprocess,sys
from pathlib import Path
r=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
image='sha256:1a4dd358bcf698df654daaac631a26d3bc874104de5108bc94ce941c33a49980'
code='''import av,importlib.metadata as m,json,platform,sys
packages={}
for name in ["ariadne-mark","av","Pillow","trustmark","torch","numpy","c2pa-python"]:
 try:packages[name]=m.version(name)
 except m.PackageNotFoundError:packages[name]=None
print(json.dumps({"python":sys.version,"platform":platform.platform(),"packages":packages,"pyav_ffmpeg_libraries":av.library_versions},indent=2))'''
result=subprocess.run(['docker','run','--rm','--name','ariadne-cj05-post-inventory','--network','none','--read-only','--cpus','2','--memory','512m','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--entrypoint','python',image,'-c',code],text=True,capture_output=True,check=True)
data=json.loads(result.stdout);data.update(image=image,node=(r/'results/node-version.txt').read_text().strip(),ffmpeg_cli=(r/'results/ffmpeg-version.txt').read_text().splitlines()[0],c2pa_qualification=json.loads((r/'results/runtime-check.json').read_text()),machine=json.loads((r/'results/MACHINE.json').read_text()))
data['post_run_host_memory_inventory_bytes']={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','SwapTotal:','SwapFree:'))}
detail=json.loads((r/'results/qualified-image.json').read_text());detail=detail[0] if isinstance(detail,list) else detail
data['docker_image_reported_size_bytes']=detail.get('Size')
data['notes']=['Collected after all timing; importing metadata/PyAV only, no SDK inference.','FFmpeg CLI and PyAV-linked FFmpeg versions are distinct and are reported separately.','Docker image size is not unique disk space, install traffic or RAM.']
(out/'RUNTIME.json').write_text(json.dumps(data,indent=2)+'\n')
(out/'post-inventory.stderr').write_text(result.stderr)
print(json.dumps(data,indent=2))
