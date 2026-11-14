"""Run only on the EC2 host: actual installed kit, Compose, TLS and recovery.

Host Python uses stdlib only; all SDK/media execution is in bounded containers.
Evidence is separated from keys, media and mutable registry state.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
import uuid

image, work, fixtures, evidence, validator = sys.argv[1:]
work, fixtures, evidence, validator = map(lambda p: Path(p).resolve(), [work, fixtures, evidence, validator])
work.mkdir(parents=True, exist_ok=True); evidence.mkdir(parents=True, exist_ok=True)
root = work / 'bundle'
assert not root.exists(), 'Use a new work directory for each acceptance run'
events = (evidence / 'events.jsonl').open('a')
project = 'ariadne-kit-' + uuid.uuid4().hex[:10]
# The SDK image is pinned through the kit's own pin-image.sh (immutable ID).
env = {k: v for k, v in os.environ.items() if k != 'KIT_SDK_IMAGE'}
compose = ['docker', 'compose', '-p', project, '--project-directory', str(root)]


def emit(kind, **values):
    row = {'kind': kind, **values}
    events.write(json.dumps(row) + '\n'); events.flush()
    print(json.dumps(row), flush=True)


def command(args, name, *, expected=0, timeout=600):
    started = time.monotonic()
    with (evidence / (name + '.log')).open('wb') as log:
        result = subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    emit('command', name=name, argv=args, exit_code=result.returncode, wall_s=time.monotonic() - started)
    if result.returncode != expected:
        raise AssertionError(f'{name}: expected exit {expected}, got {result.returncode}; inspect its log')
    return (evidence / (name + '.log')).read_text()


def sdk(args, name, *, expected=0, mounts=()):
    return command(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g',
        '--user', f'{os.getuid()}:{os.getgid()}', '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=512m',
        '-v', str(work) + ':/workspace', *mounts, image, *args], name, expected=expected)


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); return sock.getsockname()[1]


def http(path, *, body=None, content_type=None, expected=200):
    request = urllib.request.Request(base + path, data=body, headers={'Content-Type': content_type} if content_type else {})
    for retry in range(10):
        try:
            with urllib.request.urlopen(request, context=tls, timeout=200) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        if status != 429:
            break
        time.sleep(.25)
    if status != expected:
        raise AssertionError(f'{path}: expected HTTP {expected}, got {status}: {raw[:250]!r}')
    return raw


success = False
try:
    command(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], 'image-id')
    edge_image = 'nginx@sha256:583b7f2fce1cdb8da5ad5c39ebd3c33b98b87d493190e548bdee1fa8c619c311'
    command(['docker', 'image', 'inspect', edge_image, '--format', '{{.Id}}'], 'edge-image-id')
    command(['docker', 'run', '--rm', '--network', 'none', '--memory', '64m',
             '--entrypoint', 'nginx', edge_image, '-v'], 'edge-version')
    command([str(validator), '--version'], 'external-validator-version')
    sdk(['kit', 'init', '/workspace/bundle', '--development', '--public-manifests',
         '--publisher', 'Kit Integration Fixture', '--system', 'Deterministic Fixture', '--system-version', '1'], 'kit-init')
    command(['bash', str(root / 'pin-image.sh'), image], 'kit-pin-image')
    pinned = dict(l.split('=', 1) for l in (root / '.env').read_text().splitlines() if '=' in l)
    assert pinned['KIT_SDK_IMAGE'].startswith('sha256:') and pinned['KIT_SDK_RECORD_SHA256'], pinned
    https_port, http_port = port(), port()
    while http_port == https_port:
        http_port = port()
    env.update(KIT_HTTP_PORT=str(http_port), KIT_HTTPS_PORT=str(https_port), KIT_BIND_ADDRESS='127.0.0.1')
    base = f'https://localhost:{https_port}'
    config = json.loads((root / 'config/kit.json').read_text()); config['verifier_url'] = base
    (root / 'config/kit.json').write_text(json.dumps(config))
    profile = json.loads((root / 'config/product.json').read_text())
    profile['deployment'].update(verifier_url=base, feedback_url=base + '/feedback')
    (root / 'config/product.json').write_text(json.dumps(profile))
    sdk(['kit', 'render', '/workspace/bundle'], 'kit-render')
    checked = json.loads(sdk(['kit', 'check', '/workspace/bundle', '--runtime'], 'kit-check'))
    assert checked['status'] == 'ready_for_development' and checked['default_video_profile'] == 'economy_5s'
    assert checked['legal_determination'] == 'not_performed'
    assert not [w for w in checked['warnings'] if w['code'] == 'sdk_image_not_pinned'], checked['warnings']
    command([*compose, 'config'], 'compose-resolved')
    for name in ['input.png', 'input.mp4']:
        shutil.copyfile(fixtures / name, root / 'inputs' / name)
    generated_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    jobs = [{'source': 'input.png', 'destination': 'image.png', 'created_at': generated_at, 'publish_manifest': True},
            {'source': 'input.png', 'destination': 'private-history.png', 'created_at': generated_at}]
    jobs += [{'source': 'input.mp4', 'destination': mode + '.mp4', 'created_at': generated_at,
              'video_profile': mode, 'audio_kind': 'none', 'publish_manifest': True}
             for mode in ['economy_5s', 'economy_2s', 'resilient']]
    (root / 'batch.json').write_text(json.dumps({'schema_version': 1, 'jobs': jobs}))
    command([*compose, 'run', '--rm', 'exporter'], 'batch-export')
    receipts = {}
    for job in jobs:
        output = root / 'outputs' / job['destination']
        receipt = json.loads(output.with_name(output.name + '.receipt.json').read_text())
        assert hashlib.sha256(output.read_bytes()).hexdigest() == receipt['sha256']
        assert receipt['registry_recorded'] and receipt['manifest_recovery']['stored']
        if output.suffix == '.mp4':
            assert receipt['video']['profile'] == job['video_profile']
            expected_windows = {'economy_5s': [0, 1], 'economy_2s': [0, 1, 2]}
            if job['video_profile'] in expected_windows:
                actual_windows = [row['index'] for row in receipt['video']['watermark_windows']]
                assert actual_windows == expected_windows[job['video_profile']], (job['video_profile'], actual_windows)
                emit('cadence_verified', profile=job['video_profile'], windows=actual_windows,
                     marked_frames=receipt['video']['marked_frames'])
            else:
                assert receipt['video']['marked_frames'] == receipt['video']['frames_encoded']
        receipts[job['destination']] = receipt
    emit('batch_exports', count=len(receipts), video_modes=[j['video_profile'] for j in jobs if 'video_profile' in j])
    command([*compose, 'up', '-d', '--wait', '--wait-timeout', '120'], 'compose-up')
    tls = ssl.create_default_context(cafile=str(root / 'private/tls/cert.pem'))
    assert json.loads(http('/health'))['signed_reports']
    for destination, receipt in receipts.items():
        asset = root / 'outputs' / destination
        report = json.loads(http('/verify?format=' + asset.suffix[1:], body=asset.read_bytes(), content_type='application/octet-stream'))
        assert report['watermark']['token'] == receipt['token']
        assert report['c2pa']['status'] == 'verified_claim'
        assert report['c2pa']['record']['publisher'] == 'Kit Integration Fixture'
        assert report['c2pa']['record']['system'] == {'name': 'Deterministic Fixture', 'version': '1'}
        assert report['c2pa']['record']['created_at'] and report['c2pa']['record']['asset_id']
        response = work / ('response-' + destination + '.json'); response.write_text(json.dumps(report))
        sdk(['report', 'verify', '/workspace/' + response.name, '--public-key', '/workspace/bundle/config/report.pub',
             '--asset', '/workspace/bundle/outputs/' + destination, '--verifier-id', base], 'report-verify-' + destination)
        lookup = json.loads(http('/records/' + receipt['token']))
        assert lookup['record']['system']['name'] == 'Deterministic Fixture'
        emit('fresh_verified', destination=destination, token=receipt['token'], sdk_version=receipt['sdk_version'])
    original = json.loads((work / 'response-image.png.json').read_text())
    header, payload, signature = original['signed_report']['jws'].split('.')
    claim = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    claim['result']['watermark']['status'] = 'not_found'
    payload = base64.urlsafe_b64encode(json.dumps(claim).encode()).rstrip(b'=').decode()
    original['signed_report']['jws'] = '.'.join([header, payload, signature])
    (work / 'tampered.json').write_text(json.dumps(original))
    sdk(['report', 'verify', '/workspace/tampered.json', '--public-key', '/workspace/bundle/config/report.pub'],
        'tampered-report-rejected', expected=2)
    sdk(['report', 'verify', '/workspace/response-image.png.json', '--public-key', '/workspace/bundle/config/report.pub',
         '--asset', '/workspace/bundle/inputs/input.png'], 'wrong-asset-rejected', expected=2)
    emit('signed_report_negatives', tampering_rejected=True, wrong_asset_rejected=True)
    # Full manifest publication requires explicit per-asset consent.
    private_id = receipts['private-history.png']['manifest_recovery']['manifest_id']
    http('/manifests/' + urllib.parse.quote(private_id, safe=''), expected=404)
    command(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '1g',
        '--user', f'{os.getuid()}:{os.getgid()}', '-v', str(root / 'outputs') + ':/assets',
        '--entrypoint', 'python', image, '-c',
        "from PIL import Image; Image.open('/assets/image.png').convert('RGB').save('/assets/stripped.png')"], 'strip-image')
    for mode in ['economy_5s', 'economy_2s', 'resilient']:
        command(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '1g',
            '--user', f'{os.getuid()}:{os.getgid()}', '-v', str(root / 'outputs') + ':/assets',
            '--entrypoint', 'ffmpeg', image, '-v', 'error', '-i', '/assets/' + mode + '.mp4',
            '-map_metadata', '-1', '-c', 'copy', '/assets/' + mode + '.stripped.mp4'], 'strip-' + mode)
    for original, stripped, algorithm in [('image.png', 'stripped.png', 'org.ariadne-mark.trustmark-q.bch5.v1')] + [
            (mode + '.mp4', mode + '.stripped.mp4', 'org.ariadne-mark.trustmark-q.video-bch5.v1')
            for mode in ['economy_5s', 'economy_2s', 'resilient']]:
        asset = root / 'outputs' / stripped; receipt = receipts[original]
        report = json.loads(http('/verify?format=' + asset.suffix[1:], body=asset.read_bytes()))
        assert report['watermark']['token'] == receipt['token']
        assert report['c2pa']['status'] == 'not_found'
        assert report['recovery']['record']['system']['name'] == 'Deterministic Fixture'
        assert report['recovery']['manifest']['signature'] == 'valid'
        assert report['recovery']['manifest']['soft_binding'] == 'matched'
        binding = base64.b64encode(bytes.fromhex(receipt['token'])).decode()
        match = json.loads(http('/matches/byBinding?' + urllib.parse.urlencode({'alg': algorithm, 'value': binding})))
        assert match['matches'] == [{'manifestId': receipt['manifest_recovery']['manifest_id']}]
        content_match = json.loads(http('/matches/byContent?alg=' + algorithm, body=asset.read_bytes(),
            content_type='image/png' if asset.suffix == '.png' else 'video/mp4'))
        assert content_match == match
        raw = http('/manifests/' + urllib.parse.quote(match['matches'][0]['manifestId'], safe=''))
        emit('metadata_loss_recovered', asset=stripped, record_id=receipt['token'],
             manifest_sha256=hashlib.sha256(raw).hexdigest(), binding=report['recovery']['manifest'].get('asset_binding'))
        (evidence / (stripped + '.report.json')).write_text(json.dumps(report, indent=2))
    negative = json.loads(http('/verify?format=png', body=(root / 'inputs/input.png').read_bytes()))
    assert negative['watermark']['status'] == 'not_found' and not negative.get('watermark', {}).get('token')
    emit('negative_control', status=negative['watermark']['status'])
    http('/feedback', body=json.dumps({'rating': 'correct_result', 'media': 'video'}).encode(),
         content_type='application/json', expected=202)
    # Actual mounts, not only SDK's read_only flag, enforce the reader boundary.
    text = command([*compose, 'exec', '-T', 'verifier', 'python', '-c',
        "from pathlib import Path; import sqlite3; assert not Path('/kit/private/provider/private.key').exists(); "
        "db=sqlite3.connect('/kit/registry/assets.sqlite3');\n"
        "try: db.execute('CREATE TABLE forbidden_write(x)')\n"
        "except sqlite3.OperationalError: print('registry read-only; provider key absent')\n"
        "else: raise AssertionError('registry writable')\n"], 'reader-isolation')
    assert 'registry read-only; provider key absent' in text
    command([*compose, 'exec', '-T', 'edge', 'sh', '-c',
        'test ! -e /kit/private/provider/private.key && test ! -e /kit/private/reports/report.key'], 'edge-key-isolation')
    command([*compose, 'exec', '-T', 'verifier', 'python', '-c',
        "from pathlib import Path; assert not list(Path('/tmp').glob('ariadne-upload-*')); print('no retained uploads')"], 'upload-cleanup')
    command([*compose, 'down'], 'compose-restart-down')
    command([*compose, 'up', '-d', '--wait', '--wait-timeout', '120'], 'compose-restart-up')
    assert json.loads(http('/records/' + receipts['image.png']['token']))['record']['publisher'] == 'Kit Integration Fixture'
    feedback = sdk(['feedback-summary', '/workspace/bundle/state/feedback.sqlite'], 'feedback-persisted')
    assert 'correct_result' in feedback
    emit('restart_persistence', registry=True, feedback=True)
    # Independently downloaded c2patool validates C2PA structure/signature/binding.
    for name in ['image.png', 'economy_5s.mp4', 'economy_2s.mp4', 'resilient.mp4']:
        output = command(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '1g',
            '--user', f'{os.getuid()}:{os.getgid()}',
            '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=128m',
            '-v', str(validator) + ':/external/c2patool:ro', '-v', str(root / 'outputs') + ':/assets:ro',
            '--entrypoint', '/external/c2patool', image, '/assets/' + name, '--detailed'], 'external-validator-' + name)
        detailed = json.loads(output)
        active = detailed['manifests'][detailed['active_manifest']]
        # --detailed exposes raw assertion_store, not the compact assertions list.
        actions = [action for label, value in active['assertion_store'].items()
                   if label.startswith('c2pa.actions') for action in value['actions']]
        assert any(a.get('action') == 'c2pa.created' and a.get('digitalSourceType') ==
                   'http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia' for a in actions)
        validation = detailed['validation_results']['activeManifest']
        codes = {x['code'] for x in validation['success']}
        assert 'claimSignature.validated' in codes
        assert codes & {'assertion.dataHash.match', 'assertion.bmffHash.match'}
        # A local fixture is intentionally absent from the external trust list.
        failures = {x['code'] for x in validation.get('failure', [])}
        assert failures <= {'signingCredential.untrusted'}, failures
        emit('external_c2pa_read', asset=name, manifest=detailed['active_manifest'], source_type=True,
             signature_validated=True, asset_hash_matched=True, expected_trust_failures=sorted(failures))
    success = True
finally:
    subprocess.run([*compose, 'logs', '--no-color'], env=env, stdout=(evidence / 'compose.log').open('w'), stderr=subprocess.STDOUT)
    subprocess.run([*compose, 'down', '--remove-orphans'], env=env, stdout=(evidence / 'compose-down.log').open('w'), stderr=subprocess.STDOUT)
    summary = {'ok': success, 'image': image, 'mode': 'development',
        'scope': 'Installed kit integration, not legal compliance, real CA enrollment, or a population robustness benchmark',
        'video_profiles': ['economy_5s', 'economy_2s', 'resilient'],
        'processing_network': 'exporter/verifier internal; TLS edge dual bridge; external validator network none'}
    (evidence / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    events.close()
if not success:
    raise SystemExit(1)
