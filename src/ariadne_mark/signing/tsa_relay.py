"""Authenticated RFC 3161 timestamping for the pinned C2PA pair.

c2pa-python 0.38.x / native 0.91.11 sends the timestamp request itself and
accepts only a TSA URL: no request headers. TSAs such as SSL.com's C2PA TSA
require ``Authorization: Bearer <token>``. As SSL.com's own provenance SDK does
for the same c2pa-python family, native c2pa is pointed at a short-lived
loopback relay that adds the credential and forwards the unchanged RFC 3161
request to the real TSA over verified HTTPS.

The relay never changes timestamp semantics: the TSA signs the token and the
native validator still checks it against the signed data and, at
verification, against the configured TSA roots. It only carries the
credential, applies a timeout and bounds sizes. The credential is read from a
private file and is never placed in a URL, receipt, log or exception message.
"""
import os
import secrets
import ssl
import stat
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

QUERY_TYPE = 'application/timestamp-query'
REPLY_TYPE = 'application/timestamp-reply'
MAX_REQUEST = 64 * 1024
MAX_RESPONSE = 1024 * 1024


def read_credential(path):
    """Bearer token from a regular, owner-only file; never echoed."""
    path = Path(path)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('TSA credential must be a regular file, not a link or directory')
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('TSA credential file must not be group/world-readable (chmod 600)')
    token = path.read_text(encoding='ascii').strip()
    if not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('TSA credential file must contain one printable token')
    return token


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # a redirected TSA request is refused, never re-sent elsewhere


class TimestampRelay:
    """Loopback relay for one signing operation (context manager).

    Binds an ephemeral port on 127.0.0.1 and accepts only POSTs to a random
    path, so another local process cannot use it without that secret path.
    """

    def __init__(self, upstream, credential_file, *, timeout=10.0, ca_bundle=None):
        from urllib.parse import urlsplit
        url = urlsplit(upstream)
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in {'127.0.0.1', '::1', 'localhost'}):
            raise ValueError('An authenticated TSA requires an HTTPS endpoint')
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError('TSA timeout must be between 0 and 60 seconds')
        self._upstream = upstream
        self._authorization = 'Bearer ' + read_credential(credential_file)
        self._timeout = float(timeout)
        tls = ssl.create_default_context(cafile=str(ca_bundle) if ca_bundle else None)
        self._opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls), _NoRedirect)
        self._path = '/' + secrets.token_urlsafe(24)
        self._server = None
        self.calls = []

    def __repr__(self):
        return '<TimestampRelay (credential redacted)>'

    @property
    def url(self):
        return f'http://127.0.0.1:{self._server.server_port}{self._path}'

    def _forward(self, body):
        request = urllib.request.Request(self._upstream, data=body, method='POST',
                                         headers={'Content-Type': QUERY_TYPE, 'Authorization': self._authorization})
        start = time.monotonic()
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                data = response.read(MAX_RESPONSE + 1)
                status = response.status
                kind = response.headers.get('Content-Type', '').split(';')[0].strip()
            if len(data) > MAX_RESPONSE:
                status, data = 502, b''
            elif status == 200 and kind != REPLY_TYPE:
                status, data = 502, b''
        except urllib.error.HTTPError as error:
            status, data = error.code, b''
        except Exception as error:  # TLS, DNS, refused, timeout: no detail crosses back
            status, data = (504 if 'timed out' in str(error).lower() else 502), b''
        self.calls.append({'upstream_status': status, 'ms': round((time.monotonic() - start) * 1000, 1)})
        return status, data

    def __enter__(self):
        relay = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = self.headers.get('Content-Length', '')
                if self.path != relay._path:
                    self.send_error(404); return
                if (not length.isdigit() or not 0 < int(length) <= MAX_REQUEST
                        or self.headers.get('Content-Type', '').split(';')[0].strip() != QUERY_TYPE):
                    self.send_error(400); return
                status, data = relay._forward(self.rfile.read(int(length)))
                if status != 200:
                    self.send_error(502 if status >= 500 or status < 400 else status); return
                self.send_response(200)
                self.send_header('Content-Type', REPLY_TYPE)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.send_error(405)

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, name='ariadne-tsa-relay', daemon=True).start()
        return self

    def __exit__(self, *exc):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
