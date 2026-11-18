"""EC2 acceptance of the downloadable example against the installed public wheel.

Run inside the qualified CPU image; network disabled. No SDK source import path.
Retain the chosen private work directory and its logs until acceptance is complete.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request

source = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve()
work.mkdir(parents=True, exist_ok=False)
logs = work / 'logs'; logs.mkdir()
inputs = work / 'inputs'; inputs.mkdir()
(work / 'staging').mkdir(); (work / 'registry').mkdir()
events = work / 'events.jsonl'

def emit(kind, **kw):
    row = dict(at=datetime.now(timezone.utc).isoformat(), kind=kind, **kw)
    with events.open('a') as out: out.write(json.dumps(row) + '\n')
    print(json.dumps(row), flush=True)

def command(name, args, expected=0):
    started = time.monotonic()
    with (logs / (name + '.stdout')).open('w') as out, (logs / (name + '.stderr')).open('w') as err:
        result = subprocess.run(args, cwd=work, stdout=out, stderr=err, timeout=900)
    emit('command', name=name, exit_code=result.returncode, wall_s=round(time.monotonic()-started, 3))
    if result.returncode != expected:
        raise AssertionError(f'{name}: expected {expected}, got {result.returncode}; see logs')
    return (logs / (name + '.stdout')).read_text()

# Import only the example's input validator (it imports no SDK until run()).
spec = importlib.util.spec_from_file_location('export_jobs', source / 'docs/examples/export_jobs.py')
example = importlib.util.module_from_spec(spec); spec.loader.exec_module(example)
import ariadne_mark
from importlib.metadata import version
sdk_version = version('ariadne-mark')
assert sdk_version == tomllib.loads((source / 'pyproject.toml').read_text())['project']['version']
assert not Path(ariadne_mark.__file__).resolve().is_relative_to(source)
emit('runtime', version=version('ariadne-mark'), module=ariadne_mark.__file__, source_checkout_imported=False)
from PIL import Image
image = Image.new('RGB', (1024, 768)); pixels=image.load()
for y in range(image.height):
    for x in range(image.width):
        pixels[x,y]=((3*x+5*y+x*y%37)%256,(x+2*y+x*y%71)%256,(2*x+3*y)%256)
created = {}
for name in ['image.png','image.jpg']:
    image.save(inputs / name)
    created[name] = datetime.now(timezone.utc).isoformat()
for name, size, fps in [('landscape.mp4','1280x720','24'),('portrait.mp4','1080x1920','30000/1001')]:
    command('fixture-'+name, ['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
        f'testsrc2=size={size}:rate={fps}','-t','6','-an','-c:v','libx264','-threads','2',
        '-preset','fast','-crf','18','-pix_fmt','yuv420p','-colorspace','bt709',
        '-color_primaries','bt709','-color_trc','bt709','-color_range','tv',str(inputs/name)])
    created[name] = datetime.now(timezone.utc).isoformat()
manifest = dict(schema_version=1,publisher='Integration acceptance fixture',
                system=dict(name='Deterministic engineering fixture',version='1'),jobs=[])
for name in ['image.png','image.jpg']:
    manifest['jobs'].append(dict(job_id=name,source='inputs/'+name,destination='staging/'+name,generated_at=created[name]))
for name in ['landscape.mp4','portrait.mp4']:
    for profile in ['economy_5s','economy_2s','resilient']:
        manifest['jobs'].append(dict(job_id=profile+'-'+name,source='inputs/'+name,
            destination='staging/'+profile+'-'+name,generated_at=created[name],
            audio_kind='none',video_profile=profile))
# Omitted profile must preserve SDK's default, using the same source in a distinct job.
manifest['jobs'].append(dict(job_id='default',source='inputs/landscape.mp4',
    destination='staging/default.mp4',generated_at=created['landscape.mp4'],audio_kind='none'))
manifest_path=work/'jobs.json';manifest_path.write_text(json.dumps(manifest,indent=2))
assert len(set(created.values()))==4
corpus=[dict(name=f.name,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size,
    generated_at=created[f.name],source='own deterministic engineering fixture, not actual AI output') for f in sorted(inputs.iterdir())]
(work/'corpus.json').write_text(json.dumps(corpus,indent=2))
# Genuine failure cases: they must fail before an SDK/model or output is created.
for name, mutate in [
    ('duplicate-id',lambda d:d['jobs'][1].update(job_id=d['jobs'][0]['job_id'])),
    ('naive-time',lambda d:d['jobs'][0].update(generated_at='2026-01-01T12:00:00')),
    ('future-time',lambda d:d['jobs'][0].update(generated_at='2099-01-01T00:00:00+00:00')),
    ('bad-profile',lambda d:d['jobs'][2].update(video_profile='not-a-profile')),
    ('input-output-collision',lambda d:d['jobs'][0].update(destination=d['jobs'][1]['source'])),
]:
    bad=json.loads(json.dumps(manifest));mutate(bad);path=work/(name+'.json');path.write_text(json.dumps(bad))
    try: example.load_jobs(path)
    except ValueError: emit('preflight_rejected',case=name)
    else: raise AssertionError(name+' was accepted')
assert not list((work/'staging').iterdir())
command('init-dev',['ariadne','init-dev',str(work/'identity')])
text=command('resident-example',[sys.executable,str(source/'docs/examples/export_jobs.py'),str(manifest_path),
    '--identity',str(work/'identity'),'--registry',str(work/'registry/assets.sqlite3'),'--allow-dev'])
accepted=[json.loads(line) for line in text.splitlines() if line.strip()]
assert len(accepted)==9
for row,job in zip(accepted,manifest['jobs']):
    assert row['job_id']==job['job_id'] and row['status']=='accepted_in_private_staging'
    file=Path(row['output']);receipt=row['receipt']
    assert hashlib.sha256(file.read_bytes()).hexdigest()==receipt['sha256']
    if file.suffix=='.mp4': assert receipt['video']['profile']==job.get('video_profile','economy_5s')
    assert datetime.fromisoformat(row['verification']['c2pa']['record']['created_at'].replace('Z','+00:00')) == datetime.fromisoformat(job['generated_at'].replace('Z','+00:00'))
# CLI failure must not overwrite even one completed output.
before=hashlib.sha256((work/'staging/image.png').read_bytes()).hexdigest()
command('overwrite-refused',[sys.executable,str(source/'docs/examples/export_jobs.py'),str(manifest_path),
    '--identity',str(work/'identity'),'--registry',str(work/'registry/assets.sqlite3'),'--allow-dev'],expected=2)
assert before==hashlib.sha256((work/'staging/image.png').read_bytes()).hexdigest()
command('report-key',['ariadne','report','keygen',str(work/'report')])
public=work/'public-sources.json';public.write_text(json.dumps(dict(schema_version=1,sources=[dict(publisher=manifest['publisher'],system=manifest['system'])])))
with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
base=f'http://127.0.0.1:{port}'
stdout=(logs/'verifier.stdout').open('w');stderr=(logs/'verifier.stderr').open('w')
server=subprocess.Popen(['ariadne','serve','--host','127.0.0.1','--port',str(port),'--threads','2',
    '--verification-scope','current','--registry',str(work/'registry/assets.sqlite3'),
    '--public-sources',str(public),'--report-key',str(work/'report/report.key'),'--verifier-id',base],
    cwd=work,stdout=stdout,stderr=stderr)

def http(path, body=None):
    request=urllib.request.Request(base+path,data=body,headers={'Content-Type':'application/octet-stream'} if body else {})
    with urllib.request.urlopen(request,timeout=330) as response: return json.load(response)

try:
    for attempt in range(120):
        if server.poll() is not None: raise AssertionError('Verifier exited')
        try:
            health=http('/health');break
        except (OSError,urllib.error.URLError):time.sleep(.5)
    else:raise AssertionError('Verifier failed to start')
    assert health['signed_reports']
    for row in accepted:
        file=Path(row['output']);report=http('/verify?format='+file.suffix[1:],file.read_bytes())
        assert report['watermark']['token']==row['receipt']['token']
        assert report['c2pa']['status']=='verified_claim'
        report_file=work/(row['job_id']+'.report.json');report_file.write_text(json.dumps(report))
        command('jws-'+row['job_id'],['ariadne','report','verify',str(report_file),
            '--public-key',str(work/'report/report.pub'),'--asset',str(file),'--verifier-id',base])
        record=http('/records/'+row['receipt']['token'])
        assert record['record']['publisher']==manifest['publisher']
        emit('independent_verified',job_id=row['job_id'],profile=row['receipt'].get('video',{}).get('profile'))
    negative=http('/verify?format=png',(inputs/'image.png').read_bytes())
    assert negative['watermark']['status']=='not_found'
    (work/'clean-negative.json').write_text(json.dumps(negative))
    first=work/(accepted[0]['job_id']+'.report.json')
    command('wrong-asset-jws',['ariadne','report','verify',str(first),'--public-key',str(work/'report/report.pub'),
        '--asset',str(work/'staging/image.jpg'),'--verifier-id',base],expected=2)
finally:
    server.terminate()
    try:server.wait(timeout=20)
    except subprocess.TimeoutExpired:server.kill();server.wait(timeout=10)
    stdout.close();stderr.close()
summary=dict(status='passed',sdk_version=sdk_version,exports=9,independent_http_registry_jws=9,
    per_source_generation_times=4,profiles=['economy_5s','economy_2s','resilient'],
    default='economy_5s',preflight_rejections=5,overwrite_refused=True,wrong_asset_report_rejected=True,
    clean_image_negative=True,platform='Linux x86-64 CPU on owned EC2',
    scope='Engineering fixtures, dev identity, localhost HTTP; not production trust/durability/capacity qualification')
(work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');emit('complete',**summary)
