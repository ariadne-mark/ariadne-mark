"""Sequential benchmark campaign. All SDK work is in pinned, offline containers."""
import hashlib,json,os,subprocess,sys,time,traceback
from pathlib import Path
import observe as o
o.S=Path(__file__).resolve().parent
mode=sys.argv[1] if len(sys.argv)>1 else 'pilot'
o.O=o.R/'results'/mode;o.O.mkdir(exist_ok=False)
lock=open('/home/ubuntu/.ariadne-qualification.lock','a');o.fcntl.flock(lock,o.fcntl.LOCK_EX)
corpus=json.loads((o.D/'public/corpus.json').read_text())['items']
profiles=['economy_5s','economy_2s','resilient']
if mode=='pilot':selected=[x for x in corpus if x['id']=='v720_10_30'];pairs=[(selected[0],'economy_5s')]
else:
    selected=[x for x in corpus if not x.get('negative_only')]
    pairs=[]
    for i,item in enumerate(selected):
        order=profiles[i%3:]+profiles[:i%3]
        pairs.extend((item,p) for p in (order if item['kind']=='video' else ['image']))
plan={'mode':mode,'repeats':4,'cold_n':1,'warm_n':3,'export_pairs':[{'case':x['id'],'profile':p} for x,p in pairs],
      'negative_cases':[x['id'] for x in selected],'primary_scope':'current','additional_all_control':mode=='main'}
o.save(o.O/'SCHEDULE.json',plan)
failures=[];exports={};errors=[]
def fail(stage,error):
    row={'stage':stage,'error':repr(error),'traceback':traceback.format_exc()};failures.append(row);o.save(o.O/'FAILURES.json',failures);o.emit('cell_failed',stage=stage,error=repr(error))
def run_session(label,jobs,exporter=False):
    s=None;rows=[]
    try:
        s=o.Session(label,exporter=exporter)
        for j in jobs:
            row=s.request(j);rows.append(row)
            if not row['worker']['ok']:raise RuntimeError(row['worker'].get('message','operation failed'))
    finally:
        if s:s.close()
    return rows
