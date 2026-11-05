"""Inspect own distributions and record the exact CI source and artifact bytes."""
import hashlib,json,os,re,subprocess,tarfile,zipfile,tomllib
from pathlib import Path,PurePosixPath
out=Path('release-dist');artifacts=sorted([*out.glob('*.whl'),*out.glob('*.tar.gz')])
if len(artifacts)!=2:raise SystemExit('Expected one Ariadne wheel and one source archive')
records=[]
for archive in artifacts:
 if archive.suffix=='.whl':
  with zipfile.ZipFile(archive) as z:names=z.namelist()
 else:
  with tarfile.open(archive) as t:names=t.getnames()
 for name in names:
  p=PurePosixPath(name)
  if p.is_absolute() or '..' in p.parts or any(x in p.parts for x in ['.git','.secrets','.ariadne','stateless_product']):raise SystemExit('Unexpected archive path: '+name)
  if p.suffix.lower() in {'.pem','.key','.sqlite3','.mp4','.jpg','.jpeg','.png','.onnx','.jit'}:raise SystemExit('Private/media/model file in own distribution: '+name)
 if not any('LICENSE' in name for name in names):raise SystemExit('Missing license')
 if not any(name.endswith('ariadne_mark/c2pa-bootstrap.json') for name in names):raise SystemExit('Missing bootstrap pin manifest')
 records.append({'filename':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'members':len(names)})
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
if not re.fullmatch('[a-f0-9]{40}',commit):raise SystemExit('Invalid commit')
manifest={'schema_version':1,'build_commit':commit,'ci_run_id':os.environ.get('GITHUB_RUN_ID'),'version':tomllib.loads(Path('pyproject.toml').read_text())['project']['version'],'scope':'Own SDK wheel/source, no combined Docker binary','artifacts':records,'third_party_inventory':'installed-packages.json','bootstrap_pins':json.loads(Path('src/ariadne_mark/c2pa-bootstrap.json').read_text())}
(out/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(out/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['filename']+'\n' for x in records))
print(json.dumps(manifest,indent=2))
