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
import http.client
import secrets
import socket
import ssl
import stat
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

QUERY_TYPE = 'application/timestamp-query'
REPLY_TYPE = 'application/timestamp-reply'
MAX_REQUEST = 64 * 1024
MAX_RESPONSE = 1024 * 1024


def read_credential(path):
    """Bearer token from a regular, owner-only file; never echoed."""
    path = Path(path)
    # Inspect the opened descriptor, not a path checked before opening. Refuse
    # links/FIFOs and bound the read even if a file changes concurrently.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('TSA credential must be a regular file, not a link or directory')
            if stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError('TSA credential file must not be group/world-readable (chmod 600)')
            raw = stream.read(4098)
        if len(raw) > 4097:
            raise ValueError('TSA credential file is too large')
        token = raw.decode('ascii').strip()
    except (OSError, UnicodeError):
        raise ValueError('Cannot read a regular owner-only ASCII TSA credential file') from None
    if not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('TSA credential file must contain one printable token')
    return token


class TimestampRelay:
    """Loopback relay for one signing operation (context manager).

    Binds an ephemeral port on 127.0.0.1 and accepts only POSTs to a random
    path. This is a local capability, not isolation from a privileged process
    on the same host. It exists only for the signing operation.
    """

    def __init__(self, upstream, credential_file, *, timeout=10.0, ca_bundle=None, development=False):
        from urllib.parse import urlsplit
        from ariadne_mark.signing import validate_timestamp_url
        validate_timestamp_url(upstream, allow_loopback_http=development)
        url = self._upstream = urlsplit(upstream)
        # Native has a 30s direct-request timeout. Leave room for the local
        # relay response and shutdown so a configured deadline is effective.
        if type(timeout) not in (int, float) or not 0 < timeout <= 25:
            raise ValueError('Authenticated TSA timeout must be between 0 and 25 seconds')
        self._authorization = 'Bearer ' + read_credential(credential_file)
        self._timeout = float(timeout)
        self._tls = ssl.create_default_context(cafile=str(ca_bundle) if ca_bundle else None)
        self._path = '/' + secrets.token_urlsafe(24)
        self._server = None
        self.calls = []

    def __repr__(self):
        return '<TimestampRelay (credential redacted)>'

    @property
    def url(self):
        return f'http://127.0.0.1:{self._server.server_port}{self._path}'

    def _forward(self, body):
        url = self._upstream
        connection = (http.client.HTTPSConnection(url.hostname, url.port, timeout=self._timeout, context=self._tls)
                      if url.scheme == 'https' else http.client.HTTPConnection(url.hostname, url.port, timeout=self._timeout))
        expired = threading.Event()
        transport = [None]
        def stop():
            expired.set()
            # Interrupt even a drip-fed response; socket read timeouts alone
            # restart on each byte and do not bound total request time.
            sock = transport[0] or connection.sock
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        deadline = threading.Timer(self._timeout, stop)
        deadline.daemon = True
        start = time.monotonic()
        deadline.start()
        try:
            connection.request('POST', url.path or '/', body=body,
                               headers={'Content-Type': QUERY_TYPE, 'Authorization': self._authorization})
            transport[0] = connection.sock
            response = connection.getresponse()
            status = response.status
            # No proxy lookup, redirect, retry or forwarding to another host.
            if status != 200:
                status, data = (status if 400 <= status < 500 else 502), b''
            elif response.headers.get_content_type() != REPLY_TYPE:
                status, data = 502, b''
            else:
                data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                status, data = 502, b''
        except Exception:  # TLS, DNS, refused, timeout: no detail crosses back
            status, data = 502, b''
        finally:
            deadline.cancel()
            connection.close()
        if expired.is_set() or time.monotonic() - start >= self._timeout:
            status, data = 504, b''
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
                body = self.rfile.read(int(length))
                if len(body) != int(length):
                    self.send_error(400); return
                status, data = relay._forward(body)
                if status != 200:
                    self.send_error(status); return
                self.send_response(200)
                self.send_header('Content-Type', REPLY_TYPE)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.send_error(405)

        class Server(HTTPServer):
            def get_request(self):
                sock, address = super().get_request()
                sock.settimeout(2.0)  # local header/body read cannot hold the operation open
                return sock, address

        self._server = Server(('127.0.0.1', 0), Handler)
        self._thread = threading.Thread(target=lambda: self._server.serve_forever(poll_interval=.05),
                                        name='ariadne-tsa-relay', daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=3)
            self._server = None
        self._authorization = None
