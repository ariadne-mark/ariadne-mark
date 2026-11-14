"""Small self-hosted verifier: bounded uploads, single inference, no persistence."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
import io
from pathlib import Path
import tempfile
import threading
import time
import socket
from urllib.parse import parse_qs, urlsplit, unquote
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
                public_sources=None, feedback_db=None, report_signer=None, public_manifests=False):
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
    if production and report_signer is None:
        raise ValueError("Production verifier requires a separate report signing key")
    if type(public_manifests) is not bool:
        raise ValueError('public_manifests must be a boolean')
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
            elif url.path == '/services/supportedAlgorithms' and public_manifests:
                from ariadne_mark.softbinding import ALGORITHMS
                self.respond(200, {'watermarks': [{'alg': a} for a in ALGORITHMS.values()],
                    'registration_status': 'provisional_not_registered', 'profile': 'read_only'})
            elif url.path == '/matches/byBinding' and public_manifests:
                try:
                    query = parse_qs(url.query, strict_parsing=True)
                    if any(len(v) != 1 for v in query.values()) or set(query) - {'alg','value','maxResults'}:
                        raise ValueError('Invalid query parameters')
                    self.resolve_binding(query['alg'][0], query['value'][0], query.get('maxResults', ['10'])[0])
                except (ValueError, KeyError):
                    self.respond(400, {'error': 'invalid_binding_query'})
            elif url.path.startswith('/manifests/') and public_manifests:
                from ariadne_mark.softbinding import manifest_id_valid
                manifest_id = unquote(url.path[len('/manifests/'):])
                query = parse_qs(url.query)
                if not manifest_id_valid(manifest_id) or set(query) - {'returnActiveManifest'}:
                    self.respond(400, {'error': 'invalid_manifest_query'})
                elif query.get('returnActiveManifest', ['false']) != ['false']:
                    self.respond(400, {'error': 'active_only_not_supported', 'supported': 'full_manifest_store'})
                else:
                    try:
                        registry = getattr(sdk, 'registry', None)
                        bundle = registry.get_manifest(manifest_id=manifest_id, public_only=True) if registry else None
                        if bundle is None:
                            self.respond(404, {'error': 'manifest_not_found'})
                        else:
                            self.respond(200, bundle['bytes'], 'application/c2pa')
                    except Exception:
                        self.respond(503, {'error': 'manifest_store_unavailable'})
            elif url.path == "/report-key":
                if report_signer is None:
                    self.respond(404, {"error": "report_signing_not_configured"})
                else:
                    self.respond(200, {"verifier_id": report_signer.verifier_id,
                        "keys": [report_signer.public_jwk()]})
            elif url.path == "/report-key.pem":
                if report_signer is None:
                    self.respond(404, {"error": "report_signing_not_configured"})
                else:
                    self.respond(200, report_signer.public_pem(), "application/x-pem-file")
            elif url.path == "/health":
                self.respond(200, {"status": "ready", "version": sdk_version(),
                    "max_upload_bytes": limit, "formats": ["jpg", "jpeg", "png", "mp4"],
                    "c2pa_manifest_recovery": {'enabled': public_manifests, 'profile': 'read_only',
                        'algorithm_registration': 'provisional_not_registered'},
                    "signed_reports": report_signer is not None,
                    "report_verifier_id": report_signer.verifier_id if report_signer else None,
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

        def resolve_binding(self, algorithm, value, maximum='10'):
            from ariadne_mark.softbinding import decode_query
            token = decode_query(algorithm, value)
            if not isinstance(maximum, str) or len(maximum) > 3 or not maximum.isdecimal() or not 1 <= int(maximum) <= 100:
                raise ValueError('maxResults must be 1–100')
            try:
                registry = getattr(sdk, 'registry', None)
                bundle = registry.get_manifest(token=token, public_only=True) if registry else None
                matches = [{'manifestId': bundle['id']}] if bundle and bundle['algorithm'] == algorithm else []
                self.respond(200, {'matches': matches})
            except Exception:
                self.respond(503, {'error': 'manifest_store_unavailable'})

        def receive_binding_query(self, url):
            acquired = False
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2048 or self.headers.get('Transfer-Encoding'):
                    self.respond(413, {'error': 'invalid_query_size'})
                    return
                query = parse_qs(url.query, strict_parsing=True)
                if set(query) - {'maxResults'} or any(len(v) != 1 for v in query.values()):
                    raise ValueError('Invalid query parameters')
                acquired = uploads.acquire(blocking=False)
                if not acquired:
                    self.respond(429, {'error': 'upload_slots_busy'})
                    return
                deadline, raw = time.monotonic() + 5, bytearray()
                while len(raw) < length:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise TimeoutError('query_deadline')
                    self.connection.settimeout(min(1, left))
                    chunk = self.rfile.read1(length - len(raw))
                    if not chunk:
                        raise ValueError('incomplete_query')
                    raw.extend(chunk)
                from ariadne_mark.reports import _strict_json
                body = _strict_json(raw)
                if not isinstance(body, dict) or set(body) != {'alg','value'}:
                    raise ValueError('Invalid binding query')
                self.resolve_binding(body['alg'], body['value'], query.get('maxResults', ['10'])[0])
            except (ValueError, KeyError, UnicodeError):
                self.respond(400, {'error': 'invalid_binding_query'})
            except (TimeoutError, socket.timeout):
                self.close_connection = True
                self.respond(408, {'error': 'query_timeout'})
            finally:
                if acquired:
                    uploads.release()

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
            if url.path == '/matches/byBinding' and public_manifests:
                self.receive_binding_query(url)
                return
            if url.path == "/feedback":
                self.receive_feedback()
                return
            content_query = url.path == '/matches/byContent' and public_manifests
            if url.path != "/verify" and not content_query:
                self.respond(404, {"error": "not_found"})
                return
            query = parse_qs(url.query)
            requested_algorithm = None
            if content_query:
                from ariadne_mark.softbinding import ALGORITHMS
                requested_algorithm = query.get('alg', [None])[0]
                maximum = query.get('maxResults', ['10'])[0]
                if (set(query) - {'alg','maxResults','format'} or any(len(v) != 1 for v in query.values())
                        or requested_algorithm is not None and requested_algorithm not in ALGORITHMS.values()
                        or len(maximum) > 3 or not maximum.isdecimal() or not 1 <= int(maximum) <= 100):
                    self.respond(400, {'error': 'invalid_content_query'})
                    return
            content_extension = {'image/png': 'png', 'image/jpeg': 'jpg', 'video/mp4': 'mp4'}.get(self.headers.get('Content-Type', '').split(';')[0], '')
            ext = query.get("format", [content_extension if content_query else ""])[0]
            if ext not in {"png", "jpg", "jpeg", "mp4"}:
                self.respond(415, {"error": "unsupported_format"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if content_query and requested_algorithm is not None:
                from ariadne_mark.verification.scope import media_scope
                from ariadne_mark.softbinding import ALGORITHMS
                applicable = media_scope(getattr(sdk, 'verification_scope', 'all'), video=ext == 'mp4')
                if requested_algorithm not in {ALGORITHMS[s] for s in applicable}:
                    self.close_connection = True
                    self.respond(422, {'error': 'algorithm_outside_operator_scope', 'status': 'not_checked',
                                       'declared_schemes': list(applicable)})
                    return
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
                    digest = hashlib.sha256()
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
                            digest.update(chunk)
                            remaining -= len(chunk)
                    # Slow senders consume a bounded upload slot, never the
                    # model's only inference slot.
                    inference_acquired = gate.acquire(blocking=False)
                    if not inference_acquired:
                        self.respond(429, {"error": "verifier_busy"})
                        return
                    report = sdk.verify(path)
                # Temporary files are deleted before the response is returned.
                if content_query:
                    from ariadne_mark.softbinding import observed_algorithms
                    watermark = report.get('watermark', {})
                    if watermark.get('status') not in {'recovered_claim', 'not_found', 'multiple_ids'}:
                        self.respond(503, {'error': 'incomplete_content_search', 'status': 'not_checked'})
                        return
                    registry = getattr(sdk, 'registry', None)
                    # One candidate per confirmed ID; each match must come from a
                    # scheme that actually read that ID. Unconfirmed reads are skipped.
                    if watermark.get('status') == 'multiple_ids':
                        tokens = [e['token'] for e in watermark.get('ids', []) if e.get('status') == 'confirmed']
                    else:
                        tokens = [watermark['token']] if watermark.get('token') else []
                    from ariadne_mark.verification.media import MAX_IDS
                    matches = []
                    for token in tokens[:MAX_IDS]:
                        bundle = registry.get_manifest(token=token, public_only=True) if registry else None
                        if (bundle and bundle['algorithm'] in observed_algorithms(watermark, token, video=path.suffix.lower() == ".mp4")
                                and (requested_algorithm is None or bundle['algorithm'] == requested_algorithm)):
                            matches.append({'manifestId': bundle['id']})
                            if len(matches) >= int(maximum):
                                break
                    if requested_algorithm is not None and not matches:
                        from ariadne_mark.softbinding import ALGORITHMS
                        checked = {ALGORITHMS[s] for s in watermark.get('completed_schemes', []) if s in ALGORITHMS}
                        if requested_algorithm not in checked:
                            self.respond(503, {'error': 'incomplete_content_search', 'status': 'not_checked'})
                            return
                    self.respond(200, {'matches': matches})
                    return
                result = public_report(report, sources)
                if report_signer is not None:
                    media_type = "video/mp4" if ext == "mp4" else "image/png" if ext == "png" else "image/jpeg"
                    result['signed_report'] = report_signer.sign(result, sha256=digest.hexdigest(),
                        size_bytes=length, media_type=media_type)
                self.respond(200, result)
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

    check_runtime = getattr(sdk, "check_runtime", None)
    if check_runtime is not None:
        check_runtime()
    server = Server((host, port), Handler)
    server.configuration_warnings = ([] if sources else [
        'No reviewed public sources configured: provider/system provenance fields are withheld. '
        'Configure --public-sources and issuer trust before relying on public provenance disclosure.'])
    from ariadne_mark.verification.scope import runtime_warnings
    server.configuration_warnings.extend(w['message'] for w in runtime_warnings(getattr(sdk, 'verification_scope', 'all')))
    return server


def serve(sdk, **kwargs):
    server = make_server(sdk, **kwargs)
    import sys
    for warning in server.configuration_warnings:
        print('Verifier configuration: ' + warning, file=sys.stderr, flush=True)
    print(f"Verifier listening on http://{server.server_address[0]}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        close = getattr(sdk, 'close', None)
        if close:
            close()
