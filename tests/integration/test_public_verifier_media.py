"""Real files through the HTTP verifier, public projection and read-only resolver."""
import http.client
import json
import os
import threading
import unittest
from dataclasses import replace

from . import test_media as fixtures


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS') == '1', 'requires real media bundle')
class PublicVerifierMediaTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.MediaTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MediaTests.tearDownClass.__func__)
    video = fixtures.MediaTests.video
    image = fixtures.MediaTests.image
    ffmpeg = fixtures.MediaTests.ffmpeg
    record = fixtures.MediaTests.record

    def setUp(self):
        import tempfile
        from pathlib import Path
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        from ariadne_mark.server import make_server
        self.tmp = tempfile.TemporaryDirectory(dir=self.root)
        self.path = Path(self.tmp.name)
        registry = Registry(self.path / 'registry.sqlite')
        self.sdk = SDK(self.marker, self.identity, registry)
        from ariadne_mark.isolated_verifier import IsolatedVerifier
        self.reader = IsolatedVerifier(registry=registry.path, trust_anchors=self.root / 'identity/trust.pem')
        sources = self.path / 'sources.json'
        record = self.record().to_dict()
        sources.write_text(json.dumps({'schema_version': 1, 'sources': [{'publisher': record['publisher'], 'system': record['system']}]}))
        self.server = make_server(self.reader, port=0, max_upload_mb=5,
                                  public_sources=sources, feedback_db=self.path / 'feedback.sqlite')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.reader.close(); self.sdk.close(); self.tmp.cleanup()

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=180)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally: connection.close()

    def test_video_upload_metadata_loss_and_operator_resolver(self):
        output = self.path / 'marked.mp4'
        receipt = self.sdk.mark(self.video(audio=False), output, self.record('video'))
        status, report = self.request('POST', '/verify?format=mp4', output.read_bytes())
        self.assertEqual(status, 200)
        self.assertEqual(report['watermark']['token'], receipt['token'])
        self.assertEqual(report['c2pa']['record']['publisher'], 'Test Publisher')
        self.assertTrue(report['c2pa']['development_identity'])
        stripped = self.path / 'stripped.mp4'
        self.ffmpeg('-i', output, '-map_metadata', '-1', '-an', '-c:v', 'libx264', '-crf', '28', stripped)
        status, report = self.request('POST', '/verify?format=mp4', stripped.read_bytes())
        self.assertEqual(status, 200)
        self.assertEqual(report['c2pa']['status'], 'not_found')
        self.assertEqual(report['watermark']['token'], receipt['token'])
        self.assertEqual(report['recovery']['record']['publisher'], 'Test Publisher')
        self.assertEqual(report['recovery']['content_binding'], 'not_verified')
        status, entry = self.request('GET', '/records/' + receipt['token'])
        self.assertEqual(status, 200)
        self.assertEqual(entry['record']['asset_id'], receipt['asset_id'])
        self.assertIn('not_authentication', entry['binding'])
        self.assertIsNone(self.reader.identity)

    def test_real_signed_private_name_is_not_reflected_by_public_api(self):
        output = self.path / 'private-name.png'
        record = replace(self.record(), publisher='alice@example.org')
        receipt = self.sdk.mark(self.image(), output, record)
        status, report = self.request('POST', '/verify?format=png', output.read_bytes())
        self.assertEqual(status, 200)
        self.assertEqual(report['watermark']['token'], receipt['token'])
        self.assertNotIn('alice@example.org', json.dumps(report))
        self.assertTrue(report['public_output']['redacted_fields'])

    def test_clean_image_no_human_origin_claim_and_feedback_works(self):
        status, report = self.request('POST', '/verify?format=png', self.image().read_bytes())
        self.assertEqual(status, 200)
        self.assertEqual(report['watermark']['status'], 'not_found')
        self.assertNotIn('human-created', report['label'].lower())
        status, response = self.request('POST', '/feedback', json.dumps({'rating': 'unable_to_check', 'media': 'image'}))
        self.assertEqual(status, 202)
        self.assertEqual(response['storage'], 'aggregate_counters_only')
