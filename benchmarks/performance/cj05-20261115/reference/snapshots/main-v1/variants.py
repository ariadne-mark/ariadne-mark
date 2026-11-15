"""Unmeasured metadata-loss preparation; keep codec/pixel checks and commands."""
import hashlib,json,subprocess,sys
from pathlib import Path
from PIL import Image
from ariadne_mark.verification.media import inspect_c2pa
source=Path(sys.argv[1]);dest=Path(sys.argv[2]);dest.parent.mkdir(parents=True,exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if source.suffix=='.mp4':
    cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-i',str(source),'-map','0:v:0','-c:v','copy','-map_metadata','-1','-an','-movflags','+faststart',str(dest)]
    subprocess.run(cmd,check=True)
    def essence(p):return subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(p),'-map','0:v:0','-c:v','copy','-f','hash','-hash','sha256','-'],text=True).strip()
    left,right=essence(source),essence(dest);assert left==right,(left,right)
    details={'method':'MP4 stream-copy remux; video packet essence hash unchanged','command':cmd,'essence_hash':left}
else:
    with Image.open(source) as im:im=im.convert('RGB');left=hashlib.sha256(im.tobytes()).hexdigest();im.save(dest)
    with Image.open(dest) as im:right=hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()
    assert left==right
    details={'method':'Decoded RGB saved as PNG without metadata; JPEG input has no further lossy encode','rgb_sha256':left}
status=inspect_c2pa(dest);assert status['status']=='not_found',status
print(json.dumps({'source':str(source),'destination':str(dest),'source_sha256':digest(source),'output_sha256':digest(dest),'c2pa_status':status['status'],**details}))
