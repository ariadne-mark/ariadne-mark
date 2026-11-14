"""Authenticated relay protocol, secret handling and bounded failure contracts."""
import contextlib
import io
import os
import socket
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ariadne_mark.signing.tsa_relay import TimestampRelay, read_credential, QUERY_TYPE, REPLY_TYPE, MAX_RESPONSE


class CredentialTests(unittest.TestCase):
    def test_private_bounded_regular_file_and_redacted_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'token'
            path.write_text('fixture-private-token\n');path.chmod(0o600)
            self.assertEqual(read_credential(path), 'fixture-private-token')
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'chmod 600'):read_credential(path)
            path.chmod(0o600)
            link=Path(folder)/'link';link.symlink_to(path)
            with self.assertRaises(ValueError):read_credential(link)
            for value in [b'', b'x'*5000, b'fixture\nprivate', b'fixture\xffprivate']:
                path.write_bytes(value)
                with self.assertRaises(ValueError) as caught:read_credential(path)
                self.assertNotIn('fixture', str(caught.exception))
            fifo=Path(folder)/'fifo';os.mkfifo(fifo,0o600)
            with self.assertRaises(ValueError):read_credential(fifo)


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'token'
        self.path.write_text('fixture-private-token');self.path.chmod(0o600)
        self.seen=[];self.mode='ok';owner=self
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                owner.seen.append((self.path,self.headers.get('Authorization'),body))
                if owner.mode=='redirect':
                    self.send_response(307);self.send_header('Location',owner.upstream+'/stolen');self.end_headers();return
                if owner.mode=='401':self.send_error(401);return
                data=b'signed timestamp response' if owner.mode!='large' else b'x'*(MAX_RESPONSE+1)
                self.send_response(200)
                self.send_header('Content-Type','text/plain' if owner.mode=='wrong_type' else REPLY_TYPE)
                self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:
                    if owner.mode=='drip':
                        for b in data:
                            self.wfile.write(bytes([b]));self.wfile.flush();time.sleep(.08)
                    else:self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.upstream=f'http://127.0.0.1:{self.server.server_port}/ecc'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.folder.cleanup()

    def request(self,url,body=b'rfc3161-query',kind=QUERY_TYPE):
        request=urllib.request.Request(url,data=body,headers={'Content-Type':kind})
        try:
            with urllib.request.urlopen(request,timeout=3) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()

    def test_only_configured_upstream_gets_credential_and_exact_query(self):
        captured=io.StringIO()
        with contextlib.redirect_stderr(captured):
            relay=TimestampRelay(self.upstream,self.path,development=True)
            with relay:
                status,body=self.request(relay.url)
                self.assertEqual((status,body),(200,b'signed timestamp response'))
                self.assertEqual(self.request(relay.url+'wrong')[0],404)
                self.assertEqual(self.request(relay.url,kind='image/png')[0],400)
                self.assertEqual(self.request(relay.url,body=b'x'*65537)[0],400)
                self.assertNotIn('fixture-private-token',repr(relay))
                self.assertNotIn('fixture-private-token',str(relay.calls))
            self.assertFalse(relay._thread.is_alive())
            self.assertIsNone(relay._authorization)
        self.assertEqual(self.seen,[('/ecc','Bearer fixture-private-token',b'rfc3161-query')])
        self.assertNotIn('fixture-private-token',captured.getvalue())

    def test_redirects_types_and_sizes_fail_closed(self):
        for mode,expected in [('redirect',502),('wrong_type',502),('large',502),('401',401)]:
            self.mode=mode;self.seen.clear()
            with self.subTest(mode=mode),TimestampRelay(self.upstream,self.path,development=True) as relay:
                self.assertEqual(self.request(relay.url)[0],expected)
                self.assertEqual(len(self.seen),1)  # no redirect or automatic retry

    def test_drip_response_has_total_deadline_and_no_leftover_relay(self):
        self.mode='drip';start=time.monotonic()
        relay=TimestampRelay(self.upstream,self.path,timeout=.25,development=True)
        with relay:self.assertEqual(self.request(relay.url)[0],504)
        self.assertLess(time.monotonic()-start,1.5)
        self.assertFalse(relay._thread.is_alive())

    def test_production_rejects_http_secrets_and_unusable_timeout(self):
        for url in [self.upstream,'https://name:secret@tsa.invalid','https://tsa.invalid?secret=x']:
            with self.assertRaises(ValueError):TimestampRelay(url,self.path)
        for seconds in [0,26,True,float('nan')]:
            with self.assertRaises(ValueError):TimestampRelay(self.upstream,self.path,timeout=seconds,development=True)

    def test_local_header_and_body_drips_do_not_block_real_query(self):
        # Every byte arrives within the inactivity timeout. Only a total
        # deadline prevents indefinite slow-client occupation (review Q-01).
        for phase in ['headers', 'body']:
            with self.subTest(phase=phase), patch('ariadne_mark.signing.tsa_relay.LOCAL_READ_TIMEOUT', .6):
                with TimestampRelay(self.upstream,self.path,development=True) as relay:
                    sock=socket.create_connection(('127.0.0.1',relay._server.server_port),timeout=2)
                    self.addCleanup(sock.close)
                    initial=b'POST /unknown HTTP/1.0\r\nX-Slow: '
                    if phase=='body':
                        initial=(f'POST {relay._path} HTTP/1.0\r\nContent-Type: {QUERY_TYPE}\r\n'
                                 'Content-Length: 100\r\n\r\n').encode()
                    sock.sendall(initial)
                    stopped=threading.Event()
                    def drip():
                        try:
                            while not stopped.wait(.1):sock.sendall(b'x')
                        except OSError:pass
                    sender=threading.Thread(target=drip,daemon=True);sender.start()
                    try:
                        start=time.monotonic()
                        self.assertEqual(self.request(relay.url)[0],200)
                        self.assertLess(time.monotonic()-start,.55)
                        # A slow client must be disconnected despite continued
                        # bytes, and the next legitimate request must still work.
                        self.assertEqual(sock.recv(4096),b'')
                        self.assertLess(time.monotonic()-start,1.5)
                        self.assertEqual(self.request(relay.url)[0],200)
                    finally:
                        stopped.set();sender.join(1);sock.close()

    def test_local_capacity_is_bounded_and_shutdown_reclaims_clients(self):
        from ariadne_mark.signing.tsa_relay import MAX_LOCAL_CLIENTS
        captured=io.StringIO()
        with contextlib.redirect_stderr(captured):
            relay=TimestampRelay(self.upstream,self.path,development=True)
            with relay:
                sockets=[]
                for _ in range(MAX_LOCAL_CLIENTS):
                    sock=socket.create_connection(('127.0.0.1',relay._server.server_port),timeout=2)
                    sockets.append(sock);self.addCleanup(sock.close)
                    sock.sendall(b'POST / HTTP/1.0\r\nX: ')
                end=time.monotonic()+1
                while len(relay._server._clients)<MAX_LOCAL_CLIENTS and time.monotonic()<end:time.sleep(.01)
                self.assertEqual(len(relay._server._clients),MAX_LOCAL_CLIENTS)
                overflow=socket.create_connection(('127.0.0.1',relay._server.server_port),timeout=1)
                try:self.assertEqual(overflow.recv(1),b'')
                finally:overflow.close()
                threads=[s['thread'] for s in relay._server._clients.values()]
                start=time.monotonic()
            self.assertLess(time.monotonic()-start,1.5)
            self.assertTrue(all(not t.is_alive() for t in threads))
            for sock in sockets:sock.close()
        self.assertEqual(captured.getvalue(),'')

    def test_disconnected_client_is_quiet(self):
        captured=io.StringIO()
        with contextlib.redirect_stderr(captured),TimestampRelay(self.upstream,self.path,development=True) as relay:
            entered=threading.Event();release=threading.Event()
            def delayed(body):
                entered.set();release.wait(1)
                return 200,b'response'
            with patch.object(relay,'_forward',side_effect=delayed):
                sock=socket.create_connection(('127.0.0.1',relay._server.server_port),timeout=2)
                sock.sendall((f'POST {relay._path} HTTP/1.0\r\nContent-Type: {QUERY_TYPE}\r\n'
                              'Content-Length: 1\r\n\r\nx').encode())
                self.assertTrue(entered.wait(1))
                sock.shutdown(socket.SHUT_RDWR);sock.close();release.set()
                end=time.monotonic()+1
                while relay._server._clients and time.monotonic()<end:time.sleep(.01)
                self.assertEqual(relay._server._clients,{})
        self.assertNotIn('Traceback',captured.getvalue())
