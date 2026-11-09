"""Deployment readiness, publication consent and batch fail-before-publish."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from ariadne_mark import kit


class KitPathTests(unittest.TestCase):
    def test_relative_paths_cannot_read_signing_keys_or_escape_through_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); inputs = root / 'inputs'; inputs.mkdir()
            key = root / 'private.key'; key.write_text('not a key')
            (inputs / 'escape').symlink_to(root, target_is_directory=True)
            for name in ['../private.key', str(key), 'escape/private.key', '.', '']:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    kit._inside(inputs, name)


@unittest.skipUnless(importlib.util.find_spec('cryptography'), 'requires reports extra')
class KitTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / 'bundle'
        kit.initialize(self.root, publisher='Fixture Studio', system='Fixture Generator',
                       system_version='1', development=True)

    def write(self, relative, data):
        (self.root / relative).write_text(json.dumps(data))

    def test_initialized_dev_bundle_is_ready_without_claiming_scope_or_compliance(self):
        info = kit.check(self.root)
        self.assertEqual(info['status'], 'ready_for_development')
        self.assertEqual(info['default_video_profile'], 'economy_5s')
        self.assertEqual(info['legal_determination'], 'not_performed')
        self.assertEqual(info['public_reachability'], 'not_checked')
        self.assertEqual(info['profile']['assessment_status'], 'action_required')
        before = (self.root / 'private/provider/private.key').read_bytes()
        with self.assertRaises(FileExistsError):
            kit.initialize(self.root, publisher='Other', system='Other', system_version='1', development=True)
        self.assertEqual(before, (self.root / 'private/provider/private.key').read_bytes())

    def test_public_fields_and_signing_report_keys_cannot_drift_silently(self):
        source = json.loads((self.root / 'config/public-sources.json').read_text())
        source['sources'][0]['publisher'] = 'Different Publisher'
        self.write('config/public-sources.json', source)
        self.assertEqual(kit.check(self.root)['status'], 'configuration_required')
        source['sources'][0]['publisher'] = 'Fixture Studio'; self.write('config/public-sources.json', source)
        (self.root / 'config/report.pub').write_text('different key')
        self.assertIn('Pinned report public key differs', ' '.join(kit.check(self.root)['errors']))

    def test_readable_private_key_blocks_readiness(self):
        (self.root / 'private/provider/private.key').chmod(0o644)
        self.assertTrue(any('group/world-readable' in e for e in kit.check(self.root)['errors']))

    def test_production_initialization_never_creates_fake_credentials(self):
        root = Path(self.folder.name) / 'production'
        kit.initialize(root, publisher='Fixture Studio', system='Fixture Generator', system_version='1',
                       verifier_url='https://verify.integration-company.org')
        self.assertFalse((root / 'private/provider/private.key').exists())
        self.assertFalse((root / 'private/tls/key.pem').exists())
        result = kit.check(root)
        self.assertEqual(result['status'], 'configuration_required')
        self.assertTrue(any('TSA' in e for e in result['errors']))
        self.assertIn('return 308 https://verify.integration-company.org$request_uri;', (root / 'nginx.conf').read_text())
        for value in ['https://localhost', 'https://verify.example.org', 'http://real-company.org', 'https://user:secret@real-company.org']:
            with self.subTest(url=value), self.assertRaises(ValueError):
                kit._url(value)

    def test_incomplete_production_url_never_renders_cleartext_proxy(self):
        root = Path(self.folder.name) / 'unconfigured'
        kit.initialize(root, publisher='Fixture Studio', system='Fixture Generator', system_version='1')
        self.assertIn('return 503;', (root / 'nginx.conf').read_text())
        self.assertEqual(kit.check(root)['status'], 'configuration_required')

    def test_batch_preflight_refuses_bad_second_job_before_any_export(self):
        (self.root / 'inputs/image.png').write_bytes(b'not processed in this preflight')
        good = {'source': 'image.png', 'destination': 'marked.png', 'created_at': '2026-11-09T00:00:00Z'}
        for change in [dict(source='../private/provider/private.key'), dict(created_at=None),
                       dict(video_profile='compliance'), dict(audio_kind='synthetic'), dict(publish_manifest=True)]:
            with self.subTest(change=change):
                bad = {**good, 'destination': 'second.png', **change}
                self.write('batch.json', {'schema_version': 1, 'jobs': [good, bad]})
                with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                    kit.export_batch(self.root, self.root / 'batch.json')
                self.assertEqual(list((self.root / 'outputs').iterdir()), [])

    def test_explicit_render_tracks_body_limit_and_timeout(self):
        config = json.loads((self.root / 'config/kit.json').read_text())
        config.update(max_upload_mb=10, verification_timeout=240)
        self.write('config/kit.json', config)
        kit.render(self.root)
        self.assertIn('client_max_body_size 10m;', (self.root / 'nginx.conf').read_text())
        self.assertIn('proxy_read_timeout 250s;', (self.root / 'nginx.conf').read_text())
