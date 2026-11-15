import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
r=Path('/data');p=r/'public/corpus.json';d=json.loads(p.read_text())
for name,sec,codec,negative in [('v720_10_hevc',10,'libx265',False),('v720_60_negative',60,'libx264',True)]:
 out=r/'inputs'/(name+'.mp4');cmd=['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=1280x720:rate=30','-t',str(sec),'-an','-c:v',codec,'-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-color_range','tv']
 if codec=='libx265':cmd+=['-x265-params','pools=2:frame-threads=2:log-level=error']
 cmd.append(str(out));subprocess.run(cmd,check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','quiet','-show_format','-show_streams','-of','json',str(out)]))
 d['items'].append(dict(id=name,kind='video',negative_only=negative,file=out.name,created_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),bytes=out.stat().st_size,preparation=cmd,ffprobe=probe))
p.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'inputs':len(d['items']),'extra':['HEVC10s codec control','60s clean-negative budget control']}))
