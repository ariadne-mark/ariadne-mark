"""Independent consistency audit of retained reports; no SDK/media imports."""
import collections,hashlib,json,math,sys
from pathlib import Path
R=Path(sys.argv[1]);O=R/'results';rows=json.loads((O/'RESULTS.json').read_text());exports=json.loads((O/'EXPORTS.json').read_text());summary=json.loads((O/'SUMMARY.json').read_text())
assert summary['status']=='completed' and summary['errors']==0 and summary['observations']==len(rows)==96
assert len(exports)==16 and len({(e['scene'],e['profile']) for e in exports})==16
receipts={}
for e in exports:
 raw=json.loads((O/('export-'+e['scene']+'-'+e['profile']+'.json')).read_text());receipt=raw['worker']['receipt']
 assert raw['worker']['ok'] and receipt['token']==e['token'] and receipt['sha256']==e['sha256']
 receipts[e['scene'],e['profile']]=receipt
keys=set();unchanged=0
for row in rows:
 key=(row['scene'],row['profile'],row['transform']);assert key not in keys;keys.add(key)
 raw=json.loads((O/row['measurement_file']).read_text());assert raw['worker']['ok']
 report=raw['worker']['report'];w=report['watermark'];expected=receipts[row['scene'],row['profile']]['token']
 assert row['expected_token']==expected and row['observed_token']==w.get('token') and row['status']==w['status']
 assert row['input_sha256']==receipts[row['scene'],row['profile']]['sha256']
 assert all(math.isfinite(row[k]) and row[k]>=0 for k in ['wall_s','cpu_s','peak_mib'])
 assert row['wall_s']==raw['wall_s'] and row['cpu_s']==raw['cpu_s']
 if row['outcome']=='correct_id':
  assert w.get('token')==expected and any(x['token']==expected and x['status']=='confirmed' for x in w.get('ids',[]))
 elif row['outcome']=='completed_negative':assert w['status']=='not_found' and not w.get('token')
 elif row['outcome']=='single_observation':assert w['status']=='single_observation' and not w.get('token')
 elif row['outcome']=='incomplete':assert w['status']=='not_checked'
 elif row['outcome']=='wrong_id':assert w.get('token') and w['token']!=expected
 else:raise AssertionError('Unexpected outcome: '+row['outcome'])
 if row['transform']=='unchanged':
  unchanged+=1;assert row['outcome']=='correct_id' and report['c2pa']['signature']=='valid'
assert unchanged==16
counts=collections.Counter(x['outcome'] for x in rows);assert dict(counts)==summary['outcomes']
assert all(n==4 for n in collections.Counter((r['kind'],r['profile'],r['transform']) for r in rows).values())
result={'passed':True,'sdk':'0.7.3a4','raw_reports_checked':len(rows),'export_receipts_checked':len(exports),'unchanged_signature_and_id_controls':unchanged,'per_cell_scenes':4,'expected_ids_bound_to_export_receipts':True,'unconfirmed_not_counted_as_recovered':True,'negative_and_incomplete_separated':True,'outcomes':dict(counts),'results_sha256':hashlib.sha256((O/'RESULTS.json').read_bytes()).hexdigest(),'scope':'Static consistency audit against raw SDK reports/receipts; no population performance estimate or legal certification'}
(R/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
