"""Pinned TrustMark-Q CPU video profiles; persistent binary Node/ONNX worker."""
from types import SimpleNamespace
import atexit, contextlib, hashlib, json, os, queue, shutil, struct, subprocess, tempfile, threading
from pathlib import Path
from ariadne_mark.errors import AriadneError, MissingModel, UnsupportedMedia
from ariadne_mark.watermark import valid_token
from ariadne_mark.video.policy import DEFAULT_PROFILE, validate_profile
ROOT = Path(__file__).parent
ALGORITHM = 'adobe.trustmark.Q.variax-bch5'
FORMAT = 'ariadne-vq1'
MODELS = {'encoder_Q.onnx': '19b3d1b25836130ffd78775a8f61539f993375d1823ef0e59ba5b8dffb4f892d', 'decoder_Q.onnx': 'ee3268f057c9dabef680e169302f5973d0589feea86189ed229a896cc3aa88df'}
ORIGINAL = '1de62f33353525b11cb38f89c56f8b07fd8ca241092d67ce5a74bdfb5c8db3d3'
PATCHED = 'b9a1c7035bed4c35a5a0e61ff423b4fae34781634a565b56d14dfc92e2927b31'
STDERR_TAIL = 4096  # bytes of worker stderr kept in memory for last_error

def data_dir():
    explicit = os.environ.get('ARIADNE_VIDEO_DATA')
    if explicit:
        return Path(explicit)
    from ariadne_mark.paths import cache_path
    return cache_path('video-v1')

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def native_hashes(d):
    root = d / 'runtime'
    binary = root / 'node_modules/onnxruntime-node/bin'
    return {str(p.relative_to(root)): digest(p) for p in sorted(binary.rglob('*'))
            if p.is_file() and (p.suffix in {'.node', '.so', '.dylib', '.dll'} or '.so.' in p.name)}


def installation_matches(d):
    receipt = d / 'runtime/ariadne-install.json'
    adm = d / 'runtime/node_modules/adm-zip/package.json'
    try:
        return (json.loads(receipt.read_text()).get('lock_sha256') == digest(ROOT / 'package-lock.json')
                and json.loads(adm.read_text()).get('version') == '0.6.1'
                and bool(json.loads(receipt.read_text()).get('native_sha256'))
                and json.loads(receipt.read_text())['native_sha256'] == native_hashes(d))
    except (OSError, ValueError):
        return False

def check_models():
    d = data_dir()
    if not (d / 'runtime/ariadne-install.json').exists():
        raise MissingModel('Video runtime not provisioned; run ariadne models fetch --engine video')
    if not installation_matches(d):
        raise MissingModel('Video dependency policy changed; run ariadne models fetch --engine video')
    receipt = json.loads((d / 'runtime/ariadne-install.json').read_text())
    if native_hashes(d) != receipt['native_sha256']:
        raise MissingModel('Native ONNX runtime checksum mismatch; run ariadne models fetch --engine video')
    p = d / 'runtime/node_modules/@variax-ai/video-watermark/dist/index.cjs'
    if not p.is_file() or digest(p) != PATCHED:
        raise MissingModel('Video runtime missing/checksum mismatch; run ariadne models fetch --engine video')
    for name, sha in MODELS.items():
        p = d / 'models' / name
        if not p.is_file() or digest(p) != sha:
            raise MissingModel('Video ONNX model missing/checksum mismatch; run ariadne models fetch --engine video')
    ort = d / 'runtime/node_modules/onnxruntime-node/package.json'
    if not ort.is_file() or json.loads(ort.read_text()).get('version') != '1.23.2':
        raise MissingModel('Pinned CPU ONNX runtime missing; run ariadne models fetch --engine video')
    if not shutil.which('node'):
        raise MissingModel('Node.js is required for video; use the Docker image or install Node.js')
    return {'runtime_js_sha256': PATCHED, **MODELS}

