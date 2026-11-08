"""Compatibility preflight: actual handle/version/hash and operational verdicts."""
import copy
from collections import namedtuple
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ariadne_mark import c2pa_runtime as runtime
from ariadne_mark.errors import C2paRuntimeMismatch


def _identity(path):
    stat=path.stat();return stat.st_dev,stat.st_ino


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.library=self.path/'loaded.so';self.library.write_bytes(b'qualified native fixture')
        self.pins=copy.deepcopy(runtime.PINS)
        self.pins['native']['library_sha256']=hashlib.sha256(self.library.read_bytes()).hexdigest()
        self.module=SimpleNamespace(__version__=self.pins['python_version'],sdk_version=lambda:self.pins['native_version'])
        self.binding=SimpleNamespace(_lib=SimpleNamespace(_name=str(self.library),_handle=42))
        real_load=runtime.importlib.import_module
        def load(name):
            if name=='c2pa':return self.module
            if name=='c2pa.c2pa':return self.binding
            return real_load(name)
        self.stack=ExitStack()
        for context in [patch.object(runtime,'_mapped_identity',side_effect=lambda lib:_identity(self.library)),patch.object(runtime,'PINS',self.pins),patch.object(runtime,'_cache',{}),
                patch.object(runtime.platform,'system',return_value='Linux'),
                patch.object(runtime.platform,'machine',return_value='x86_64'),
                patch.object(runtime.sys,'version_info',namedtuple('VersionInfo','major minor micro releaselevel serial')(3,12,13,'final',0)),
                patch.object(runtime,'version',return_value=self.pins['python_version']),
                patch.object(runtime.importlib,'import_module',side_effect=load)]:self.stack.enter_context(context)

    def tearDown(self):self.stack.close();self.temp.cleanup()

    def test_actual_handle_path_not_assumed_package_file_and_cache(self):
        self.module.__file__=str(self.path/'unrelated-package/__init__.py')
        with patch.object(runtime,'_digest',wraps=runtime._digest) as digest:
            one=runtime.require_runtime();two=runtime.require_runtime()
            self.assertEqual(one['status'],'qualified');self.assertEqual(digest.call_count,1)
            one['expected']['native_version']='tampered report'
            self.assertEqual(runtime.require_runtime()['expected']['native_version'],self.pins['native_version'])
            with patch.object(runtime.os,'getpid',return_value=99999):runtime.require_runtime()
            self.assertEqual(digest.call_count,2)
        self.assertNotIn(str(self.path),json.dumps(two))

    def test_same_python_wrapper_different_native_version_is_rejected(self):
        self.module.sdk_version=lambda:'0.91.6'
        with self.assertRaises(C2paRuntimeMismatch) as error:runtime.require_runtime()
        self.assertEqual(error.exception.report['reason'],'native_version_mismatch')
        self.assertIn('0.91.6',str(error.exception))
        self.assertIn('bootstrap_c2pa',str(error.exception))

    def test_same_version_changed_binary_invalidates_the_cached_qualification(self):
        runtime.require_runtime()
        self.library.write_bytes(b'different native bytes, same version')
        self.assertEqual(runtime.runtime_info()['reason'],'native_hash_mismatch')
        with self.assertRaises(C2paRuntimeMismatch):runtime.require_runtime()

    def test_wrong_wrapper_and_uninspectable_handle(self):
        self.module.__version__='0.38.2'
        self.assertEqual(runtime.runtime_info()['reason'],'python_package_mismatch')
        self.module.__version__=self.pins['python_version']
        self.binding._lib._name='libc2pa_c.so'
        self.assertEqual(runtime.runtime_info()['reason'],'native_path_unverifiable')

    def test_unsupported_platform_does_not_load_native_code(self):
        with patch.object(runtime.platform,'system',return_value='Darwin'),patch.object(runtime.importlib,'import_module') as load:
            self.assertEqual(runtime.runtime_info()['reason'],'unsupported_platform');load.assert_not_called()

    def test_missing_dependency_keeps_core_lazy_but_explicit_preflight_fails(self):
        with patch.object(runtime.importlib.util,'find_spec',return_value=None):
            self.assertIsNone(runtime.check_if_installed())
        with patch.object(runtime.importlib,'import_module',side_effect=ModuleNotFoundError):
            self.assertEqual(runtime.runtime_info()['reason'],'dependency_missing')
            with self.assertRaises(C2paRuntimeMismatch):runtime.require_runtime()

    def test_context_does_not_construct_native_reader_settings_when_mismatched(self):
        from ariadne_mark.signing import context
        self.module.Context=SimpleNamespace(from_dict=Mock())
        self.module.sdk_version=lambda:'0.91.6'
        with self.assertRaises(C2paRuntimeMismatch):context()
        self.module.Context.from_dict.assert_not_called()

    def test_inspection_failure_is_not_absence_or_forgery_and_public_output_is_scoped(self):
        from ariadne_mark.verification.media import inspect_c2pa,_verification_result
        from ariadne_mark.public_verifier import public_report
        self.module.sdk_version=lambda:'0.91.6'
        with patch('ariadne_mark.verification.media.read_manifest',side_effect=C2paRuntimeMismatch(runtime.runtime_info())):
            result=inspect_c2pa(Path('fixture.png'))
        self.assertEqual((result['status'],result['signature']),('not_checked','not_checked'))
        self.assertEqual(result['reason'],'c2pa_runtime_unqualified')
        report=_verification_result(Path('fixture.png'),result,{'status':'not_found'},registry=None,video=False)
        self.assertIn('Signature check unavailable',report['label'])
        self.assertNotIn('runtime',public_report(report)['c2pa'])

    def test_cli_diagnostic_has_failure_exit_and_machine_readable_reason(self):
        from ariadne_mark.cli import main
        self.module.sdk_version=lambda:'0.91.6'
        with redirect_stdout(io.StringIO()) as output:code=main(['runtime','check'])
        self.assertEqual(code,2)
        self.assertEqual(json.loads(output.getvalue())['reason'],'native_version_mismatch')

    def test_server_preflight_runs_before_socket_binding(self):
        from ariadne_mark.server import make_server
        class Unqualified:
            def check_runtime(this):raise C2paRuntimeMismatch(runtime.runtime_info())
        self.module.sdk_version=lambda:'0.91.6'
        with patch('http.server.HTTPServer.server_bind') as bind:
            with self.assertRaises(C2paRuntimeMismatch):make_server(Unqualified(),port=0)
            bind.assert_not_called()

    def test_replaced_path_is_not_the_file_backing_the_loaded_function(self):
        with patch.object(runtime,'_mapped_identity',return_value=(0,0)):
            self.assertEqual(runtime.runtime_info()['reason'],'native_file_identity_mismatch')
