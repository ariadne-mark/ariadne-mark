import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from ariadne_mark.reports import ReportSigner, generate_report_key, verify_report, _b64, _json, TYPE
from ariadne_mark.server import make_server

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    Ed25519PrivateKey = None


@unittest.skipUnless(Ed25519PrivateKey, 'requires cryptography')
class SignedReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.asset = self.path / 'asset.png'
        self.asset.write_bytes(b'original asset')
        self.signer = ReportSigner(Ed25519PrivateKey.generate(), 'https://verifier.example.test')
        self.result = {'label': 'Check incomplete', 'watermark': {'status': 'not_checked'}}

    def tearDown(self):
        self.temp.cleanup()

    def receipt(self):
        data = self.asset.read_bytes()
        return self.signer.sign(self.result, sha256=hashlib.sha256(data).hexdigest(),
                                size_bytes=len(data), media_type='image/png')

    def test_portable_round_trip_and_asset_binding(self):
        payload = verify_report(self.receipt(), self.signer.public_pem(), asset=self.asset,
                                verifier_id=self.signer.verifier_id)
        self.assertEqual(payload['result'], self.result)
        self.assertEqual(payload['verifier']['key_id'], self.signer.key_id)
        self.assertNotIn('PRIVATE KEY', json.dumps(payload))
        self.asset.write_bytes(b'changed asset')
        with self.assertRaisesRegex(ValueError, 'Asset does not match'):
            verify_report(self.receipt_for_original(), self.signer.public_pem(), asset=self.asset)

    def receipt_for_original(self):
        return self.signer.sign(self.result, sha256=hashlib.sha256(b'original asset').hexdigest(),
                                size_bytes=14, media_type='image/png')

    def test_result_tampering_is_rejected(self):
        receipt = self.receipt()
        header, payload, signature = receipt['jws'].split('.')
        payload = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        payload['result']['watermark']['status'] = 'recovered_claim'
        receipt['jws'] = '.'.join([header, _b64(_json(payload)), signature])
        with self.assertRaisesRegex(ValueError, 'signature is invalid'):
            verify_report(receipt, self.signer.public_pem())

    def test_key_or_verifier_substitution_is_rejected(self):
        other = ReportSigner(Ed25519PrivateKey.generate(), 'https://other.example.test')
        with self.assertRaises(ValueError):
            verify_report(self.receipt(), other.public_pem())
        with self.assertRaisesRegex(ValueError, 'Unexpected verifier'):
            verify_report(self.receipt(), self.signer.public_pem(), verifier_id=other.verifier_id)

    def test_algorithm_confusion_and_duplicate_headers_are_rejected(self):
        receipt = self.receipt()
        header, payload, signature = receipt['jws'].split('.')
        for raw in (b'{"alg":"none"}', b'{"alg":"EdDSA","alg":"none"}'):
            with self.subTest(raw=raw):
                bad = {'format': 'JWS-compact', 'jws': '.'.join([_b64(raw), payload, signature])}
                with self.assertRaises(ValueError):
                    verify_report(bad, self.signer.public_pem())

    def test_keygen_is_separate_private_and_never_overwrites(self):
        folder = self.path / 'identity'
        generated = generate_report_key(folder)
        self.assertEqual(os.stat(folder / 'report.key').st_mode & 0o777, 0o600)
        loaded = ReportSigner.from_file(folder / 'report.key', self.signer.verifier_id)
        self.assertEqual(loaded.key_id, generated['key_id'])
        with self.assertRaises(FileExistsError):
            generate_report_key(folder)
        self.assertNotIn('d', loaded.public_jwk())

    def test_api_signs_exact_upload_and_only_public_result_and_cleans_up(self):
        outer = self
        class SDK:
            def verify(self, path):
                outer.upload = path
                return {'label': 'Check incomplete', 'watermark': {'status': 'not_checked'},
                        'private_debug': 'must not be public'}
        server = make_server(SDK(), port=0, report_signer=self.signer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection(*server.server_address, timeout=5)
            conn.request('POST', '/verify?format=png', self.asset.read_bytes())
            response = conn.getresponse()
            data = json.loads(response.read())
            self.assertEqual(response.status, 200)
            payload = verify_report(data, self.signer.public_pem(), asset=self.asset)
            self.assertEqual(payload['result']['watermark']['status'], 'not_checked')
            self.assertNotIn('private_debug', payload['result'])
            self.assertFalse(self.upload.exists())
            conn.request('GET', '/report-key')
            key_response = json.loads(conn.getresponse().read())
            self.assertEqual(key_response['keys'][0], self.signer.public_jwk())
            self.assertNotIn('d', key_response['keys'][0])
            conn.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_signing_failure_never_returns_unsigned_success(self):
        class SDK:
            def verify(self, path): return {'label': 'fixture'}
        with patch.object(self.signer, 'sign', side_effect=ValueError('private key diagnostic')):
            server = make_server(SDK(), port=0, report_signer=self.signer)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                conn = http.client.HTTPConnection(*server.server_address, timeout=5)
                conn.request('POST', '/verify?format=png', b'asset')
                response = conn.getresponse()
                self.assertNotEqual(response.status, 200)
                self.assertNotIn(b'private key', response.read()); conn.close()
            finally:
                server.shutdown(); server.server_close(); thread.join()
