"""Private stock-media product emulator; persistent queue, real installed SDK."""
from contextlib import contextmanager
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import shutil
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

ROOT = Path(os.environ.get('PRODUCT_DATA', '/data'))
INPUTS = Path(os.environ.get('PRODUCT_INPUTS', '/inputs'))
CODE = Path(__file__).resolve().parent
CATALOG = {x['id']: x for x in json.loads((CODE / 'catalog.json').read_text())}
PROFILE = json.loads((CODE / 'product.json').read_text())
VERIFIER = os.environ.get('VERIFIER_URL', 'http://verifier:8080')
MAX_ATTEMPTS = int(os.environ.get('PRODUCT_MAX_ATTEMPTS', '3'))
if not 1 <= MAX_ATTEMPTS <= 10:
    raise ValueError('PRODUCT_MAX_ATTEMPTS must be 1–10')


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@contextmanager
def connect():
    db = sqlite3.connect(ROOT / 'jobs.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def init():
    ROOT.mkdir(exist_ok=True, parents=True)
    for name in ('results', 'staging', 'registry'):
        (ROOT / name).mkdir(exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, fixture TEXT NOT NULL,
            visible INTEGER NOT NULL, record TEXT NOT NULL, status TEXT NOT NULL,
            created TEXT NOT NULL, started TEXT, finished TEXT, attempts INTEGER DEFAULT 0,
            seconds REAL, error TEXT, result TEXT, verification TEXT)''')
        columns = {row[1] for row in db.execute('PRAGMA table_info(jobs)')}
        if 'video_profile' not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN video_profile TEXT NOT NULL DEFAULT 'fast'")
        if 'next_attempt' not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN next_attempt REAL NOT NULL DEFAULT 0")


def view(row):
    item = dict(row)
    for key in ('record', 'result', 'verification'):
        item[key] = json.loads(item[key]) if item[key] else None
    item['fixture_info'] = CATALOG[item['fixture']]
    if item['status'] == 'ready':
        item['download'] = f"/files/{item['id']}/media"
        item['receipt'] = f"/files/{item['id']}/receipt"
    return item


def get(job_id):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if row is None:
        raise KeyError('Job not found')
    return view(row)


class Conflict(ValueError):
    pass


def submit(body):
    if set(body) - {'fixture', 'visible', 'request_key', 'video_profile'}:
        raise ValueError('Unknown request fields')
    fixture = body.get('fixture')
    visible = body.get('visible', False)
    key = body.get('request_key', str(uuid4()))
    video_profile = body.get('video_profile', 'fast')
    if not isinstance(video_profile, str) or video_profile not in {'fast', 'resilient'}:
        raise ValueError('video_profile must be fast or resilient')
    if not isinstance(fixture, str) or fixture not in CATALOG or type(visible) is not bool:
        raise ValueError('Select a fixture and a boolean visible option')
    if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', key):
        raise ValueError('Invalid request key')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT * FROM jobs WHERE request_key=?', (key,)).fetchone()
        if old:
            if old['fixture'] != fixture or bool(old['visible']) != visible or old['video_profile'] != video_profile:
                raise Conflict('Request key already belongs to another export')
            return view(old), False
        if db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','processing')").fetchone()[0] >= 64:
            raise OverflowError('Queue is full')
        from ariadne_mark.provenance import ProvenanceRecord, GenerativeSystem, MediaKind, Action
        stamp = now()
        record = ProvenanceRecord.create(publisher=PROFILE['publisher'],
            system=GenerativeSystem(**PROFILE['system']), media_kind=MediaKind(CATALOG[fixture]['kind']),
            action=Action.CREATED, created_at=datetime.fromisoformat(stamp))
        job_id = str(uuid4())
        db.execute('INSERT INTO jobs(id,request_key,fixture,visible,record,status,created,video_profile) VALUES(?,?,?,?,?,?,?,?)',
                   (job_id, key, fixture, int(visible), record.to_json(), 'queued', stamp, video_profile))
    return get(job_id), True


def recover_interrupted_jobs():
    """Only called while holding the exclusive single-worker flock."""
    failed = []
    with connect() as db:
        for row in db.execute("SELECT id,attempts FROM jobs WHERE status='processing'").fetchall():
            if row['attempts'] >= MAX_ATTEMPTS:
                db.execute("UPDATE jobs SET status='failed', finished=?, error='worker_retry_limit' WHERE id=?", (now(), row['id']))
                failed.append(row['id'])
            else:
                db.execute("UPDATE jobs SET status='queued', next_attempt=? WHERE id=?", (time.time() + min(2 ** row['attempts'], 30), row['id']))
    for job_id in failed:
        if re.fullmatch(r'[0-9a-f-]{36}', job_id):
            shutil.rmtree(ROOT / 'staging' / job_id, ignore_errors=True)
    return failed


def worker():
    from ariadne_mark.pipeline import SDK
    from ariadne_mark.registry import Registry
    from ariadne_mark.signing import SigningIdentity
    from ariadne_mark.watermark import Watermarker
    from ariadne_mark.provenance import ProvenanceRecord
    # Exactly one queue consumer for this demo; OS releases lock on kill/restart.
    lock = (ROOT / 'worker.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    registry = Registry(ROOT / 'registry/assets.sqlite3')
    marker = Watermarker(threads=2)
    identity = SigningIdentity.from_directory(ROOT / 'identity', allow_dev=True)
    sdks = {p: SDK(marker, identity, registry, video_profile=p) for p in ('fast', 'resilient')}
    recover_interrupted_jobs()
    print('Worker ready; model instances reused across jobs', flush=True)
    while True:
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM jobs WHERE status='queued' AND next_attempt<=? ORDER BY created LIMIT 1", (time.time(),)).fetchone()
            if row:
                db.execute("UPDATE jobs SET status='processing', started=?, attempts=attempts+1, error=NULL WHERE id=?", (now(), row['id']))
        if not row:
            time.sleep(0.25)
            continue
        job = view(row)
        sdk = sdks[job['video_profile']]
        start = time.monotonic()
        stage = ROOT / 'staging' / job['id']
        final = ROOT / 'results' / job['id']
        fixture = CATALOG[job['fixture']]
        extension = '.mp4' if fixture['kind'] == 'video' else '.png'
        source = INPUTS / fixture['file']
        try:
            if sha(source) != fixture['sha256']:
                raise ValueError('Stock fixture checksum mismatch')
            record = ProvenanceRecord.from_json(json.dumps(job['record']))
            directory = final if final.exists() else stage
            directory.mkdir(exist_ok=True)
            output = directory / ('media' + extension)
            receipt_path = output.with_name(output.name + '.receipt.json')
            receipt = None
            # A crash before the media commit marker may leave a durable
            # receipt/registry row. This single-worker wrapper owns the job and
            # can remove only its unpublished binding before retrying.
            if not final.exists() and not output.exists():
                with registry.connect() as db:
                    abandoned = db.execute('SELECT token,sha256 FROM assets WHERE asset_id=?', (str(record.asset_id),)).fetchone()
                if abandoned:
                    registry.remove(abandoned[0], abandoned[1])
                receipt_path.unlink(missing_ok=True)
                for leftover in directory.glob('.ariadne-*'):
                    if leftover.is_dir():
                        shutil.rmtree(leftover)
            if receipt_path.exists():
                try:
                    receipt = json.loads(receipt_path.read_text())
                except json.JSONDecodeError:
                    if final.exists():
                        raise ValueError('Committed receipt is corrupt')
            if receipt:
                checked = sdk.verify(output)
                if (sha(output) != receipt['sha256'] or checked['c2pa'].get('record') != record.to_dict()
                        or checked['c2pa']['status'] != 'verified_claim'
                        or checked['watermark'].get('token') != receipt['token']):
                    raise ValueError('Interrupted export cannot be safely recovered')
                entry = registry.get(receipt['token'])
                expected = {'record': record.to_dict(), 'sha256': receipt['sha256']}
                if entry is None:
                    registry.add(receipt['token'], record, receipt['sha256'], receipt)
                elif entry != expected:
                    raise ValueError('Recovery registry conflict')
            else:
                if final.exists():
                    raise ValueError('Committed export has no valid receipt')
                output.unlink(missing_ok=True)
                receipt_path.unlink(missing_ok=True)
                receipt = sdk.mark(source, output, record, profile=PROFILE, visible=bool(job['visible']))
            if not final.exists():
                os.rename(stage, final)
            result = {'file': output.name, 'sha256': receipt['sha256'], 'token': receipt['token'],
                      'asset_id': receipt['asset_id'], 'sdk_seconds': receipt['seconds'],
                      'sdk_version': receipt['sdk_version'], 'fixture_sha256': fixture['sha256'],
                      'source_page': fixture['page'], 'test_fixture': True,
                      'profile_status': receipt['profile_assessment']['assessment_status']}
            with connect() as db:
                db.execute("UPDATE jobs SET status='ready', finished=?, seconds=?, result=? WHERE id=?",
                           (now(), round(time.monotonic() - start, 3), json.dumps(result), job['id']))
            print(json.dumps({'job': job['id'], 'status': 'ready', 'seconds': result['sdk_seconds']}), flush=True)
        except Exception as exc:
            with connect() as db:
                db.execute("UPDATE jobs SET status='failed', finished=?, error=? WHERE id=?", (now(), str(exc)[:500], job['id']))
            print(json.dumps({'job': job['id'], 'status': 'failed', 'error': str(exc)}), flush=True)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(120)

    def log_message(self, *args):
        pass

    def send(self, status, value, content_type='application/json'):
        payload = json.dumps(value).encode() if content_type == 'application/json' else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def file(self, path):
        size = path.stat().st_size
        first, last = 0, size - 1
        status = 200
        header = self.headers.get('Range')
        if header:
            match = re.fullmatch(r'bytes=(\d+)-(\d*)', header)
            if not match:
                return self.send(416, {'error': 'unsupported_range'})
            first = int(match[1]); last = min(int(match[2]) if match[2] else last, last)
            if not 0 <= first <= last < size:
                return self.send(416, {'error': 'invalid_range'})
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(last - first + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if status == 206:
            self.send_header('Content-Range', f'bytes {first}-{last}/{size}')
        self.end_headers()
        with path.open('rb') as stream:
            stream.seek(first)
            remaining = last - first + 1
            while remaining:
                block = stream.read(min(65536, remaining))
                if not block: break
                self.wfile.write(block); remaining -= len(block)

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == '/':
                return self.send(200, (CODE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/catalog':
                return self.send(200, [x for x in CATALOG.values() if not x.get('hidden')])
            if path == '/api/jobs':
                with connect() as db:
                    rows = db.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 100').fetchall()
                return self.send(200, [view(x) for x in rows])
            if path == '/health':
                return self.send(200, {'status': 'ready', 'product': 'stock-export-emulator'})
            if path.startswith('/api/jobs/'):
                return self.send(200, get(path.split('/')[-1]))
            if path.startswith('/stock/'):
                fixture = CATALOG[path.split('/')[-1]]
                if fixture.get('hidden'): raise KeyError()
                return self.file(INPUTS / fixture['file'])
            match = re.fullmatch(r'/files/([a-f0-9-]{36})/(media|receipt)', path)
            if match:
                job = get(match[1])
                if job['status'] != 'ready':
                    return self.send(409, {'error': 'Export is not ready'})
                file = ROOT / 'results' / job['id'] / job['result']['file']
                if match[2] == 'receipt': file = file.with_name(file.name + '.receipt.json')
                return self.file(file)
            raise KeyError()
        except (KeyError, FileNotFoundError):
            self.send(404, {'error': 'Not found'})

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.send(403, {'error': 'Cross-origin request rejected'})
        path = urlsplit(self.path).path
        try:
            if path == '/api/jobs':
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192 or self.headers.get('Transfer-Encoding'):
                    return self.send(413, {'error': 'Invalid request size'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict): raise ValueError('Expected JSON object')
                job, created = submit(body)
                return self.send(202 if created else 200, job)
            match = re.fullmatch(r'/api/jobs/([a-f0-9-]{36})/verify', path)
            if match:
                job = get(match[1])
                if job['status'] != 'ready': return self.send(409, {'error': 'Export is not ready'})
                media = ROOT / 'results' / job['id'] / job['result']['file']
                request = Request(VERIFIER + '/verify?format=' + media.suffix[1:],
                                  data=media.read_bytes(), headers={'Content-Type': 'application/octet-stream'})
                with urlopen(request, timeout=120) as response:
                    report = json.load(response)
                with connect() as db:
                    db.execute('UPDATE jobs SET verification=? WHERE id=?', (json.dumps(report), job['id']))
                return self.send(200, report)
            self.send(404, {'error': 'Not found'})
        except HTTPError as exc:
            status = exc.code if exc.code in {413, 415, 422, 429} else 502
            self.send(status, {'error': 'Verifier busy; retry shortly' if status == 429 else 'Verification service could not complete this check'})
        except Conflict as exc:
            self.send(409, {'error': str(exc)})
        except OverflowError as exc:
            self.send(429, {'error': str(exc)})
        except (ValueError, TypeError) as exc:
            self.send(400, {'error': str(exc)})
        except KeyError:
            self.send(404, {'error': 'Not found'})
        except Exception as exc:
            self.send(502, {'error': str(exc)[:300]})


if __name__ == '__main__':
    init()
    if len(sys.argv) > 1 and sys.argv[1] == 'worker':
        worker()
    else:
        ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
