"""Current-release delivery observations; runs only on the experiment server."""
from pathlib import Path
import collections,csv,datetime,fcntl,hashlib,json,os,shutil,subprocess,sys,tarfile,time,traceback
import observe as o
R=o.R;D=o.D;O=o.O
for name in ['inputs','artifacts','registry','public','private']:
 (D/name).mkdir(parents=True,exist_ok=True);os.chown(D/name,1000,1000)
lock=open('/home/ubuntu/.ariadne-qualification.lock','a');fcntl.flock(lock,fcntl.LOCK_EX)
PROFILES=['economy_5s','economy_2s','resilient'];NAMES=['face','crowd','mixkit-1164','mixkit-5016']
PROTOCOL={'date':'2026-11-18','sdk':'0.7.3a4','runtime_source':'49578688710a8bae2373aaf9d47ff9521f566d4c','image':o.IMAGE,'threads':2,'container_memory_gib':4,'scenes':NAMES,'repeats':1,'profiles':PROFILES,'video_transforms':['unchanged','metadata_removed','h264_crf28','resize_480_crf23','trim_0.2_for_3s','center_crop_9_16'],'image_transforms':['unchanged','metadata_removed','jpeg_q90','jpeg_q75','resize_768_jpeg85','center_crop_80pct'],'scope':'Four retained stock scenes; one new watermark ID per scene/profile; not actual AI generation, named-social-platform testing, population estimates or legal pass criteria. Masters are not redistributed.','minimum_free_disk_gib':5}
o.save(R/'PROTOCOL.json',PROTOCOL)
rows=[];exports=[];errors=[];transform_log=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(args,label):
 start=time.monotonic()
 with (O/(label+'.stderr')).open('w') as err:r=subprocess.run(args,stdout=subprocess.PIPE,stderr=err,text=True,timeout=300)
 entry={'label':label,'argv':args,'exit':r.returncode,'wall_s':time.monotonic()-start};transform_log.append(entry)
 with (O/'commands.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n')
 if r.returncode:raise RuntimeError('Command failed: '+label)
 return r.stdout

def container(code,args,label):
 return command(['docker','run','--rm','--network','none','--cpus','2','--memory','1g','--user','1000:1000','-v',str(D)+':/data','--entrypoint','python',o.IMAGE,'-c',code,*args],label)
