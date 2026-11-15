"""Post-run analysis of recorded metrics only; no SDK import or media processing."""
import collections,csv,hashlib,json,math,statistics,sys
from pathlib import Path
root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
raw=root/'results/main'
if not (raw/'COMPLETE.json').is_file():raise SystemExit('Primary campaign is not complete; no final summary produced')
completion=json.loads((raw/'COMPLETE.json').read_text())
rows=[json.loads(x) for x in (raw/'measurements.jsonl').read_text().splitlines()]
corpus=json.loads((root/'data/public/corpus.json').read_text());items={x['id']:x for x in corpus['items']}

def kind(r):
 i=r['id']
 group='speed_control' if i.startswith('speedcontrol-') else 'all_scope_control' if i.startswith('all-') else 'budget_control' if i.startswith('budget-') else 'matrix'
 if r['op']=='mark':op='export'
 elif 'metadata_loss' in i:op='verify_metadata_loss'
 elif 'negative' in i:op='verify_negative'
 elif r['op']=='verify':op='verify_positive'
 else:op=r['op']
 return group,op

def expectation(r):
 group,op=kind(r)
 if op not in ['verify_positive','verify_metadata_loss']:return None
 if group=='speed_control':key=f'speedcontrol-export-r{r["iteration"]}'
 else:key=f'export-{r["case"]}-{r["profile"]}-r{r["iteration"]}'
 return indexed.get(key,{}).get('worker',{}).get('receipt',{}).get('token')
