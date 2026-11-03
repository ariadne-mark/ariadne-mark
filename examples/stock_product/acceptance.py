"""End-to-end acceptance against the running product, including worker loss."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8020')
    parser.add_argument('--verifier', default='http://127.0.0.1:8021')
    parser.add_argument('--compose-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    prefix = uuid4().hex[:10]
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'checks': [], 'exports': [],
              'scope': 'Private stock-generator replacement, real installed SDK, HTTP product + separate verifier, CPU. Not a durability or throughput qualification.'}

    def save():
        args.report.write_text(json.dumps(report, indent=2))

    def check(name, ok, details=None):
        report['checks'].append({'name': name, 'passed': bool(ok), 'details': details})
        save(); print(name, bool(ok), flush=True)
        if not ok: raise AssertionError(name)

    def request(path, value=None, *, base=None, raw=None, headers=None):
        data = json.dumps(value).encode() if value is not None else raw
        req = Request((base or args.base) + path, data=data, headers=headers or ({'Content-Type':'application/json'} if data else {}))
        try:
            with urlopen(req, timeout=120) as res:
                content = res.read()
                return res.status, content
        except HTTPError as exc:
            return exc.code, exc.read()

    def api(path, value=None):
        status, data = request(path, value)
        return status, json.loads(data)

    def wait(job_id, expected='ready', timeout=360):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _, job = api('/api/jobs/' + job_id)
            if job['status'] == expected: return job
            if job['status'] == 'failed' and expected != 'failed':
                raise AssertionError(job['error'])
            time.sleep(0.5)
        raise TimeoutError(job_id)

    def compose(*cmd):
        return subprocess.run(['docker', 'compose', '-p', 'ariadne-stock', *cmd],
                              cwd=args.compose_dir, check=True, capture_output=True, text=True, timeout=60)

    def ready():
        for _ in range(60):
            try:
                if request('/health')[0] == 200: return
            except (OSError, URLError): pass
            time.sleep(0.5)
        raise TimeoutError('Web did not recover')

    ready()
    _, catalog = api('/api/catalog')
    check('catalog_has_six_images_three_videos', len(catalog) == 9 and sum(x['kind']=='video' for x in catalog)==3)
    batch = []
    for fixture in catalog:
        body = {'fixture':fixture['id'], 'request_key':prefix+'-'+fixture['id'], 'visible':False}
        status, job = api('/api/jobs', body)
        if status != 202: raise AssertionError(job)
        batch.append(job)
    status, duplicate = api('/api/jobs', {'fixture':catalog[0]['id'], 'request_key':prefix+'-'+catalog[0]['id'], 'visible':False})
    check('duplicate_delivery_returns_same_job', status==200 and duplicate['id']==batch[0]['id'])
    status, _ = api('/api/jobs', {'fixture':catalog[1]['id'], 'request_key':prefix+'-'+catalog[0]['id']})
    check('conflicting_idempotency_key_rejected', status==409)
    status, _ = api('/api/jobs', {'fixture':'../../identity/private_key.pem'})
    check('arbitrary_source_path_rejected', status==400)
    for queued in batch:
        job = wait(queued['id'])
        status, result = api('/api/jobs/'+job['id']+'/verify', {})
        check('verify_'+job['fixture'], status==200 and result['c2pa']['status']=='verified_claim'
              and result['watermark'].get('token')==job['result']['token'] and result['recovery']['status']=='found',
              {'sdk_seconds':job['result']['sdk_seconds'],'issuer_trust':result.get('c2pa',{}).get('issuer_trust'),'response':result if status!=200 else None})
        status, data = request(job['download'])
        check('download_'+job['fixture'], status==200 and hashlib.sha256(data).hexdigest()==job['result']['sha256'])
        _, receipt = request(job['receipt'])
        receipt = json.loads(receipt)
        check('profile_receipt_'+job['fixture'], receipt['sdk_version']=='0.4.0a0'
              and receipt['profile_assessment']['legal_determination']=='not_performed'
              and receipt['profile_assessment']['configuration_status']=='valid')
        report['exports'].append({'job_id':job['id'], 'fixture':job['fixture'], 'kind':job['fixture_info']['kind'],
                                 **job['result'], 'worker_seconds':job['seconds']})
        save()
    video = next(j for j in batch if j['fixture_info']['kind']=='video')
    video = api('/api/jobs/'+video['id'])[1]
    status, ranged = request(video['download'], headers={'Range':'bytes=0-1023'})
    check('video_byte_ranges_supported',status==206 and len(ranged)==1024)
    _, bad = api('/api/jobs', {'fixture':'invalid-fixture','request_key':prefix+'-bad'})
    failed = wait(bad['id'],'failed')
    status, _ = request('/files/'+bad['id']+'/media')
    check('corrupt_input_fails_without_download',status==409 and bool(failed['error']))
    _, visible = api('/api/jobs', {'fixture':catalog[0]['id'],'visible':True,'request_key':prefix+'-visible'})
    visible = wait(visible['id'])
    status, checked = api('/api/jobs/'+visible['id']+'/verify',{})
    check('visible_label_is_in_signed_claim',status==200 and checked['c2pa']['visible_disclosure'] is True)
    _, restart = api('/api/jobs', {'fixture':'waterfall','request_key':prefix+'-restart'})
    wait(restart['id'],'processing')
    time.sleep(2)  # Interrupt real inference, not merely a queued item.
    compose('stop','-t','0','worker')
    _, interrupted = api('/api/jobs/'+restart['id'])
    status, _ = request('/files/'+restart['id']+'/media')
    check('worker_killed_mid_export_no_partial_download', interrupted['status']=='processing' and status==409)
    compose('start','worker')
    recovered = wait(restart['id'])
    status, checked = api('/api/jobs/'+restart['id']+'/verify',{})
    check('worker_restart_recovers_job', recovered['attempts']==2 and status==200
          and checked['watermark'].get('token')==recovered['result']['token'])
    before = recovered['result']
    compose('restart','web','verifier')
    ready()
    # Verifier may still be initializing after the HTTP process is ready.
    for _ in range(60):
        try:
            if request('/health',base=args.verifier)[0]==200:break
        except (OSError,URLError): pass
        time.sleep(.5)
    _, after = api('/api/jobs/'+restart['id'])
    status, checked = api('/api/jobs/'+restart['id']+'/verify',{})
    check('web_and_verifier_restart_preserve_results',after['result']==before and status==200 and checked['recovery']['status']=='found')
    # The source is unmarked: absence must remain a negative result, not an AI verdict.
    stock = request('/stock/'+catalog[0]['id'])[1]
    status, raw = request('/verify?format=png',base=args.verifier,raw=stock,headers={'Content-Type':'application/octet-stream'})
    unmarked = json.loads(raw)
    check('unmarked_stock_not_claimed_as_marked', status==200 and unmarked['c2pa']['status']=='not_found' and unmarked['watermark']['status']=='not_found')
    # Re-encode a marked PNG without metadata, then check the separate resolver.
    image = next(j for j in batch if j['fixture_info']['kind']=='image')
    image = api('/api/jobs/'+image['id'])[1]
    conversion = "import io,sys;from PIL import Image;b=io.BytesIO();Image.open(sys.argv[1]).convert('RGB').save(b,format='JPEG',quality=90);sys.stdout.buffer.write(b.getvalue())"
    converted = subprocess.run(['docker','compose','-p','ariadne-stock','exec','-T','worker','python','-c',conversion,
                                '/data/results/'+image['id']+'/'+image['result']['file']],cwd=args.compose_dir,
                               check=True,capture_output=True,timeout=30).stdout
    status, raw = request('/verify?format=jpg',base=args.verifier,raw=converted,headers={'Content-Type':'application/octet-stream'})
    recovered_mark = json.loads(raw)
    check('metadata_stripped_image_recovers_source_record', status==200
          and recovered_mark['c2pa']['status']=='not_found'
          and recovered_mark['watermark'].get('token')==image['result']['token']
          and recovered_mark['recovery']['status']=='found')
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    report['passed'] = sum(x['passed'] for x in report['checks'])
    report['total'] = len(report['checks'])
    save()
    print(json.dumps({'passed':report['passed'],'total':report['total']}),flush=True)


if __name__ == '__main__':
    main()
