"""A hanging/crashed verification child cannot hold the public service forever."""
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from ariadne_mark.errors import AriadneError, VerificationTimeout
from ariadne_mark.isolated_verifier import IsolatedVerifier
from ariadne_mark.server import make_server

WORKER = '''
import os,sys,time,subprocess
from pathlib import Path
from ariadne_mark.verifier_worker import read_message,send_message
config=read_message(sys.stdin.buffer)
send_message(sys.stdout.buffer,{'ready':True})
while True:
 command=read_message(sys.stdin.buffer)
 path=Path(command['path'])
 if path.name.startswith('upload.'):(Path(__file__).parent/'last-upload.txt').write_text(str(path))
 if path.name=='slow':
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  (path.parent/'descendant.pid').write_text(str(child.pid))
  time.sleep(60)
 elif path.name=='crash':os._exit(8)
 elif path.read_bytes()==b'slow':time.sleep(60)
 send_message(sys.stdout.buffer,{'id':command['id'],'report':{'schema_version':1,'label':'Fixture checked','watermark':{'status':'not_found'}}})
'''


@unittest.skipUnless(os.name == 'posix', 'qualified process-group cleanup is POSIX')
class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        script = self.path / 'worker.py'; script.write_text(WORKER)
        self.verifier = IsolatedVerifier(timeout=1, _command=[sys.executable, str(script)])
        for name in ['good', 'slow', 'crash']:
            (self.path / name).write_bytes(b'fixture')

    def tearDown(self):
        self.verifier.close(); self.tmp.cleanup()

    def test_timeout_kills_descendant_and_next_request_uses_a_fresh_worker(self):
        self.verifier.verify(self.path / 'good')
        initial_pid = self.verifier._process.pid
        started = time.monotonic()
        with self.assertRaises(VerificationTimeout):
            self.verifier.verify(self.path / 'slow')
        self.assertLess(time.monotonic() - started, 5)
        child = int((self.path / 'descendant.pid').read_text())
        stat = Path('/proc') / str(child) / 'stat'
        if Path('/proc/self').exists() and stat.exists():
            self.assertEqual(stat.read_text().split()[2], 'Z')  # dead; init may not have reaped it yet
        self.assertEqual(self.verifier.verify(self.path / 'good')['label'], 'Fixture checked')
        self.assertNotEqual(self.verifier._process.pid, initial_pid)

    def test_crash_is_not_a_negative_and_closed_worker_cannot_restart(self):
        with self.assertRaises(AriadneError): self.verifier.verify(self.path / 'crash')
        self.assertEqual(self.verifier.verify(self.path / 'good')['watermark']['status'], 'not_found')
        self.verifier.close()
        self.assertIsNone(self.verifier._process)
        with self.assertRaises(AriadneError): self.verifier.verify(self.path / 'good')

    def test_repeated_jobs_reuse_worker_without_more_live_fds(self):
        self.verifier.verify(self.path / 'good')
        pid = self.verifier._process.pid
        descriptors = Path('/proc/self/fd')
        before = len(list(descriptors.iterdir())) if descriptors.exists() else None
        for _ in range(20): self.verifier.verify(self.path / 'good')
        self.assertEqual(self.verifier._process.pid, pid)
        if before is not None: self.assertLessEqual(len(list(descriptors.iterdir())), before + 1)

    def test_http_timeout_is_explicit_temp_is_cleaned_and_gate_recovers(self):
        server = make_server(self.verifier, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def request(body):
            connection = http.client.HTTPConnection(*server.server_address, timeout=8)
            try:
                connection.request('POST', '/verify?format=png', body=body)
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally: connection.close()
        try:
            status, result = request(b'slow')
            self.assertEqual(status, 504)
            self.assertEqual(result['status'], 'not_checked')
            self.assertNotIn('not_found', json.dumps(result))
            upload = Path((self.path / 'last-upload.txt').read_text())
            self.assertFalse(upload.exists())
            self.assertFalse(upload.parent.exists())
            self.assertEqual(request(b'good')[0], 200)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_inherited_instance_cannot_use_or_kill_parent_worker(self):
        from unittest.mock import patch
        self.verifier.verify(self.path / 'good')
        process = self.verifier._process
        with patch('ariadne_mark.isolated_verifier.os.getpid', return_value=os.getpid() + 100000):
            with self.assertRaises(AriadneError): self.verifier.verify(self.path / 'good')
            self.verifier.close()
        self.assertIs(self.verifier._process, process)
        self.assertEqual(self.verifier.verify(self.path / 'good')['label'], 'Fixture checked')