indexed={r['id']:r for r in rows};flat=[];quality=[]
for r in rows:
 if r['op']=='close':continue
 group,op=kind(r);w=r['worker'];report=w.get('report',{});watermark=report.get('watermark',{});c2pa=report.get('c2pa',{})
 expected=expectation(r);status=watermark.get('status');found=watermark.get('token')
 if not w.get('ok'):outcome='operational_error'
 elif op=='export':outcome='accepted_export'
 elif op in ['verify_positive','verify_metadata_loss']:outcome='correct_id' if expected and found==expected else 'wrong_id' if found else status or 'unknown'
 else:outcome='completed_negative' if status=='not_found' else 'incomplete' if status=='not_checked' else 'unexpected_id' if found else status or 'unknown'
 item=items.get(r['case'],{})
 export_row=indexed.get(f'speedcontrol-export-r{r["iteration"]}' if group=='speed_control' else f'export-{r["case"]}-{r["profile"]}-r{r["iteration"]}',{})
 artifact_sha=w.get('receipt',{}).get('sha256') if op=='export' else item.get('sha256') if op=='verify_negative' else export_row.get('worker',{}).get('receipt',{}).get('sha256')
 if op=='verify_metadata_loss':
  variant=raw/(f'variant-{r["case"]}-{r["profile"]}-{r["iteration"]}.json')
  if variant.exists():artifact_sha=json.loads(variant.read_text())['output_sha256']
 attempts=[]
 for a in watermark.get('attempts',[]):
  a={k:v for k,v in a.items() if k not in {'samples','observations','aggregates','logits'}}
  if isinstance(a.get('search'),dict):
   a['search']={**a['search']};ag=a['search'].pop('aggregate_attempts',None)
   if ag is not None:a['search']['aggregate_attempts_count']=len(ag)
  attempts.append(a)
 scan=next((a.get('search',{}) for a in attempts if a.get('algorithm')=='adobe.trustmark.Q.variax-bch5' and a.get('search')),watermark.get('search') or {})
 q={'input_sha256':item.get('sha256'),'artifact_sha256':artifact_sha,'id':r['id'],'group':group,'operation':op,'outcome':outcome,'expected_id':expected,'found_id':found,'watermark_status':status,'watermark_reason':watermark.get('reason'),'c2pa_signature':c2pa.get('signature'),'c2pa_status':c2pa.get('status'),'search':scan,'attempts':attempts,'evidence_scope':watermark.get('evidence_scope'),'recovery_status':report.get('recovery',{}).get('status')};quality.append(q)
 item=items.get(r['case'],{});probe=item.get('ffprobe',{});video=next((s for s in probe.get('streams',[]) if s.get('codec_type')=='video'),{})
 sampled_anon=sampled_file=0
 timeline=raw/(r['id']+'.timeline.jsonl')
 if timeline.exists():
  with timeline.open() as stream:
   for line in stream:
    point=json.loads(line);sampled_anon=max(sampled_anon,point.get('anon_bytes',0));sampled_file=max(sampled_file,point.get('file_bytes',0))
 row={'id':r['id'],'group':group,'operation':op,'case':r['case'],'profile':r['profile'] or 'not_applicable','scope':r['scope'],'temperature':r['temperature'],'iteration':r['iteration'],
  'width':video.get('width',item.get('width')),'height':video.get('height',item.get('height')),'duration_s':video.get('duration'),'fps':video.get('avg_frame_rate'),'codec':video.get('codec_name',Path(item.get('file','')).suffix.lstrip('.')),
  'outcome':outcome,'input_sha256':item.get('sha256'),'artifact_sha256':artifact_sha,'input_file_bytes':item.get('bytes'),'frames_encoded':w.get('receipt',{}).get('video',{}).get('frames_encoded'),'marked_frames':w.get('receipt',{}).get('video',{}).get('marked_frames'),'watermark_status':status,'worker_ok':w.get('ok'),
  'receipt_encoder_inference_s':w.get('receipt',{}).get('video',{}).get('watermark_stats',{}).get('inference_s'),'receipt_encoder_inference_calls':w.get('receipt',{}).get('video',{}).get('watermark_stats',{}).get('inference_calls'),
  'verification_reason':watermark.get('reason'),'scan_frames_decoded':scan.get('frames_decoded'),'scan_file_exhausted':scan.get('file_exhausted'),'scan_hypotheses_complete':scan.get('hypotheses_complete'),'scan_budget_seconds':scan.get('max_seconds'),'scan_stop_reason':scan.get('reason'),
  'wall_s':r['wall_s'],'sdk_call_s':w.get('sdk_call_s'),'sdk_init_s':w.get('sdk_init_s'),'worker_operation_s':w.get('worker_operation_s'),'total_cgroup_cpu_s':r['cpu_s'],
  'cgroup_user_cpu_s':r['cpu_stat_delta'].get('user_usec',0)/1e6,'cgroup_system_cpu_s':r['cpu_stat_delta'].get('system_usec',0)/1e6,
  'average_cpu_cores':r['cpu_s']/r['wall_s'],'python_process_cpu_s':w.get('python_self_cpu_s'),
  'live_node_cpu_s':r.get('live_child_cpu_delta_s',{}).get('node',0),'reaped_child_cpu_s':w.get('reaped_children_cpu_s'),
  'cpu_accounting_difference_s':r['cpu_accounting_difference_s'],'observer_cpu_s':r['observer_cpu_s'],'observer_cpu_fraction_of_wall':r['observer_cpu_s']/r['wall_s'],
  'memory_peak_mib':r['memory_peak_bytes']/2**20,'memory_start_mib':r['memory_start_bytes']/2**20,'memory_end_mib':r['memory_end_bytes']/2**20,
  'sampled_anon_peak_mib':sampled_anon/2**20,'sampled_file_charge_peak_mib':sampled_file/2**20,'sampled_cgroup_peak_mib':r['sampled_memory_peak_bytes']/2**20,'sampled_rss_sum_peak_mib':r['sampled_rss_sum_peak_bytes']/2**20,
  'sampled_python_rss_peak_mib':r['sampled_role_rss_peak_bytes'].get('python',0)/2**20,'sampled_node_rss_peak_mib':r['sampled_role_rss_peak_bytes'].get('node',0)/2**20,
  'sampled_ffmpeg_rss_peak_mib':r['sampled_role_rss_peak_bytes'].get('ffmpeg',0)/2**20,'sampled_ffprobe_rss_peak_mib':r['sampled_role_rss_peak_bytes'].get('ffprobe',0)/2**20,
  'throttled_s':r['cpu_stat_delta'].get('throttled_usec',0)/1e6,'throttled_periods':r['cpu_stat_delta'].get('nr_throttled',0),
  'host_steal_percent':r['host_steal_percent'],'host_busy_percent':r['host_busy_percent'],'sampling_enabled':r.get('resource_sampling_enabled',True),
  'sample_count':r['sample_count'],'max_pids_threads':r['max_pids_threads'],'host_available_memory_start_mib':r['host_available_memory_start_bytes']/2**20,'host_available_memory_end_mib':r['host_available_memory_end_bytes']/2**20,
  'cold_inclusive_wall_s':r.get('cold_inclusive_wall_s'),'cold_inclusive_cpu_s':r.get('cold_inclusive_cpu_s'),'cold_inclusive_peak_mib':(r.get('cold_inclusive_memory_peak_bytes') or 0)/2**20 if r.get('cold_inclusive_memory_peak_bytes') is not None else None,
  'io_read_bytes':r['io_delta'].get('rbytes',0),'io_write_bytes':r['io_delta'].get('wbytes',0),'raw_record':r['id']+'.json','timeline':r['id']+'.timeline.jsonl'}
 flat.append(row)

def write_csv(name,data):
 with (out/name).open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
