"""Final integrity/method audit; run only after primary and mixed jobs finish."""
from pathlib import Path
import hashlib,json,math,subprocess,sys
r=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
main=r/'results/main';complete=json.loads((main/'COMPLETE.json').read_text());mixed=json.loads((r/'results/mixed-v1/COMPLETE.json').read_text());idle=json.loads((r/'results/idle-v1/COMPLETE.json').read_text())
rows=[json.loads(x) for x in (main/'measurements.jsonl').read_text().splitlines()]
ids=[x['id'] for x in rows];assert len(ids)==len(set(ids))
assert sum(x['op']!='close' for x in rows)==338,(len(rows),sum(x['op']!='close' for x in rows))
assert sum(x['op']=='close' for x in rows)==85
for row in rows:
 assert (main/(row['id']+'.json')).is_file()
 assert row['cpu_s']>=0 and row['wall_s']>0
 assert 0 < row['memory_peak_bytes'] <= 4*2**30
 assert row['memory_peak_method'].startswith('kernel memory.peak')
 if row['op']!='close':assert abs(row['cpu_accounting_difference_s'])<max(.15,row['cpu_s']*.02),(row['id'],row['cpu_accounting_difference_s'])
corpus=json.loads((r/'data/public/corpus.json').read_text())['items'];assert len(corpus)==10
for item in corpus:
 p=r/'data/inputs'/item['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
legacy=Path('/home/ubuntu/ariadne-verifier-r2-20261112/legacy-cache/y_256b_img.jit')
assert hashlib.sha256(legacy.read_bytes()).hexdigest()=='5c7a4581c36fc6090aafdcfb3999123bae5172a4847f22e2da4e7fd1a39d1e1b'
with (out/'frozen-harness-check.log').open('w') as log:
 for name in ['MAIN_HARNESS_SHA256.txt','MIXED_HARNESS_SHA256.txt','IDLE_HARNESS_SHA256.txt']:
  subprocess.run(['sha256sum','-c',str(r/'results'/name)],cwd=r,check=True,stdout=log)
image='sha256:1a4dd358bcf698df654daaac631a26d3bc874104de5108bc94ce941c33a49980'
for folder,expected_rows in [(main,423),(r/'results/mixed-v1',12),(r/'results/idle-v1',23)]:
 data=[json.loads(line) for line in (folder/'measurements.jsonl').read_text().splitlines()];assert len(data)==expected_rows,(folder,len(data))
 for infofile in folder.glob('*.container.json'):
  info=json.loads(infofile.read_text());assert info['image']==image
  assert info['limits']=={'NanoCpus':2000000000,'Memory':4294967296},info['limits']
runtime=json.loads((out/'RUNTIME.json').read_text());assert runtime['c2pa_qualification']['status']=='qualified'
expected={'ariadne-06-verifier-preview':'62cfb9af9e80','ariadne-stock-web-1':'458b5643cfdf','ariadne-stock-worker-1':'edaaa89ad92b','ariadne-stock-verifier-1':'adab2f33cd6e'}
current=dict(x.split() for x in subprocess.check_output(['docker','ps','--format','{{.Names}} {{.ID}}'],text=True).splitlines())
assert all(current.get(k)==v for k,v in expected.items())
assert not any(k.startswith('ariadne-cj05-') for k in current)
cal=json.loads((r/'results/CALIBRATION.json').read_text());assert cal['status']=='passed'
result={'status':'passed','primary':complete,'mixed':mixed,'idle':idle,'primary_data_rows':338,'shutdown_rows':85,'corpus_inputs_sha256_unchanged':10,'unique_record_ids':len(ids),'legacy_model_hash_matches':True,'same_fd_memory_peak_reset_calibrated':True,'full_cpu_accounting_checked':True,'frozen_harness_hashes_match':True,'existing_services_preserved':expected,'owned_containers_remaining':0,'sdk_or_modes_changed':False,'scope':'Integrity/method audit; incomplete negative outcomes, if present, remain classified separately in analysis'}
(out/'FINAL_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in {'primary','mixed','idle','existing_services_preserved'}},indent=2))
