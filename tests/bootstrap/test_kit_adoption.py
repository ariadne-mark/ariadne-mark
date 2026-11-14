"""ADOPTION-OPT-01 kit contracts: image pinning, version guard, bind defaults, reserved origins."""
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from ariadne_mark import kit


class ReservedOriginTests(unittest.TestCase):
    def test_all_rfc2606_and_6761_names_are_rejected_for_production(self):
        # ISS-16: example.net slipped through the previous suffix list.
        for host in ['example.net', 'verify.example.net', 'example.com', 'a.example.org', 'studio.example',
                     'kit.test', 'x.invalid', 'app.localhost', 'EXAMPLE.NET.']:
            with self.subTest(host=host):
                self.assertTrue(kit.reserved_host(host))
                with self.assertRaisesRegex(ValueError, 'placeholder'):
                    kit._url(f'https://{host.rstrip(".")}')

    def test_real_names_containing_reserved_words_are_accepted(self):
        for host in ['myexample.net', 'example.network', 'testing.io', 'invalidation.org', 'contest.dev']:
            with self.subTest(host=host):
                self.assertFalse(kit.reserved_host(host))
                self.assertEqual(kit._url(f'https://{host}'), f'https://{host}')

    def test_development_kits_may_use_localhost(self):
        self.assertEqual(kit._url('https://localhost:8443', development=True), 'https://localhost:8443')


class RuntimeGuardTests(unittest.TestCase):
    def test_mismatched_image_is_refused_before_kit_work(self):
        with patch.dict(os.environ, {kit.EXPECTED_SDK_ENV: '0.0.0a0'}):
            with self.assertRaisesRegex(ValueError, 'pin-image.sh'):
                kit.require_expected_runtime()
            with self.assertRaisesRegex(ValueError, 'expects SDK 0.0.0a0'):
                kit.export_batch('/nonexistent', '/nonexistent/batch.json')
            with self.assertRaisesRegex(ValueError, 'expects SDK 0.0.0a0'):
                kit.serve('/nonexistent')

    def test_matching_or_unpinned_legacy_kit_is_allowed(self):
        from ariadne_mark.version import sdk_version
        with patch.dict(os.environ, {kit.EXPECTED_SDK_ENV: sdk_version()}):
            kit.require_expected_runtime()
        with patch.dict(os.environ, {kit.EXPECTED_SDK_ENV: ''}):
            kit.require_expected_runtime()


class BindTests(unittest.TestCase):
    def test_host_default_is_loopback_and_container_default_is_all_interfaces(self):
        with patch.object(Path, 'exists', autospec=True, return_value=False):
            self.assertEqual(kit.default_bind_host(), '127.0.0.1')
        with patch.object(Path, 'exists', autospec=True, side_effect=lambda self: str(self) == '/.dockerenv'):
            self.assertEqual(kit.default_bind_host(), '0.0.0.0')

    def test_invalid_port_is_rejected(self):
        with patch.dict(os.environ, {kit.EXPECTED_SDK_ENV: ''}):
            for port in [0, 70000, '8080']:
                with self.subTest(port=port), self.assertRaisesRegex(ValueError, 'Port'):
                    kit.serve('/nonexistent', host='127.0.0.1', port=port)

    def test_compose_passes_explicit_container_bind_and_expected_version(self):
        from importlib.resources import files
        compose = files('ariadne_mark').joinpath('kit_assets', 'compose.yaml').read_text()
        self.assertIn('"--host", "0.0.0.0", "--port", "8080"', compose)
        self.assertIn('ARIADNE_KIT_EXPECTED_SDK: ${KIT_SDK_VERSION:-}', compose)
        self.assertIn('./pin-image.sh', compose)


@unittest.skipUnless(importlib.util.find_spec('cryptography'), 'requires reports extra')
class InitPinTests(unittest.TestCase):
    def test_new_kit_requires_an_image_pin_and_ships_the_pin_script(self):
        from ariadne_mark.version import sdk_version
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'bundle'
            kit.initialize(root, publisher='Fixture Studio', system='Fixture Generator', system_version='1',
                           development=True)
            env = dict(l.split('=', 1) for l in (root / '.env').read_text().splitlines() if '=' in l)
            self.assertEqual(env['KIT_SDK_IMAGE'], '')  # never a mutable tag
            self.assertEqual(env['KIT_SDK_VERSION'], sdk_version())
            script = root / 'pin-image.sh'
            self.assertTrue(stat.S_IMODE(script.stat().st_mode) & 0o100)
            self.assertIn('docker image inspect', script.read_text())
            codes = [w['code'] for w in kit.check(root)['warnings']]
            self.assertIn('sdk_image_not_pinned', codes)
            (root / '.env').write_text((root / '.env').read_text().replace(
                'KIT_SDK_IMAGE=\n', 'KIT_SDK_IMAGE=sha256:' + 'a' * 64 + '\n'))
            self.assertNotIn('sdk_image_not_pinned', [w['code'] for w in kit.check(root)['warnings']])
