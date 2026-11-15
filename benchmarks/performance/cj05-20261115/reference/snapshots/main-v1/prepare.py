"""Prepare deterministic private engineering inputs using the qualified image."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
from PIL import Image
from ariadne_mark.signing import create_development_identity
from ariadne_mark.registry import Registry
r=Path('/data');p=json.loads(Path('/scripts/PROTOCOL.json').read_text());rows=[]
for name in ['inputs','artifacts','registry','public','private']:(r/name).mkdir(exist_ok=True)
if not (r/'private/identity').exists():
 create_development_identity(r/'private/identity')
else:
 from ariadne_mark.signing import SigningIdentity
 assert SigningIdentity.from_directory(r/'private/identity',allow_dev=True).development
(r/'public/trust.pem').write_bytes((r/'private/identity/trust.pem').read_bytes())
Registry(r/'registry/assets.sqlite3')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for name,size,ext in [('i1024_png',(1024,683),'.png'),('i2048_jpeg',(2048,1152),'.jpg')]:
 im=Image.new('RGB',size);pix=im.load()
 for y in range(size[1]):
  for x in range(size[0]):pix[x,y]=((3*x+5*y+x*y%37)%256,(x+2*y+x*y%71)%256,(2*x+3*y)%256)
 path=r/'inputs'/(name+ext);kwargs={'quality':95,'subsampling':0} if ext=='.jpg' else {};im.save(path,**kwargs)
 rows.append(dict(id=name,kind='image',file=path.name,width=size[0],height=size[1],sha256=digest(path),bytes=path.stat().st_size,created_at=datetime.now(timezone.utc).isoformat(),preparation='Pillow RGB modular texture: R=(3x+5y+xy%37)%256,G=(x+2y+xy%71)%256,B=(2x+3y)%256; JPEG quality95 subsampling0'))
for v in p['corpus']['videos']:
 path=r/'inputs'/(v['id']+'.mp4')
 cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi','-i',f"testsrc2=size={v['size']}:rate={v['fps']}",'-t',str(v['duration_s']),'-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-color_range','tv',str(path)]
 subprocess.run(cmd,check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','quiet','-show_format','-show_streams','-of','json',str(path)]))
 rows.append(dict(id=v['id'],kind='video',file=path.name,sha256=digest(path),bytes=path.stat().st_size,created_at=datetime.now(timezone.utc).isoformat(),preparation=cmd,ffprobe=probe))
(r/'public/corpus.json').write_text(json.dumps({'source':'own deterministic engineering fixtures; not actual AI-generated media; no stock originals redistributed','items':rows},indent=2)+'\n')
print(json.dumps({'status':'prepared','inputs':len(rows),'bytes':sum(x['bytes'] for x in rows)}))