write_csv('MEASUREMENTS.csv',flat)
incomplete=[x for x in flat if x['outcome']=='incomplete']
if incomplete:write_csv('INCOMPLETE_SCANS.csv',incomplete)
(out/'OUTCOMES.json').write_text(json.dumps(quality,indent=2)+'\n')
groups=collections.defaultdict(list)
for r in flat:groups[(r['group'],r['operation'],r['case'],r['profile'],r['scope'],r['temperature'])].append(r)
summary=[]
for key,samples in sorted(groups.items()):
 good=[r for r in samples if r['worker_ok']]
 row=dict(zip(['group','operation','case','profile','scope','temperature'],key));row.update(n=len(samples),n_ok=len(good),outcomes=dict(collections.Counter(r['outcome'] for r in samples)))
 for metric in ['wall_s','total_cgroup_cpu_s','memory_peak_mib','python_process_cpu_s','live_node_cpu_s','reaped_child_cpu_s','sampled_rss_sum_peak_mib','observer_cpu_fraction_of_wall','host_steal_percent','throttled_s','cold_inclusive_wall_s','receipt_encoder_inference_s','receipt_encoder_inference_calls']:
  vals=[r[metric] for r in good if r.get(metric) is not None]
  for stat,fn in [('median',statistics.median),('min',min),('max',max)]:row[metric+'_'+stat]=fn(vals) if vals else None
 summary.append(row)
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
write_csv('SUMMARY.csv',[{**r,'outcomes':json.dumps(r['outcomes'])} for r in summary])
# Exact-file profile comparisons, current scope and warm observations only.
comparisons=[]
for case in items:
 table={r['profile']:r for r in summary if r['group']=='matrix' and r['operation']=='export' and r['temperature']=='resident_warm' and r['case']==case}
 if 'resilient' not in table:continue
 for profile in ['economy_5s','economy_2s']:
  if profile not in table:continue
  a=table[profile];b=table['resilient']
  comparisons.append({'case':case,'profile':profile,'vs':'resilient','warm_wall_s':a['wall_s_median'],'resilient_wall_s':b['wall_s_median'],'wall_saving_percent':100*(1-a['wall_s_median']/b['wall_s_median']),
  'warm_cpu_s':a['total_cgroup_cpu_s_median'],'resilient_cpu_s':b['total_cgroup_cpu_s_median'],'cpu_saving_percent':100*(1-a['total_cgroup_cpu_s_median']/b['total_cgroup_cpu_s_median']),
  'observed_warm_max_peak_mib':a['memory_peak_mib_max'],'resilient_observed_warm_max_peak_mib':b['memory_peak_mib_max']})
write_csv('PROFILE_COMPARISONS.csv',comparisons) if comparisons else None
(out/'PROFILE_COMPARISONS.json').write_text(json.dumps(comparisons,indent=2)+'\n')
# Measurement overhead and explicit legacy/default-all cost controls.
controls=[]
for control,baseline_group in [('speed_control','matrix'),('all_scope_control','matrix')]:
 for op in ['export','verify_positive','verify_metadata_loss','verify_negative']:
  a=next((r for r in summary if r['group']==control and r['operation']==op and r['temperature']=='resident_warm'),None)
  if not a:continue
  b=next((r for r in summary if r['group']==baseline_group and r['operation']==op and r['temperature']=='resident_warm' and r['case']==a['case'] and r['profile']==a['profile']),None)
  if b:controls.append({'control':control,'operation':op,'case':a['case'],'n_control':a['n'],'n_baseline':b['n'],'control_wall_s':a['wall_s_median'],'baseline_wall_s':b['wall_s_median'],'control_wall_change_percent':100*(a['wall_s_median']/b['wall_s_median']-1),'control_cpu_s':a['total_cgroup_cpu_s_median'],'baseline_cpu_s':b['total_cgroup_cpu_s_median'],'control_max_memory_mib':a['memory_peak_mib_max'],'baseline_max_memory_mib':b['memory_peak_mib_max']})
(out/'CONTROLS.json').write_text(json.dumps(controls,indent=2)+'\n')
write_csv('CONTROLS.csv',controls) if controls else None
issues=[q for q in quality if q['outcome'] in {'operational_error','wrong_id','unexpected_id','unknown'}]
fail=json.loads((raw/'FAILURES.json').read_text()) if (raw/'FAILURES.json').exists() else []
checks={'campaign_status':completion['status'],'data_rows':len(flat),'shutdown_rows':sum(r['op']=='close' for r in rows),'outcome_counts':dict(collections.Counter(q['outcome'] for q in quality)),
 'failures_recorded':fail,'unexpected_outcomes':issues,'max_cpu_accounting_abs_difference_s':max(abs(r['cpu_accounting_difference_s']) for r in flat),
 'max_observer_cpu_fraction_wall':max(r['observer_cpu_fraction_of_wall'] for r in flat),'max_host_steal_percent':max(r['host_steal_percent'] for r in flat),
 'max_charged_memory_peak_mib':max(r['memory_peak_mib'] for r in flat),'memory_limit_mib':4096,
 'protocol':'CJ-05-20261115-v1 + AMENDMENT1','cold_n':1,'warm_n':3,'corpus':'engineering fixtures, not a population or representative quality/durability/FPR sample'}
(out/'ANALYSIS_CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n')
(out/'CORPUS.json').write_text(json.dumps(corpus,indent=2)+'\n')
print(json.dumps({k:v for k,v in checks.items() if k not in {'failures_recorded','unexpected_outcomes'}},indent=2))
