"""Offline RFC 3161 failure paths with the real native client (ADOPTION-OPT-01 item 5).

An OpenSSL TSA on loopback answers normally, with HTTP 401/500, or with a
valid token for *different* data. Signing must fail and publish nothing;
an untrusted TSA root must stop a production export at the SDK gate.
This is offline simulation, not qualification of any public TSA service.
"""
import os, subprocess, tempfile, threading, unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS') == '1', 'requires OpenSSL, C2PA, Pillow and models')
class TsaFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, rsa
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        cls.folder = tempfile.TemporaryDirectory(); p = cls.p = Path(cls.folder.name)
        now = datetime.now(timezone.utc); pem = serialization.Encoding.PEM

        def ca(name):
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
            cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
                    .not_valid_after(now + timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
                    .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
                    .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False).sign(key, hashes.SHA256()))
            return key, subject, cert

        def leaf(issuer, key, name, eku, critical=False):
            ikey, iname, _ = issuer
            return (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                    .issuer_name(iname).public_key(key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
                    .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), True)
                    .add_extension(x509.ExtendedKeyUsage([eku]), critical)
                    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ikey.public_key()), False)
                    .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False).sign(ikey, hashes.SHA256()))
        root, other = ca('Offline issuer and TSA root'), ca('Unrelated TSA root')
        key = ec.generate_private_key(ec.SECP256R1()); tsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signer = leaf(root, key, 'Offline production-style signer', ExtendedKeyUsageOID.EMAIL_PROTECTION)
        tsa = leaf(root, tsa_key, 'Offline TSA', ExtendedKeyUsageOID.TIME_STAMPING, True)
        (p / 'root.pem').write_bytes(root[2].public_bytes(pem)); (p / 'other.pem').write_bytes(other[2].public_bytes(pem))
        (p / 'cert.pem').write_bytes(signer.public_bytes(pem) + root[2].public_bytes(pem)); (p / 'tsa.pem').write_bytes(tsa.public_bytes(pem))
        for name, k in [('key', key), ('tsa', tsa_key)]:
            (p / (name + '.key')).write_bytes(k.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        (p / 'serial').write_text('01\n')
        (p / 'tsa.cnf').write_text(f"[tsa]\nserial = {p/'serial'}\nsigner_cert = {p/'tsa.pem'}\ncerts = {p/'root.pem'}\n"
            f"signer_key = {p/'tsa.key'}\nsigner_digest = sha256\ndefault_policy = 1.2.3.4.1\ndigests = sha256\n"
            "accuracy = secs:1\nordering = yes\ntsa_name = yes\ness_cert_id_chain = yes\ness_cert_id_alg = sha256\n")
        # A valid query for unrelated data, used to answer with a mismatched token.
        (p / 'other.dat').write_bytes(b'unrelated data')
        subprocess.run(['openssl', 'ts', '-query', '-data', str(p / 'other.dat'), '-sha256', '-cert', '-out', str(p / 'other.tsq')], check=True)
        cls.mode = 'ok'; cls.requests = []; owner = cls

        class TSA(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append({'mode': owner.mode, 'authorization': self.headers.get('Authorization')})
                if owner.mode in {'401', '500'}:
                    self.send_error(int(owner.mode)); return
                query = p / 'request.tsq'; query.write_bytes(body)
                if owner.mode == 'wrong_imprint':
                    query = p / 'other.tsq'
                done = subprocess.run(['openssl', 'ts', '-reply', '-config', str(p / 'tsa.cnf'), '-section', 'tsa',
                                       '-queryfile', str(query), '-out', str(p / 'reply.tsr')], capture_output=True)
                if done.returncode:
                    self.send_error(500); return
                reply = (p / 'reply.tsr').read_bytes()
                self.send_response(200); self.send_header('Content-Type', 'application/timestamp-reply')
                self.send_header('Content-Length', str(len(reply))); self.end_headers(); self.wfile.write(reply)
        cls.server = HTTPServer(('127.0.0.1', 0), TSA)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/tsa'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.folder.cleanup()

    def sign(self, mode, name):
        from PIL import Image
        from ariadne_mark.signing import SigningIdentity, sign_file
        from tests.provenance.test_records import example_record
        type(self).mode = mode
        Image.new('RGB', (256, 256), 'gray').save(self.p / 'input.png')
        identity = SigningIdentity(self.p / 'cert.pem', self.p / 'key.key', True, self.url)
        return sign_file(self.p / 'input.png', self.p / name, example_record(), '014d000000000001', identity)

    def test_trusted_token_is_embedded_on_success(self):
        from ariadne_mark.verification.media import inspect_c2pa
        self.sign('ok', 'ok.png')
        stamped = inspect_c2pa(self.p / 'ok.png', trust_anchors=self.p / 'root.pem', tsa_trust_anchors=self.p / 'root.pem')
        self.assertEqual(stamped['timestamp_trust'], 'trusted', stamped)
        other = inspect_c2pa(self.p / 'ok.png', trust_anchors=self.p / 'root.pem', tsa_trust_anchors=self.p / 'other.pem')
        self.assertNotEqual(other['timestamp_trust'], 'trusted', other)
        self.assertIsNone(self.requests[-1]['authorization'])  # pinned runtime sends no credentials

    def test_error_responses_and_mismatched_token_fail_without_output(self):
        from ariadne_mark.errors import AriadneError
        for mode in ['401', '500', 'wrong_imprint']:
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(AriadneError, 'no output published') as caught:
                    self.sign(mode, mode + '.png')
                self.assertNotIn('127.0.0.1', str(caught.exception))
                self.assertFalse((self.p / (mode + '.png')).exists())

    def test_untrusted_tsa_root_stops_a_production_export_at_the_gate(self):
        from PIL import Image
        from ariadne_mark.errors import VerificationFailed
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        from ariadne_mark.signing import SigningIdentity
        from ariadne_mark.watermark import Watermarker
        from tests.provenance.test_records import example_record
        type(self).mode = 'ok'
        # A production-style identity requires HTTPS, so build it without
        # validation only to exercise the SDK's trusted-timestamp gate offline.
        identity = SigningIdentity.__new__(SigningIdentity)
        for k, v in dict(certificate=self.p / 'cert.pem', private_key=self.p / 'key.key', development=False,
                         timestamp_url=self.url).items():
            object.__setattr__(identity, k, v)
        source, output = self.p / 'prod-in.png', self.p / 'prod-out.png'
        Image.new('RGB', (512, 512), (40, 90, 140)).save(source)
        registry = Registry(self.p / 'prod.sqlite3')
        with SDK(Watermarker(), identity, registry, trust_anchors=self.p / 'root.pem',
                 tsa_trust_anchors=self.p / 'other.pem') as sdk:
            with self.assertRaisesRegex(VerificationFailed, 'trusted timestamp'):
                sdk.mark(source, output, example_record())
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + '.receipt.json').exists())
        with registry.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM assets').fetchone()[0], 0)
