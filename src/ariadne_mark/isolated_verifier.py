"""Persistent verification-only subprocess with a whole-job deadline.

The qualified Linux server kills the worker's process group (including Node)
on timeout/crash. No signing identity, media bytes or expected ID crosses IPC.
"""
import math
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time

from ariadne_mark.errors import AriadneError, VerificationTimeout, C2paRuntimeMismatch
from ariadne_mark.verifier_worker import MAX_MESSAGE, read_message, send_message


class IsolatedVerifier:
    identity = None

    def __init__(self, *, registry=None, trust_anchors=None, threads=2, timeout=180, tsa_trust_anchors=None, verification_scope="all", _command=None):
        if type(threads) is not int or not 1 <= threads <= 64:
            raise ValueError('threads must be1–64')
        if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
            raise ValueError('verification timeout must be finite and between0 and3600seconds')
        from ariadne_mark.registry import Registry
        self.registry = Registry(Path(registry), read_only=True) if registry else None
        self.trust_anchors = Path(trust_anchors) if trust_anchors else None
        self.tsa_trust_anchors = Path(tsa_trust_anchors) if tsa_trust_anchors else None
        self.timeout = timeout
        from ariadne_mark.verification.scope import normalize_scope
        schemes = normalize_scope(verification_scope)
        self._config = {'verification_schemes': list(schemes), 'threads': threads, 'registry': str(Path(registry).resolve()) if registry else None,
                        'trust_anchors': str(self.trust_anchors.resolve()) if self.trust_anchors else None,
                        'tsa_trust_anchors': str(self.tsa_trust_anchors.resolve()) if self.tsa_trust_anchors else None}
        self._builtin_worker = _command is None
        self._command = _command or [sys.executable, '-m', 'ariadne_mark.verifier_worker']
        self._lock = threading.RLock()
        self._process = None
        self._events = None
        self._reader = None
        self._request_id = 0
        self._closed = False
        self._owner = os.getpid()

    def check_runtime(self):
        if os.getpid() != self._owner:
            raise AriadneError('Create a verification service in each process after forking')
        with self._lock:
            if self._closed:
                raise AriadneError('Verification service is closed')
            if self._builtin_worker:
                from ariadne_mark.c2pa_runtime import require_runtime
                require_runtime()
            was_running = self._process is not None
            try:
                self._start(time.monotonic() + self.timeout)
            finally:
                # A preflight probe must not leak a child if later HTTP config
                # or binding fails. Normal requests retain their resident child.
                if not was_running:
                    self._stop()

    def _receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise VerificationTimeout('Verification exceeded its whole-job deadline')
        try:
            value = self._events.get(timeout=remaining)
        except queue.Empty:
            raise VerificationTimeout('Verification exceeded its whole-job deadline') from None
        if isinstance(value, Exception):
            raise AriadneError('Verification worker channel failed') from None
        return value

    def _start(self, deadline):
        if self._process is not None:
            return
        events = queue.Queue()
        process = subprocess.Popen(self._command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, start_new_session=os.name == 'posix')
        self._process, self._events = process, events
        def reader():
            try:
                while True:
                    events.put(read_message(process.stdout, limit=MAX_MESSAGE))
            except Exception as error:
                events.put(error)
        self._reader = threading.Thread(target=reader, daemon=True)
        self._reader.start()
        send_message(process.stdin, self._config)
        ready = self._receive(deadline)
        if ready.get('error') == 'c2pa_runtime_unqualified':
            raise C2paRuntimeMismatch(ready['runtime'])
        if ready != {'ready': True}:
            raise AriadneError('Verification worker did not initialize')

    def verify(self, path):
        if os.getpid() != self._owner:
            raise AriadneError('Create a verification service in each process after forking')
        with self._lock:
            if self._closed:
                raise AriadneError('Verification service is closed')
            deadline = time.monotonic() + self.timeout
            try:
                self._start(deadline)
                self._request_id += 1
                send_message(self._process.stdin, {'id': self._request_id, 'path': str(Path(path).resolve())})
                result = self._receive(deadline)
                if result.get('id') != self._request_id or 'report' not in result:
                    raise AriadneError('Verification worker could not complete the check')
                return result['report']
            except BaseException:
                self._stop()
                raise

    def _stop(self):
        # Keep ownership until the group is killed, then reap; no poll/reap
        # before killpg, so an exited leader's PID is not released for reuse.
        process, self._process = self._process, None
        if process is None:
            return
        try:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        except PermissionError:
            # macOS may report EPERM for an already-exited empty group. Do
            # not suppress a denied signal to a still-live owned worker.
            if process.poll() is None:
                raise
        process.wait(timeout=5)
        if self._reader is not None:
            self._reader.join(timeout=2)
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()

    def close(self):
        if os.getpid() != self._owner:
            return  # Never terminate another process's worker after a fork.
        self._closed = True
        self._stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