def save_results():
 with (O/'RESULTS.json').open('w') as f:json.dump(rows,f,indent=2)
 fields=['scene','kind','profile','transform','expected_token','observed_token','status','outcome','c2pa_status','c2pa_signature','wall_s','cpu_s','peak_mib','input_sha256','output_sha256']
 with (O/'RESULTS.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
 o.save(O/'EXPORTS.json',exports);o.save(O/'ERRORS.json',errors)

def transform(src,kind,name,profile,scene):
 if name=='unchanged':return src
 dest=src.parent/(name+('.mp4' if kind=='video' else '.jpg' if name.startswith(('jpeg','resize')) else '.png'))
 if kind=='video':
  args=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-i',str(src),'-map_metadata','-1','-an']
  if name=='metadata_removed':args+=['-c:v','copy']
  else:
   if name=='trim_0.2_for_3s':args+=['-ss','0.2','-t','3']
   if name=='resize_480_crf23':args+=['-vf','scale=-2:480']
   if name=='center_crop_9_16':args+=['-vf','crop=trunc(ih*9/16/2)*2:ih']
   args+=['-c:v','libx264','-threads','2','-preset','fast','-crf','28' if name=='h264_crf28' else '23','-pix_fmt','yuv420p','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-color_range','tv']
  command(args+[str(dest)],'transform-'+scene+'-'+profile+'-'+name)
 else:
  code="""from PIL import Image
from pathlib import Path
import sys
p,q,k=sys.argv[1:];im=Image.open(p).convert('RGB')
if k=='resize_768_jpeg85':im.thumbnail((768,768),Image.Resampling.LANCZOS)
if k=='center_crop_80pct':
 w,h=im.size;im=im.crop((int(w*.1),int(h*.1),int(w*.9),int(h*.9)))
kwargs={'quality':90 if k=='jpeg_q90' else 75 if k=='jpeg_q75' else 85,'subsampling':2} if q.endswith('.jpg') else {}
im.save(q,**kwargs)
"""
  container(code,[str(Path('/data')/src.relative_to(D)),str(Path('/data')/dest.relative_to(D)),name],'transform-'+scene+'-'+name)
 return dest

try:
 assert shutil.disk_usage(R).free>5*2**30
 sources=[]
 for scene in NAMES:
  original=Path('/home/ubuntu/ariadne-review-071a1-20261109/inputs/clean')/('stock_'+scene+'.mp4');assert original.is_file()
  vp=D/'inputs'/(scene+'.mp4');shutil.copy2(original,vp)
  ip=D/'inputs'/(scene+'.png')
  command(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-ss','1','-i',str(vp),'-frames:v','1','-vf','scale=1024:-2','-threads','2','-map_metadata','-1',str(ip)],'extract-'+scene)
  probe=json.loads(command(['ffprobe','-v','quiet','-show_format','-show_streams','-of','json',str(vp)],'probe-'+scene))
  sources.append({'scene':scene,'original_sha256':sha(original),'video_sha256':sha(vp),'image_sha256':sha(ip),'original_path':str(original),'ffprobe':probe})
 o.save(R/'CORPUS.json',{'items':sources,'distribution':'Source stock files are excluded from public evidence; hashes and preparation commands retained.'})
 container("from pathlib import Path;from ariadne_mark.signing import create_development_identity;from ariadne_mark.registry import Registry;create_development_identity(Path('/data/private/identity'));Registry(Path('/data/registry/assets.sqlite3'));Path('/data/public/trust.pem').write_bytes(Path('/data/private/identity/trust.pem').read_bytes())",[],'initialize')
 encoder=o.Session('delivery-export',exporter=True)
 try:
  for scene in NAMES:
   for kind in ['image','video']:
    for profile in (['image'] if kind=='image' else PROFILES):
     target=D/'artifacts'/scene/profile;target.mkdir(parents=True);os.chown(target,1000,1000)
     src=D/'inputs'/(scene+('.mp4' if kind=='video' else '.png'));dest=target/('marked.mp4' if kind=='video' else 'marked.png')
     row=encoder.request({'id':'export-'+scene+'-'+profile,'op':'mark','exporter':True,'kind':kind,'case':scene,'profile':profile,'scope':'current','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'/inputs/'+src.name,'destination':'/artifacts/'+str(dest.relative_to(D/'artifacts'))})
     if not row['worker']['ok']:
      errors.append({'stage':'export','scene':scene,'profile':profile,'error':row['worker'].get('message')});save_results();continue
     receipt=row['worker']['receipt'];assert sha(dest)==receipt['sha256']
     exports.append({'scene':scene,'kind':kind,'profile':profile,'file':str(dest),'sha256':sha(dest),'token':receipt['token']});save_results()
 finally:encoder.close()
 # Materialize every distinct pixel/codec transformation; no replay of image changes.
 tasks=[]
 for e in exports:
  src=Path(e['file']);spec=PROTOCOL['video_transforms'] if e['kind']=='video' else PROTOCOL['image_transforms']
  for variant in spec:
   try:
    transformed=transform(src,e['kind'],variant,e['profile'],e['scene']);tasks.append((e,variant,transformed))
   except Exception as exc:errors.append({'stage':'transform','scene':e['scene'],'profile':e['profile'],'transform':variant,'error':repr(exc)});save_results()
 verifier=o.Session('delivery-independent-verifier',exporter=False)
 try:
  for e,variant,path in tasks:
   row=verifier.request({'id':'verify-'+e['scene']+'-'+e['profile']+'-'+variant.replace('.','_'),'op':'verify','case':e['scene'],'profile':e['profile'],'scope':'current','source':'/artifacts/'+str(path.relative_to(D/'artifacts'))})
   report=row['worker'].get('report',{});w=report.get('watermark',{});c=report.get('c2pa',{});observed=w.get('token');status=w.get('status','engine_error')
   outcome='correct_id' if observed==e['token'] else 'incomplete' if status=='not_checked' else 'wrong_id' if observed else 'completed_negative' if status=='not_found' else status
   rows.append({'scene':e['scene'],'kind':e['kind'],'profile':e['profile'],'transform':variant,'expected_token':e['token'],'observed_token':observed,'status':status,'outcome':outcome,'c2pa_status':c.get('status'),'c2pa_signature':c.get('signature'),'wall_s':row['wall_s'],'cpu_s':row['cpu_s'],'peak_mib':row['memory_peak_bytes']/2**20,'input_sha256':e['sha256'],'output_sha256':sha(path),'measurement_file':row['id']+'.json'})
   save_results()
 finally:verifier.close()
 status='completed' if not errors else 'completed_with_errors'
except Exception as exc:
 errors.append({'stage':'campaign','error':repr(exc),'traceback':traceback.format_exc()});status='failed';save_results();raise
finally:
 save_results()
 o.save(O/'SUMMARY.json',{'status':locals().get('status','failed'),'exports':len(exports),'observations':len(rows),'outcomes':dict(collections.Counter(x['outcome'] for x in rows)),'errors':len(errors),'sdk':'0.7.3a4','profiles':PROFILES})
 with tarfile.open(R/'PUBLIC_EVIDENCE.tar.gz','w:gz') as t:
  for name in ['PROTOCOL.json','CORPUS.json','results','logs','scripts']:t.add(R/name,arcname=name)
 os.chmod(R/'PUBLIC_EVIDENCE.tar.gz',0o644)
 print(json.dumps({'event':'campaign_finished','status':locals().get('status','failed'),'observations':len(rows),'errors':len(errors)}),flush=True)