def fetch_models():
    # Frozen Docker runtime needs only Node; npm belongs to the build stage.
    try:
        return check_models()
    except MissingModel:
        pass
    import urllib.request
    d = data_dir()
    runtime = d / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    if not shutil.which('npm') or not shutil.which('node'):
        raise MissingModel('Install Node.js20+ and npm, or use the Docker image')
    for name in ['package.json', 'package-lock.json']:
        shutil.copyfile(ROOT / name, runtime / name)
    p = runtime / 'node_modules/@variax-ai/video-watermark/dist/index.cjs'
    ort = runtime / 'node_modules/onnxruntime-node/package.json'
    if not installation_matches(d) or not p.exists() or digest(p) != PATCHED or (not ort.is_file()) or (json.loads(ort.read_text()).get('version') != '1.23.2'):
        # A throwaway npm cache: provisioning never writes ~/.npm (ISS-08).
        with tempfile.TemporaryDirectory(prefix='.npm-cache-', dir=d) as npm_cache:
            env = {**os.environ, 'ONNXRUNTIME_NODE_INSTALL_CUDA': 'skip', 'npm_config_cache': npm_cache}
            try:
                subprocess.run(['npm', 'ci', '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=runtime, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            except (subprocess.SubprocessError, OSError) as exc:
                raise MissingModel('Could not provision CPU video runtime; check Node/npm and network access') from exc
        if digest(p) != ORIGINAL:
            raise MissingModel('Unexpected upstream video runtime; refusing to patch')
        s = p.read_text()
        old = '          signature,\n          region'
        if s.count(old) != 1:
            raise MissingModel('Unsupported upstream signature cache layout')
        p.write_text(s.replace(old, '          signature: signature.slice(),\n          region'))
        (runtime / 'ariadne-install.json').write_text(json.dumps({'lock_sha256': digest(ROOT / 'package-lock.json'), 'runtime_js_sha256': PATCHED, 'native_sha256': native_hashes(d)}))
    model = d / 'models'
    model.mkdir(exist_ok=True)
    for name, sha in MODELS.items():
        path = model / name
        if path.exists() and digest(path) == sha:
            continue
        fd, tmp = tempfile.mkstemp(dir=model, prefix='.download-')
        try:
            total = 0
            with os.fdopen(fd, 'wb') as f, urllib.request.urlopen('https://cai-watermark.adobe.net/watermarking/trustmark-models/' + name, timeout=90) as response:
                for b in iter(lambda: response.read(1048576), b''):
                    total += len(b)
                    if total > 512 * 1024 * 1024:
                        raise MissingModel('Model size exceeded')
                    f.write(b)
            if digest(Path(tmp)) != sha:
                raise MissingModel('Video model checksum mismatch')
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return check_models()

class VideoWatermarker:
    algorithm = ALGORITHM
    payload_format = FORMAT
    implementation = 'node-onnxruntime-variax-video-watermark'
    batch_size = 1

    def __init__(self, *, profile=DEFAULT_PROFILE, threads=2, timeout=120):
        validate_profile(profile)
        if not 1 <= threads <= 64:
            raise ValueError('threads must be1–64')
        self.profile = profile
        self.profile_id = {'fast': 'fast-cpu-v2', 'resilient': 'resilient-cpu-candidate-v1',
                           'economy_5s': 'economy-5s-125ms-cpu-v1',
                           'economy_2s': 'economy-2s-125ms-cpu-v1'}[profile]
        self.threads = threads
        self.timeout = timeout
        # Worker state lives in one holder so profile views can share it.
        self._worker = SimpleNamespace(_lock=threading.RLock(), _process=None, _owner=None,
                                       _cleanup_registered=False)
        self._lock = self._worker._lock
        self._process = None
        self._owner = None
        self._token = None
        self.stats = {}
        self.last_error = None
        self._cleanup_registered = False

    def with_profile(self, profile):
        """Another preset on the SAME Node worker process (ISS-12).

        The worker is profile-agnostic: the preset is sent with each encoding
        session and its state is reset at begin/end, and every preset loads the
        same two ONNX models. Separate processes per preset only duplicated
        those models. The shared lock serialises whole sessions, as it already
        did for concurrent exports of one preset.
        """
        validate_profile(profile)
        view = VideoWatermarker(profile=profile, threads=self.threads, timeout=self.timeout)
        view._worker = self._worker
        return view

    def _load(self):
        if self._process and self._owner == os.getpid() and (self._process.poll() is None):
            return
        if self._process:
            self.close()
        check_models()
        d = data_dir().resolve()
        self._responses = queue.Queue()
        self._process = subprocess.Popen(['node', str(ROOT / 'worker.mjs'), str(d / 'runtime'), str(d / 'models'), str(self.threads)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._start_stderr_drain(self._process)
        self._owner = os.getpid()
        if not self._cleanup_registered:
            atexit.register(self.close)
            self._cleanup_registered = True
        process = self._process
        responses = self._responses

        def read_exact(n):
            chunks = []
            while n:
                b = process.stdout.read(n)
                if not b:
                    raise EOFError('video worker exited')
                chunks.append(b)
                n -= len(b)
            return b''.join(chunks)

        def reader():
            try:
                while True:
                    n = struct.unpack('>I', read_exact(4))[0]
                    if n > 65536:
                        raise ValueError('oversized worker header')
                    h = json.loads(read_exact(n))
                    size = h.get('n', 0)
                    if not isinstance(size, int) or not 0 <= size <= 67108864:
                        raise ValueError('oversized worker response')
                    responses.put((h, read_exact(size)))
            except Exception as e:
                responses.put(e)
        threading.Thread(target=reader, daemon=True).start()
        self._receive()

    def _start_stderr_drain(self, process):
        """Keep only the last STDERR_TAIL bytes; the pipe is always drained.

        Diagnostics stay on this object (last_error). They are never added to
        exception messages, verifier IPC or public output, and cannot grow a
        file or memory without bound over a long-lived worker.
        """
        tail, lock = bytearray(), threading.Lock()
        self._stderr_tail, self._stderr_lock = tail, lock

        def drain():
            try:
                while True:
                    data = process.stderr.read1(STDERR_TAIL)
                    if not data:
                        return
                    with lock:
                        tail.extend(data)
                        del tail[:-STDERR_TAIL]
            except (OSError, ValueError):
                return
        self._stderr_thread = threading.Thread(target=drain, daemon=True)
        self._stderr_thread.start()

    def _capture_stderr(self):
        lock = getattr(self, '_stderr_lock', None)
        if lock is None:
            return
        with lock:
            text = bytes(self._stderr_tail).decode(errors='replace').strip()
        if text:
            self.last_error = text

    def _fail(self, message, cause=None):
        self.close()
        self._capture_stderr()
        raise AriadneError(message) from cause

    def _receive(self):
        try:
            r = self._responses.get(timeout=self.timeout)
        except queue.Empty:
            self._fail('Video worker timed out')
        if isinstance(r, Exception):
            self._fail('Video worker failed: ' + str(r), r)
        if r[0].get('error'):
            raise AriadneError(r[0]['error'])
        return r

    def _request(self, h, body=b''):
        self._load()
        h = {**h, 'n': len(body)}
        head = json.dumps(h).encode()
        p = self._process
        try:
            p.stdin.write(struct.pack('>I', len(head)) + head)
            p.stdin.write(body)
            p.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._fail('Video worker pipe failed', exc)
        return self._receive()

    @contextlib.contextmanager
    def encoding_session(self, token):
        if not valid_token(token):
            raise ValueError('Invalid token')
        with self._lock:
            self._request({'op': 'begin', 'profile': self.profile, 'token': token})
            process = self._process
            self._token = token
            result = SimpleNamespace(stats={})
            try:
                yield result
                if process.poll() is not None:
                    raise AriadneError('Video worker exited before export completed')
                result.stats = self._request({'op': 'end'})[0]
                if self._process is not process:
                    raise AriadneError('Video worker restarted before export completed')
                self.stats = result.stats
            except BaseException:
                self.close()
                raise
            finally:
                self._token = None

    def encode_frames(self, images, token):
        with self._lock:
            from PIL import Image
            if self._token != token:
                raise AriadneError('Video encoding requires a per-export session')
            result = []
            for image in images:
                image = image.convert('RGBA')
                h, body = self._request({'op': 'encode', 'width': image.width, 'height': image.height}, image.tobytes())
                if len(body) != image.width * image.height * 4:
                    raise AriadneError('Incomplete encoded frame')
                result.append(Image.frombytes('RGBA', image.size, body).convert('RGB'))
            return result

    def decode_frames(self, frames):
        with self._lock:
            self._load()
            rows = []
            logits = []
            for image, timestamp in frames:
                image = image.convert('RGBA')
                h, _ = self._request({'op': 'decode', 'width': image.width, 'height': image.height}, image.tobytes())
                rows.append({'time': timestamp, 'token': h['token']})
                logits.append(h['logits'])
            h, _ = self._request({'op': 'aggregate', 'logits': logits}) if logits else ({'token': None}, b'')
            return (rows, {'token': h['token']} if h['token'] else None)

    def decode_logits(self, image):
        """Return one fresh decoder observation; no expected payload is accepted."""
        with self._lock:
            image = image.convert('RGBA')
            h, _ = self._request({'op': 'decode', 'width': image.width, 'height': image.height}, image.tobytes())
            return h['token'], h['logits']

    def aggregate_logits(self, logits):
        with self._lock:
            return self._request({'op': 'aggregate', 'logits': logits})[0].get('token')

    def scan_video(self, path, *, max_frames=2000, max_seconds=120, max_hypotheses=512):
        from ariadne_mark.video.detection import scan_video
        # One worker operation owns its decoder state through the complete scan.
        with self._lock:
            return scan_video(path, self, max_frames=max_frames, max_seconds=max_seconds,
                              max_hypotheses=max_hypotheses)

    def close(self):
        """Stop the shared worker process (idempotent for every profile view)."""
        if self._cleanup_registered:
            atexit.unregister(self.close)
            self._cleanup_registered = False
        p = self._process
        if p and self._owner == os.getpid():
            if p.poll() is None:
                p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
            # The pipe reaches EOF once the worker has exited; join briefly so
            # its final diagnostic lines are kept before the stream is closed.
            thread = getattr(self, '_stderr_thread', None)
            if thread is not None:
                thread.join(timeout=1)
            for f in [p.stdin, p.stdout, p.stderr]:
                if f:
                    f.close()
        self._process = None
        self._token = None


def _shared(name):
    return property(lambda self: getattr(self._worker, name, None),
                    lambda self, value: setattr(self._worker, name, value))


for _name in ('_lock', '_process', '_owner', '_responses', '_stderr_tail', '_stderr_lock',
              '_stderr_thread', '_cleanup_registered'):
    setattr(VideoWatermarker, _name, _shared(_name))
del _name
