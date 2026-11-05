"""Small self-hosted verifier: bounded uploads, single inference, no persistence."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import io
from pathlib import Path
import tempfile
import threading
import time
import socket
from urllib.parse import parse_qs, urlsplit

HTML = b'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Ariadne Mark verifier</title><style>body{font:17px system-ui;max-width:760px;margin:60px auto;padding:24px;background:#f7f8f5;color:#17382c}button{padding:12px 20px;background:#17382c;color:white;border:0;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px;border-radius:12px}small{display:block;margin:20px 0}</style>
<h1>Check content provenance</h1><p>Inspect C2PA credentials and Ariadne Mark watermarks in JPEG, PNG or MP4.</p>
<input id="file" type="file" accept=".jpg,.jpeg,.png,.mp4"><button id="check">Check file</button>
<small>Files are processed by this server and deleted after the request. No account required. An absent mark does not establish human origin. A valid credential does not establish factual truth.</small>
<h2 id="label"></h2><pre id="result">Choose a file to begin.</pre><p id="feedback"></p>
<script>
fetch('/health').then(r=>r.json()).then(x=>{if(x.feedback_url){let a=document.createElement('a');a.href=x.feedback_url;a.textContent='Report an issue with this verification';a.rel='noopener noreferrer';document.getElementById('feedback').append(a)}});
document.getElementById('check').onclick=async()=>{let f=document.getElementById('file').files[0];if(!f)return;
let b=document.getElementById('check');b.disabled=true;document.getElementById('label').textContent='Checking...';
try{let ext=f.name.split('.').pop().toLowerCase();let r=await fetch('/verify?format='+encodeURIComponent(ext),{method:'POST',body:f,headers:{'Content-Type':'application/octet-stream'}});let x=await r.json();document.getElementById('label').textContent=x.label||x.error||'Unable to check';document.getElementById('result').textContent=JSON.stringify(x,null,2)}catch(e){document.getElementById('label').textContent='Check failed'}finally{b.disabled=false}};
</script></html>'''


class _DeadlineReader(io.RawIOBase):
    """Apply one total deadline across every socket read of request headers."""
    def __init__(self, connection):
        super().__init__()
        self.connection = connection
        self.deadline = None

    def readable(self):
        return True

    def readinto(self, buffer):
        if self.deadline is not None:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('header_deadline')
            self.connection.settimeout(remaining)
        return self.connection.recv_into(buffer)


def make_server(sdk, *, host="127.0.0.1", port=8080, max_upload_mb=512, feedback_url=None,
                upload_timeout=120, upload_slots=4, production=False, header_timeout=10):
    if not 1 <= max_upload_mb <= 512:
        raise ValueError("max_upload_mb must be between 1 and 512")
    if feedback_url and urlsplit(feedback_url).scheme not in {"https", "http"}:
        raise ValueError("feedback URL must use HTTPS or HTTP")
    if not 0 < upload_timeout <= 3600 or not 1 <= upload_slots <= 16 or not 0 < header_timeout <= 30:
        raise ValueError("Invalid upload deadline or slots")
    if production:
        if not getattr(sdk, "trust_anchors", None):
            raise ValueError("Production verification requires configured trust anchors")
        from ariadne_mark.signing import validate_trust_roots
        validate_trust_roots(sdk.trust_anchors)
    gate = threading.BoundedSemaphore(1)
    uploads = threading.BoundedSemaphore(upload_slots)
    limit = max_upload_mb * 1024 * 1024

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.rfile.close()
            self._request_reader = _DeadlineReader(self.connection)
            self.rfile = io.BufferedReader(self._request_reader)
            self.connection.settimeout(30)

        def handle_one_request(self):
            self._request_reader.deadline = time.monotonic() + header_timeout
            return super().handle_one_request()

        def parse_request(self):
            result = super().parse_request()
            self._request_reader.deadline = None
            self.connection.settimeout(30)
            return result

        def log_message(self, format, *args):
            pass  # No IPs, filenames or upload content in default logs.

        def respond(self, status, data, content_type="application/json"):
            payload = json.dumps(data).encode() if content_type == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/":
                self.respond(200, HTML, "text/html; charset=utf-8")
            elif self.path == "/health":
                self.respond(200, {"status": "ready", "max_upload_bytes": limit, "feedback_url": feedback_url})
            else:
                self.respond(404, {"error": "not_found"})

        def do_POST(self):
            url = urlsplit(self.path)
            if url.path != "/verify":
                self.respond(404, {"error": "not_found"})
                return
            ext = parse_qs(url.query).get("format", [""])[0]
            if ext not in {"png", "jpg", "jpeg", "mp4"}:
                self.respond(415, {"error": "unsupported_format"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 0 < length <= limit or self.headers.get("Transfer-Encoding"):
                self.respond(413, {"error": "invalid_upload_size"})
                return
            if not uploads.acquire(blocking=False):
                self.respond(429, {"error": "upload_slots_busy"})
                self.close_connection = True
                return
            inference_acquired = False
            try:
                with tempfile.TemporaryDirectory(prefix="ariadne-upload-") as directory:
                    path = Path(directory) / ("upload." + ext)
                    with path.open("wb") as file:
                        remaining = length
                        deadline = time.monotonic() + upload_timeout
                        while remaining:
                            left = deadline - time.monotonic()
                            if left <= 0:
                                raise TimeoutError("upload_deadline")
                            self.connection.settimeout(min(5, left))
                            chunk = self.rfile.read1(min(65536, remaining))
                            if not chunk:
                                raise ValueError("incomplete_upload")
                            file.write(chunk)
                            remaining -= len(chunk)
                    # Slow senders consume a bounded upload slot, never the
                    # model's only inference slot.
                    inference_acquired = gate.acquire(blocking=False)
                    if not inference_acquired:
                        self.respond(429, {"error": "verifier_busy"})
                        return
                    report = sdk.verify(path)
                # Temporary files are deleted before the response is returned.
                self.respond(200, report)
            except (TimeoutError, socket.timeout):
                self.close_connection = True
                self.respond(408, {"error": "upload_timeout", "status": "not_checked"})
            except Exception:
                self.respond(422, {"error": "verification_failed", "status": "not_checked"})
            finally:
                if inference_acquired:
                    gate.release()
                uploads.release()

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        block_on_close = False

        def __init__(self, *args, **kwargs):
            self.handlers = threading.BoundedSemaphore(16)
            super().__init__(*args, **kwargs)

        def process_request(self, request, address):
            if not self.handlers.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, address)
            except BaseException:
                self.handlers.release()
                raise

        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                self.handlers.release()

        def handle_error(self, request, client_address):
            # The stdlib default includes client IPs in exception logs.
            # Do not retain them for failed/disconnected uploads either.
            pass

    return Server((host, port), Handler)


def serve(sdk, **kwargs):
    server = make_server(sdk, **kwargs)
    print(f"Verifier listening on http://{server.server_address[0]}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
