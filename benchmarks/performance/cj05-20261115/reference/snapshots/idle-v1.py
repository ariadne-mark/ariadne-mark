"""Supplement: resident idle CPU/RAM after image and video models load."""
from pathlib import Path
import fcntl,json,sys
R=Path('/home/ubuntu/ariadne-cj05-20261115');sys.path.insert(0,str(R/'snapshots/main-v1'))
import observe as o
o.S=R/'snapshots/main-v1';o.O=R/'results/idle-v1';o.O.mkdir(exist_ok=False)
lock=open('/home/ubuntu/.ariadne-qualification.lock','a');fcntl.flock(lock,fcntl.LOCK_EX)
items={x['id']:x for x in json.loads((o.D/'public/corpus.json').read_text())['items']}
s=None
try:
 s=o.Session('resident-idle',exporter=True)
 for case,profile in [('i1024_png','image'),('v720_10_30','economy_5s')]:
  item=items[case]
  row=s.request({'id':'idle-setup-'+case,'op':'mark','case':case,'kind':item['kind'],'profile':profile,'scope':'current','exporter':True,'iteration':None,'created_at':item['created_at'],'source':'/inputs/'+item['file'],'destination':'/artifacts/idle-v1/'+item['file']})
  assert row['worker']['ok']
 before=o.snapshot(s.cg);start=o.time.monotonic();peaks=[]
 for i in range(20):
  row=s.request({'id':'idle-window-'+str(i),'op':'noop','iteration':i,'case':None,'profile':None,'scope':'current'})
  assert row['worker']['ok'];peaks.append(row['memory_peak_bytes'])
 after=o.snapshot(s.cg)
 result={'status':'passed','purpose':'Resident SDK after both modalities; twenty 250ms sleep requests, no media work in this interval; IPC/measurement included as upper-bound idle overhead',
   'wall_s':o.time.monotonic()-start,'full_cgroup_cpu_s':(after['cpu']['usage_usec']-before['cpu']['usage_usec'])/1e6,
   'memory_start_mib':before['memory_bytes']/2**20,'memory_end_mib':after['memory_bytes']/2**20,'max_kernel_peak_mib':max(peaks)/2**20}
 o.save(o.O/'COMPLETE.json',result);o.emit('idle_complete',**result)
finally:
 if s:s.close()
