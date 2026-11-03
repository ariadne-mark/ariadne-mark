"""Repeated random-payload video qualification; creates local development keys."""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,time,statistics
import av,numpy as np
from ariadne_mark.pipeline import SDK
from ariadne_mark.provenance import *
from ariadne_mark.signing import *
from ariadne_mark.watermark import Watermarker
import argparse
parser=argparse.ArgumentParser(description='Eight random video payloads: read-back and frame PSNR')
parser.add_argument('output',type=Path)
p=parser.parse_args().output
p.mkdir(parents=True,exist_ok=False)
create_development_identity(p/'identity')
sdk=SDK(Watermarker(),SigningIdentity.from_directory(p/'identity',allow_dev=True))
source=p/'source.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x512:rate=12:duration=2','-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True)
rows=[]
for n in range(8):
 out=p/f'output-{n}.mp4'
 record=ProvenanceRecord.create(publisher='Stress fixture',system=GenerativeSystem('Procedural','1'),media_kind=MediaKind.VIDEO,action=Action.CREATED,created_at=datetime.now(timezone.utc))
 try:
  receipt=sdk.mark(source,out,record)
  quality=[]
  with av.open(str(source)) as a,av.open(str(out)) as b:
   for x,y in zip(a.decode(video=0),b.decode(video=0)):
    mse=np.mean((x.to_ndarray(format='rgb24').astype(float)-y.to_ndarray(format='rgb24').astype(float))**2)
    quality.append(float(10*np.log10(255**2/mse)))
  rows.append({'trial':n,'passed':True,'token':receipt['token'],'seconds':receipt['seconds'],'mean_frame_psnr_db':round(statistics.mean(quality),2),'min_frame_psnr_db':round(min(quality),2)})
 except Exception as e:rows.append({'trial':n,'passed':False,'error':str(e)})
 print(json.dumps(rows[-1]),flush=True)
result={'scope':'8 random payloads on the same 2s vertical fixture; not a population robustness guarantee','video_strength':1.5,'h264_crf':18,'rows':rows}
(p/'report.json').write_text(json.dumps(result,indent=2))
if not all(r['passed'] for r in rows):raise SystemExit(1)
