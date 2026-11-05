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
from ariadne_mark.errors import VerificationTimeout

from importlib.resources import files
from ariadne_mark.public_verifier import public_report, public_record, load_public_sources, FeedbackStore
from ariadne_mark.watermark import valid_token
from ariadne_mark.version import sdk_version

ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "application/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/privacy": ("privacy.html", "text/html; charset=utf-8"),
          "/feedback": ("feedback.html", "text/html; charset=utf-8"),
          "/feedback.js": ("feedback.js", "application/javascript; charset=utf-8"),
          "/openapi.json": ("openapi.json", "application/json")}



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
                upload_timeout=120, upload_slots=4, production=False, header_timeout=10,
                public_sources=None, feedback_db=None):
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
    sources = load_public_sources(public_sources)
    feedback = FeedbackStore(feedback_db) if feedback_db is not None else None
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
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path in ASSETS:
                name, content_type = ASSETS[url.path]
                payload = files('ariadne_mark').joinpath('verifier_assets', name).read_bytes()
                self.respond(200, json.loads(payload) if content_type == "application/json" else payload, content_type)
            elif url.path == "/health":
                self.respond(200, {"status": "ready", "version": sdk_version(),
                    "max_upload_bytes": limit, "formats": ["jpg", "jpeg", "png", "mp4"],
                    "feedback_enabled": feedback is not None, "feedback_url": feedback_url,
                    "public_source_profiles": len(sources), "public_output": "reviewed_system_fields_only",
                    "video_search": {"max_frames": 2000, "max_seconds": 120},
                    "universal_ai_detector": False})
            elif url.path.startswith('/records/'):
                token = url.path[len('/records/'):]
                if not valid_token(token):
                    self.respond(400, {"error": "invalid_asset_id"})
                    return
                registry = getattr(sdk, 'registry', None)
                try:
                    stored = registry.get(token) if registry is not None else None
                    if stored is None:
                        self.respond(404, {"status": "unknown_id"})
                    else:
                        record, redacted = public_record(stored.get('record'), sources)
                        self.respond(200, {"status": "found", "token": token, "record": record,
                            "binding": "registry_entry_not_authentication_of_a_copy",
                            "public_output": {"policy": "reviewed_system_fields_only", "redacted_fields": redacted}})
                except Exception:
                    self.respond(503, {"status": "not_checked", "error": "registry_unavailable"})
            else:
                self.respond(404, {"error": "not_found"})

        def receive_feedback(self):
            if feedback is None:
                self.respond(503, {"error": "feedback_not_configured"})
                return
            acquired = False
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2048 or self.headers.get('Transfer-Encoding'):
                    self.respond(413, {"error": "invalid_feedback_size"})
                    return
                acquired = uploads.acquire(blocking=False)
                if not acquired:
                    self.respond(429, {"error": "upload_slots_busy"})
                    return
                deadline, raw = time.monotonic() + 5, bytearray()
                while len(raw) < length:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise TimeoutError('feedback_deadline')
                    self.connection.settimeout(min(1, left))
                    chunk = self.rfile.read1(length - len(raw))
                    if not chunk:
                        raise ValueError('incomplete_feedback')
                    raw.extend(chunk)
                feedback.add(json.loads(raw))
                self.respond(202, {"status": "recorded", "storage": "aggregate_counters_only"})
            except (ValueError, UnicodeError):
                self.respond(400, {"error": "invalid_feedback", "allowed": "rating_and_media_enums_only"})
            except (TimeoutError, socket.timeout):
                self.close_connection = True
                self.respond(408, {"error": "feedback_timeout"})
            except Exception:
                self.respond(503, {"error": "feedback_unavailable"})
            finally:
                if acquired:
                    uploads.release()

        def do_POST(self):
            url = urlsplit(self.path)
            if url.path == "/feedback":
                self.receive_feedback()
                return
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
                self.respond(200, public_report(report, sources))
            except (TimeoutError, socket.timeout):
                self.close_connection = True
                self.respond(408, {"error": "upload_timeout", "status": "not_checked"})
            except VerificationTimeout:
                self.respond(504, {"error": "verification_timeout", "status": "not_checked"})
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
        close = getattr(sdk, 'close', None)
        if close:
            close()
