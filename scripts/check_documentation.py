"""Static documentation contracts; run on EC2, never import the SDK."""
import ast,csv,hashlib,json,re,shlex,subprocess,tomllib
from pathlib import Path
from urllib.parse import unquote,urlsplit
root=Path(__file__).resolve().parents[1]
errors=[];warnings=[];checked_links=0;python_blocks=0;shell_blocks=0
manifest=json.loads((root/'docs/site-publication.json').read_text())
version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
summary=json.loads((root/'docs/validation/results/0.7.2a1-summary.json').read_text())
# The website publication snapshot is immutable evidence for the prior release,
# not qualification of a new SDK candidate.
assert manifest['sdk_version']==summary['sdk_version']=='0.7.2a1'
assert version == '0.7.3a4'
assert (root/'docs/operations/release-0.7.3a0.md').is_file()
assert manifest['tested_sdk_commit']==summary['commit']=='8c6fda81b27c5c6c0c9539bbbc3daef7e285b1fa'
assert summary['ci_conclusion']=='success' and summary['full_media']=={'tests':217,'wall_s':357.287,'skipped':0}
assert summary['video_profiles']==['economy_5s','economy_2s','resilient']
paths=set()
for item in manifest['pages']+manifest['assets']:
 p=root/item['source']
 if not p.is_file():errors.append('Missing publication source: '+item['source'])
 if p.suffix=='.md':paths.add(p)
routes=[x['route'] for x in manifest['pages']+manifest['assets']]
if len(routes)!=len(set(routes)):errors.append('Duplicate publication route')
paths|={root/'README.md',root/'compliance/COVERAGE.md',root/'docs/README.ru.md'}
for section in ['implementation','operations','compliance','benchmarks','reference']:
 paths|=set((root/'docs'/section).glob('*.md'))
# Include the current protocol as well as actual results; old validation is immutable history.
paths.add(root/'docs/validation/0.7.2a1.md')
flags={'--help'}
for n in ast.walk(ast.parse((root/'src/ariadne_mark/cli.py').read_text())):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument':
  flags|={a.value for a in n.args if isinstance(a,ast.Constant) and isinstance(a.value,str) and a.value.startswith('--')}
def slug(x):
 x=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',x)
 return re.sub(r'[^\w\- ]','',x.replace('`','').lower()).strip().replace(' ','-')
for p in sorted(paths):
 if not p.exists():continue
 text=p.read_text();rel=str(p.relative_to(root))
 if not re.search(r'^# .+',text,re.M):errors.append(rel+': missing H1')
 for language,block in re.findall(r'^```([^\n]*)\n(.*?)^```',text,re.M|re.S):
  language=language.strip()
  if language in {'python','py'}:
   python_blocks+=1
   try:ast.parse(block)
   except SyntaxError as e:errors.append(f'{rel}: Python syntax: {e}')
  if language in {'sh','bash','shell'}:
   shell_blocks+=1
   q=subprocess.run(['bash','-n'],input=block,text=True,capture_output=True)
   if q.returncode:errors.append(rel+': shell syntax: '+q.stderr.strip())
   logical=block.replace('\\\n',' ')
   for line in logical.splitlines():
    if line.strip().startswith('ariadne '):
     try:tokens=shlex.split(line,comments=True)
     except ValueError as e:errors.append(rel+': shell tokenization: '+str(e));continue
     unknown={t.split('=',1)[0] for t in tokens if t.startswith('--')}-flags
     if unknown:errors.append(rel+': unknown CLI options '+str(sorted(unknown)))
 prose=re.sub(r'^```[^\n]*\n.*?^```','',text,flags=re.M|re.S)
 for target in re.findall(r'(?<!!)\[[^]]*\]\(([^)]+)\)',prose):
  checked_links+=1
  if target.startswith(('https://','http://','mailto:')):continue
  path,_,fragment=target.partition('#')
  dest=(p.parent/unquote(path)).resolve() if path else p
  if not dest.is_relative_to(root):errors.append(rel+': link escapes root '+target);continue
  if not dest.exists():errors.append(rel+': broken link '+target);continue
  if fragment and dest.suffix=='.md':
   headings={slug(h) for h in re.findall(r'^#{1,6} (.+)$',dest.read_text(),re.M)}
   if unquote(fragment) not in headings:errors.append(rel+': missing anchor '+target)
# Candidate headings cannot impersonate the dated published baseline.
for p in paths:
 if p.is_file() and 'validation' not in p.parts and 'benchmarks' not in p.parts:
  text=p.read_text()
  release_note=re.fullmatch(r'release-(0\.7\.[0-9]+a[0-9]+)\.md',p.name)
  expected_header=release_note.group(1) if release_note else version
  # Anywhere in a line, not only at its start (P-04: '... · SDK **x** scope').
  for header in re.findall(r'\bSDK \*\*([^*]+)\*\*',text):
   if header.split()[0] != expected_header:errors.append(str(p.relative_to(root))+': stale active SDK header '+header)
  first_line=text.splitlines()[0] if text else ''
  heading_version=re.search(r'^# .* (?:—|-) (0\.7\.[0-9]+a[0-9]+)\s*$',first_line)
  if heading_version and heading_version.group(1)!=version and 'release-' not in p.name and p.name!='releases.md':
   errors.append(str(p.relative_to(root))+': stale versioned title '+heading_version.group(1))
  first=text.splitlines()[0] if text else ''
  # Per-version release notes describe their own version by design.
  if 'candidate' in first.lower() and re.search(r'0\.7\.[0-9]+a[0-9]+',first) and version not in first and not p.name.startswith('release-'):
   errors.append(str(p.relative_to(root))+': stale candidate heading')

for p in (root/'docs').rglob('*.json'):json.loads(p.read_text())
for p in (root/'compliance').rglob('*.json'):json.loads(p.read_text())
legal=json.loads((root/'docs/compliance/requirements-matrix.json').read_text())
sources={x['id'] for x in json.loads((root/'compliance/sources/index.json').read_text())['sources']}
for row in legal['rows']:
 if row['source_id'] not in sources:errors.append('Unknown legal source '+row['id'])
 for key in ['implementation_path','evidence_path']:
  if not (root/row[key]).exists():errors.append('Missing matrix path '+row['id']+': '+row[key])
with (root/'docs/compliance/requirements-matrix.csv').open(newline='') as f:
 if list(csv.DictReader(f))!=legal['rows']:errors.append('CSV/JSON legal matrix mismatch')
# Quote totals in the single canonical excerpt page, grouped by original URL.
quote_words={}
for line in (root/'docs/compliance/source-excerpts.md').read_text().splitlines():
 m=re.search(r'\[.+?\]\((https?://[^)]+)\).*?“([^”]+)”',line)
 if m:quote_words[m[1]]=quote_words.get(m[1],0)+len(m[2].split())
if any(n>25 for n in quote_words.values()):errors.append('Excerpt quota exceeded')
result={'ok':not errors,'sdk_version':version,'published_snapshot_qualified_commit':summary['commit'],
 'active_markdown_files':len(paths),'local_links_checked':checked_links,'python_blocks_syntax_checked':python_blocks,
 'shell_blocks_syntax_checked':shell_blocks,'publication_pages':len(manifest['pages']),'publication_assets':len(manifest['assets']),
 'legal_matrix_rows':len(legal['rows']),'excerpt_words_by_source':quote_words,'errors':errors,'warnings':warnings,
 'scope':'Static document/link/contract checks only; no SDK import, inference, new legal approval or media benchmark'}
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['ok'] else 1)
