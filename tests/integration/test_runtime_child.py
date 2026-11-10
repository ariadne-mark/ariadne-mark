"""A lazy core constructor cannot accidentally bypass child startup preflight."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires qualified native media runtime')
class RuntimeChildTests(unittest.TestCase):
    def test_real_child_rejects_same_version_changed_binary_before_http_bind(self):
        import c2pa.c2pa
        from ariadne_mark.errors import C2paRuntimeMismatch
        from ariadne_mark.isolated_verifier import IsolatedVerifier
        from ariadne_mark.server import make_server
        with tempfile.TemporaryDirectory() as folder:
            library=Path(folder)/'changed.so'
            shutil.copyfile(c2pa.c2pa._lib._name,library)
            with library.open('ab') as stream:stream.write(b'changed qualification fixture')
            code="import os;os.environ['C2PA_LIBRARY_NAME']="+repr(str(library))+";from ariadne_mark.verifier_worker import main;main()"
            with IsolatedVerifier(timeout=20,_command=[sys.executable,'-c',code]) as verifier:
                with self.assertRaises(C2paRuntimeMismatch) as error:make_server(verifier,port=0)
                # Hardened CI has noexec /tmp: dlopen is denied before hashing.
                # Both are typed unqualified-runtime failures before HTTP bind;
                # an executable-temp probe separately exercises hash rejection.
                self.assertIn(error.exception.report['reason'],{'native_hash_mismatch','native_inspection_failed'})
                self.assertIsNone(verifier._process)

    def test_real_default_child_preflight_does_not_leave_a_probe_process(self):
        from ariadne_mark.isolated_verifier import IsolatedVerifier
        from ariadne_mark.server import make_server
        with IsolatedVerifier(timeout=20) as verifier:
            server=make_server(verifier,port=0)
            server.server_close()
            self.assertIsNone(verifier._process)