try:
    for item,profile in pairs:
        cell=item['id']+'-'+profile
        try:
            jobs=[]
            for i in range(4):
                target=f"/artifacts/{mode}/{cell}/out-{i}"+Path(item['file']).suffix
                j={'id':f'export-{cell}-r{i}','op':'mark','exporter':True,'case':item['id'],'kind':item['kind'],
                    'profile':profile,'scope':'current','iteration':i,
                    'created_at':item['created_at'],'source':'/inputs/'+item['file'],'destination':target}
                jobs.append(j)
            rows=run_session('export-'+cell,jobs,exporter=True)
            for i,row in enumerate(rows):
                receipt=row['worker']['receipt'];dest=jobs[i]['destination'];host=o.D/'artifacts'/Path(dest).relative_to('/artifacts')
                assert hashlib.sha256(host.read_bytes()).hexdigest()==receipt['sha256']
                if item['kind']=='video':assert receipt['video']['profile']==profile
            exports[cell]={'item':item,'profile':profile,'rows':rows,'destinations':[j['destination'] for j in jobs]}
            o.save(o.O/'EXPORT_INDEX.json',{k:{'case':v['item']['id'],'profile':v['profile'],'destinations':v['destinations']} for k,v in exports.items()})
        except Exception as e:fail('export-'+cell,e)
    # Independent verifier processes are never warmed by their encoder.
    for cell,bundle in exports.items():
        item=bundle['item'];profile=bundle['profile'];targets=bundle['destinations']
        for variant in ['positive','metadata_loss']:
            try:
                variants=[]
                if variant=='metadata_loss':
                    for i,target in enumerate(targets):
                        suffix='.mp4' if item['kind']=='video' else '.png'
                        dest=f'/artifacts/{mode}/{cell}/without-metadata-{i}'+suffix
                        args=['docker','run','--rm','--network','none','--cpus','2','--memory','512m','--read-only','--user','1000:1000','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','-v',str(o.S)+':/scripts:ro','-v',str(o.D/'artifacts')+':/artifacts','--entrypoint','python',o.IMAGE,'/scripts/variants.py',target,dest]
                        result=subprocess.check_output(args,text=True,stderr=(o.O/(f'variant-{cell}-{i}.stderr')).open('w'),timeout=120)
                        o.save(o.O/(f'variant-{cell}-{i}.json'),json.loads(result));variants.append(dest)
                else:variants=targets
                jobs=[{'id':f'{variant}-{cell}-r{i}','op':'verify','case':item['id'],'profile':profile,'scope':'current','iteration':i,'source':target} for i,target in enumerate(variants)]
                rows=run_session(variant+'-'+cell,jobs)
                for i,row in enumerate(rows):
                    report=row['worker']['report'];expected=bundle['rows'][i]['worker']['receipt']['token']
                    assert report['watermark'].get('token')==expected,(cell,i,report['watermark'])
                    if variant=='positive':assert report['c2pa']['signature']=='valid'
                    else:assert report['c2pa']['status']=='not_found' and report.get('recovery',{}).get('status')=='found',report.get('recovery')
            except Exception as e:fail(variant+'-'+cell,e)
    for item in selected:
        try:
            jobs=[{'id':f'negative-{item["id"]}-r{i}','op':'verify','case':item['id'],'profile':None,'scope':'current','iteration':i,'source':'/inputs/'+item['file']} for i in range(4)]
            rows=run_session('negative-'+item['id'],jobs)
            for row in rows:
                report=row['worker']['report'];status=report['watermark']['status']
                if status!='not_found':errors.append({'case':item['id'],'status':status,'reason':report['watermark'].get('reason'),'interpretation':'Keep incomplete or unexpected result distinct from a completed clean negative'})
        except Exception as e:fail('negative-'+item['id'],e)
    # The legacy/full scope is an explicit additional cost, not hidden in current.
    control='v720_10_30-economy_5s'
    if mode=='main' and control in exports:
        bundle=exports[control];item=bundle['item']
        for variant in ['positive','metadata_loss','negative']:
            try:
                targets=bundle['destinations'] if variant=='positive' else [f'/artifacts/{mode}/{control}/without-metadata-{i}.mp4' for i in range(4)] if variant=='metadata_loss' else ['/inputs/'+item['file']]*4
                jobs=[{'id':f'all-{variant}-{control}-r{i}','op':'verify','case':item['id'],'profile':'economy_5s' if variant!='negative' else None,'scope':'all','iteration':i,'source':target} for i,target in enumerate(targets)]
                rows=run_session('all-'+variant+'-'+control,jobs)
                for i,row in enumerate(rows):
                    report=row['worker']['report']
                    if variant!='negative':assert report['watermark'].get('token')==bundle['rows'][i]['worker']['receipt']['token']
                    elif report['watermark']['status']!='not_found':errors.append({'scope':'all','variant':'negative','status':report['watermark']['status']})
            except Exception as e:fail('all-'+variant,e)
    if mode=='main':
        for item in [x for x in corpus if x.get('negative_only')]:
            try:
                jobs=[{'id':f'budget-negative-{item["id"]}-r{i}','op':'verify','case':item['id'],'profile':None,'scope':'current','iteration':i,'source':'/inputs/'+item['file']} for i in range(2)]
                rows=run_session('budget-negative-'+item['id'],jobs)
                for row in rows:
                    report=row['worker']['report']
                    o.emit('budget_negative_result',id=row['id'],status=report['watermark']['status'],reason=report['watermark'].get('reason'))
            except Exception as e:fail('budget-negative-'+item['id'],e)
        if control in exports:
            bundle=exports[control];item=bundle['item']
            try:
                jobs=[{'id':f'speedcontrol-export-r{i}','op':'mark','case':item['id'],'kind':'video','profile':'economy_5s','scope':'current','iteration':i,'exporter':True,'created_at':item['created_at'],'source':'/inputs/'+item['file'],'destination':f'/artifacts/{mode}/speedcontrol/out-{i}.mp4','sample_resources':False} for i in range(4)]
                speed=run_session('speedcontrol-export',jobs,exporter=True)
                for variant in ['positive','negative']:
                    targets=[f'/artifacts/{mode}/speedcontrol/out-{i}.mp4' for i in range(4)] if variant=='positive' else ['/inputs/'+item['file']]*4
                    checks=[{'id':f'speedcontrol-{variant}-r{i}','op':'verify','case':item['id'],'profile':'economy_5s' if variant=='positive' else None,'scope':'current','iteration':i,'source':target,'sample_resources':False} for i,target in enumerate(targets)]
                    read=run_session('speedcontrol-'+variant,checks)
                    for i,row in enumerate(read):
                        report=row['worker']['report']
                        if variant=='positive':assert report['watermark'].get('token')==speed[i]['worker']['receipt']['token']
                        else:assert report['watermark']['status']=='not_found'
            except Exception as e:fail('sampling-disabled-speed-control',e)
    o.save(o.O/'COMPLETE.json',{'status':'complete_with_failures' if failures else 'passed','failures':len(failures),'distinct_operations':sum(1 for row in (o.O/'measurements.jsonl').open()),'export_cells':len(exports),'negative_non_not_found':errors,'protocol':'CJ-05-20261115-v1','runtime_unchanged':True})
    o.emit('campaign_complete',failures=len(failures),export_cells=len(exports),negative_non_not_found=errors)
except Exception as e:
    fail('campaign_fatal',e);raise
