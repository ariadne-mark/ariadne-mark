"""Production timestamping boundary for the pinned C2PA pair (ADOPTION-OPT-01 item 5)."""
import os
from pathlib import Path
import tempfile
import unittest

from ariadne_mark.errors import AriadneError
from ariadne_mark.signing import SigningIdentity, validate_timestamp_url


class TimestampUrlTests(unittest.TestCase):
    def test_secrets_and_cleartext_never_reach_the_native_tsa_client(self):
        for url in ['http://tsa.example.org/tsr', 'https://user:key@tsa.example.org/tsr',
                    'https://tsa.example.org/tsr?api_key=secret', 'https://tsa.example.org/tsr#x',
                    'https:// tsa.example.org', 'https://', 'ftp://tsa.example.org', 'https://tsa.example.org:99999']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_timestamp_url(url)
            with self.subTest(identity=url), self.assertRaises(ValueError):
                SigningIdentity(Path('c'), Path('k'), False, url)

    def test_https_endpoint_with_path_and_port_is_accepted(self):
        url = 'https://timestamp.operator-tsa.org:8443/rfc3161'
        self.assertEqual(SigningIdentity(Path('c'), Path('k'), False, url).timestamp_url, url)
        self.assertIsNone(SigningIdentity(Path('c'), Path('k'), True).timestamp_url)


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS') == '1', 'requires the qualified C2PA runtime and models')
class TimestampFailureTests(unittest.TestCase):
    def test_unreachable_tsa_publishes_nothing_and_does_not_echo_the_endpoint(self):
        from PIL import Image
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        from ariadne_mark.signing import create_development_identity
        from ariadne_mark.watermark import Watermarker
        from tests.provenance.test_records import example_record
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            create_development_identity(root / 'id')
            # Port 9 (discard) on loopback refuses connections: a failed TSA call.
            identity = SigningIdentity.from_directory(root / 'id', allow_dev=True,
                                                      timestamp_url='https://127.0.0.1:9/tsa-endpoint-marker')
            source = root / 'in.png'
            Image.new('RGB', (512, 512), (90, 120, 150)).save(source)
            registry = Registry(root / 'registry.sqlite3')
            output = root / 'out.png'
            with SDK(Watermarker(), identity, registry) as sdk:
                with self.assertRaises(AriadneError) as caught:
                    sdk.mark(source, output, example_record())
            message = str(caught.exception)
            self.assertIn('no output published', message)
            self.assertNotIn('tsa-endpoint-marker', message)
            self.assertNotIn('127.0.0.1', message)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_name(output.name + '.receipt.json').exists())
            with registry.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM assets').fetchone()[0], 0)
            self.assertEqual([p.name for p in root.iterdir() if p.name.startswith('.ariadne-')], [])

    def test_low_level_sign_file_removes_its_failed_output(self):
        from PIL import Image
        from ariadne_mark.signing import create_development_identity, sign_file
        from tests.provenance.test_records import example_record
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            create_development_identity(root / 'id')
            identity = SigningIdentity.from_directory(root / 'id', allow_dev=True,
                                                      timestamp_url='https://127.0.0.1:9/tsa')
            Image.new('RGB', (512, 512)).save(root / 'in.png')
            with self.assertRaisesRegex(AriadneError, 'no output published'):
                sign_file(root / 'in.png', root / 'out.png', example_record(), '014d123456789abc', identity)
            self.assertFalse((root / 'out.png').exists())
