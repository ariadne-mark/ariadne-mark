"""Supplementary mixed-image/video resident SDK check; same frozen observer/worker."""
from pathlib import Path
import fcntl,json,sys,traceback
R=Path('/home/ubuntu/ariadne-cj05-20261115');sys.path.insert(0,str(R/'snapshots/main-v1'))
import observe as o
o.S=R/'snapshots/main-v1';o.O=R/'results/mixed-v1';o.O.mkdir(exist_ok=False)
lock=open('/home/ubuntu/.ariadne-qualification.lock','a');fcntl.flock(lock,fcntl.LOCK_EX)
corpus={x['id']:x for x in json.loads((o.D/'public/corpus.json').read_text())['items']}
plan=[('first_image','i1024_png','image'),('first_video_engine','v720_10_30','economy_5s'),
 ('warm_image','i1024_png','image'),('warm_video','v720_10_30','economy_5s'),
 ('switch_economy2','v720_10_30','economy_2s'),('large_image','i2048_jpeg','image'),
 ('switch_resilient','v720_5_24','resilient')]
o.save(o.O/'SCHEDULE.json',{'purpose':'One persistent SDK after both image and video engines load; profile switching shares Node; supplementary to independent-process primary matrix','schedule':plan,'negative_after_both_models':True,'protocol':'CJ05 mixed amendment2; no runtime changes'})
s=None;marked={};node_pids=[]
try:
 s=o.Session('mixed-modalities',exporter=True)
 for stage,case,profile in plan:
  item=corpus[case];destination=f'/artifacts/mixed-v1/{stage}'+Path(item['file']).suffix
  row=s.request({'id':'mixed-'+stage,'op':'mark','case':case,'profile':profile,'scope':'current','iteration':None,'exporter':True,'kind':item['kind'],'created_at':item['created_at'],'source':'/inputs/'+item['file'],'destination':destination})
  assert row['worker']['ok'],row['worker'];marked[stage]=(destination,row['worker']['receipt']['token'])
  processes=o.snapshot(s.cg)['processes'];node_pids.append({'stage':stage,'node_pids':[p['pid'] for p in processes if p['role']=='node']})
 for stage in ['warm_image','warm_video','switch_resilient']:
  source,token=marked[stage];case=next(case for name,case,p in plan if name==stage)
  row=s.request({'id':'mixed-verify-'+stage,'op':'verify','case':case,'profile':'image' if case.startswith('i') else 'resilient' if stage=='switch_resilient' else 'economy_5s','scope':'current','iteration':None,'source':source})
  assert row['worker']['ok'] and row['worker']['report']['watermark'].get('token')==token
 item=corpus['v720_10_30'];negative=s.request({'id':'mixed-negative-video','op':'verify','case':item['id'],'profile':None,'scope':'current','iteration':None,'source':'/inputs/'+item['file']})
 assert negative['worker']['ok'] and negative['worker']['report']['watermark']['status']=='not_found'
 active=[x['node_pids'] for x in node_pids if x['node_pids']]
 assert active and all(len(x)==1 and x==active[0] for x in active),active
 o.save(o.O/'COMPLETE.json',{'status':'passed','marks':7,'positive_verifications':3,'clean_negative':1,'node_pids_by_stage':node_pids,'one_shared_node_across_profiles':True,'scope':'Supplementary mixed resident process; not independent verifier/public HTTP workload'})
 o.emit('mixed_complete',one_shared_node_across_profiles=True)
except Exception as e:
 o.save(o.O/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc()});o.emit('mixed_failed',error=repr(e));raise
finally:
 if s:s.close()
