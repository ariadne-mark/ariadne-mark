"""Summarize mixed/idle/session accounting from recorded data, no SDK execution."""
from pathlib import Path
import collections,csv,json,sys
root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
mixed=root/'results/mixed-v1';idle=root/'results/idle-v1'
summary={'mixed':json.loads((mixed/'COMPLETE.json').read_text()),'idle':json.loads((idle/'COMPLETE.json').read_text())}
rows=[json.loads(x) for x in (mixed/'measurements.jsonl').read_text().splitlines() if json.loads(x)['op']!='close']
flat=[{'id':r['id'],'operation':r['op'],'case':r['case'],'profile':r['profile'],'wall_s':r['wall_s'],'cpu_s':r['cpu_s'],'kernel_peak_mib':r['memory_peak_bytes']/2**20,'memory_start_mib':r['memory_start_bytes']/2**20,'memory_end_mib':r['memory_end_bytes']/2**20,'note':'First image / first video engine explicitly named in ID; supplementary mixed resident session, not pooled into primary cold/warm medians'} for r in rows]
with (out/'MIXED_CONTROL.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
summary['mixed']['max_kernel_peak_mib']=max(r['kernel_peak_mib'] for r in flat)
summary['mixed']['operations']=flat
summary['idle']['average_cpu_cores']=summary['idle']['full_cgroup_cpu_s']/summary['idle']['wall_s']
(out/'SUPPLEMENT.json').write_text(json.dumps(summary,indent=2)+'\n')
sessions=[]
for folder in [root/'results/main',mixed,idle]:
 records=[json.loads(x) for x in (folder/'measurements.jsonl').read_text().splitlines()]
 grouped=collections.defaultdict(list)
 for r in records:grouped[r['session']].append(r)
 for infofile in folder.glob('*.container.json'):
  info=json.loads(infofile.read_text());data=grouped[info['label']]
  closing=next(x for x in data if x['op']=='close')
  timeline=folder/(closing['id']+'.timeline.jsonl');last=json.loads(timeline.read_text().splitlines()[-1])
  total=last['cpu']['usage_usec']/1e6
  timed=sum(r['cpu_s'] for r in data)
  gap=total-timed-info['startup_cpu_s']
  sessions.append({'group':folder.name,'session':info['label'],'requests':len(data),'startup_wall_s':info['startup_wall_s'],'startup_cpu_s':info['startup_cpu_s'],'timed_requests_cpu_s':timed,'session_cpu_through_shutdown_sample_s':total,'between_requests_or_boundary_cpu_s':gap,'gap_fraction':gap/total if total else 0,'note':'Final timeline sample precedes result serialization by milliseconds; tiny negative gaps are boundary/clock accounting, not negative work. Excludes Docker daemon and external host observer.'})
with (out/'SESSION_ACCOUNTING.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(sessions[0]));w.writeheader();w.writerows(sessions)
print(json.dumps({'mixed_max_peak_mib':summary['mixed']['max_kernel_peak_mib'],'idle':summary['idle'],'session_accounting_rows':len(sessions)},indent=2))
