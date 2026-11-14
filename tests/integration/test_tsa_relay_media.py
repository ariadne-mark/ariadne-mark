"""Real native signing through authenticated HTTPS TSA, using offline test PKI."""
import ipaddress
import os
import ssl
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
import unittest

from tests.integration import test_tsa_failures as fixtures


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires real native C2PA and models')
class AuthenticatedTsaTests(fixtures.TsaFailureTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
        cls.server.shutdown();cls.thread.join()
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Offline HTTPS TSA')])
        now=datetime.now(timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
              .not_valid_after(now+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=0),True)
              .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),False)
              .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),False).sign(key,hashes.SHA256()))
        (cls.p/'tls.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        (cls.p/'tls.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cls.p/'tls.pem',cls.p/'tls.key')
        cls.server.socket=tls.wrap_socket(cls.server.socket,server_side=True)
        original=cls.server.RequestHandlerClass;owner=cls
        class AuthTSA(original):
            def do_POST(self):
                if self.headers.get('Authorization')!='Bearer offline-fixture-token':self.send_error(401);return
                if owner.mode=='hang':time.sleep(1);return
                return super().do_POST()
        cls.server.RequestHandlerClass=AuthTSA
        import threading
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'https://127.0.0.1:{cls.server.server_port}/ecc'
        (cls.p/'credential').write_text('offline-fixture-token\n');(cls.p/'credential').chmod(0o600)

    def identity(self,*,credential='credential',timeout=10,ca=True):
        from ariadne_mark.signing import SigningIdentity
        return SigningIdentity(self.p/'cert.pem',self.p/'key.key',False,self.url,
                               self.p/credential,timeout,self.p/'tls.pem' if ca else None)

    # Parent cases exercise unauthenticated HTTP. They live in their original
    # class; this class replaces them with end-to-end authenticated cases.
    def test_trusted_token_is_embedded_on_success(self):
        from PIL import Image
        from ariadne_mark.signing import sign_file
        from ariadne_mark.verification.media import inspect_c2pa
        from tests.provenance.test_records import example_record
        type(self).mode='ok'
        source=self.p/'auth-in.png';out=self.p/'auth-ok.png';Image.new('RGB',(256,256),'gray').save(source)
        sign_file(source,out,example_record(),'014d000000000001',self.identity())
        result=inspect_c2pa(out,trust_anchors=self.p/'root.pem',tsa_trust_anchors=self.p/'root.pem')
        self.assertEqual(result['timestamp_trust'],'trusted',result)
        self.assertEqual(self.requests[-1]['authorization'],'Bearer offline-fixture-token')
        self.assertNotIn(b'offline-fixture-token',out.read_bytes())

    def test_error_responses_and_mismatched_token_fail_without_output(self):
        from PIL import Image
        from ariadne_mark.signing import sign_file
        from ariadne_mark.errors import AriadneError
        from tests.provenance.test_records import example_record
        source=self.p/'auth-errors-in.png';Image.new('RGB',(256,256),'gray').save(source)
        (self.p/'wrong-token').write_text('wrong');(self.p/'wrong-token').chmod(0o600)
        cases=[('ok',self.identity(credential='wrong-token')),('401',self.identity()),
               ('wrong_imprint',self.identity()),('hang',self.identity(timeout=.2)),('ok',self.identity(ca=False))]
        for i,(mode,identity) in enumerate(cases):
            type(self).mode=mode;out=self.p/f'auth-fail-{i}.png'
            with self.subTest(mode=mode),self.assertRaisesRegex(AriadneError,'no output published') as caught:
                sign_file(source,out,example_record(),'014d000000000001',identity)
            self.assertFalse(out.exists());self.assertNotIn('offline-fixture-token',str(caught.exception))

    def test_untrusted_tsa_root_stops_a_production_export_at_the_gate(self):
        from PIL import Image
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        from ariadne_mark.watermark import Watermarker
        from ariadne_mark.errors import VerificationFailed
        from tests.provenance.test_records import example_record
        type(self).mode='ok';source=self.p/'auth-prod.png';out=self.p/'auth-rejected.png'
        Image.new('RGB',(512,512),(40,90,140)).save(source);registry=Registry(self.p/'auth.sqlite3')
        with SDK(Watermarker(),self.identity(),registry,trust_anchors=self.p/'root.pem',tsa_trust_anchors=self.p/'other.pem') as sdk:
            with self.assertRaisesRegex(VerificationFailed,'trusted timestamp'):sdk.mark(source,out,example_record())
        self.assertFalse(out.exists());self.assertFalse(out.with_name(out.name+'.receipt.json').exists())
        with registry.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM assets').fetchone()[0],0)

    def test_authenticated_failure_cannot_publish_through_sdk(self):
        from PIL import Image
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        from ariadne_mark.watermark import Watermarker
        from ariadne_mark.errors import AriadneError
        from tests.provenance.test_records import example_record
        source=self.p/'auth-sdk-input.png';Image.new('RGB',(512,512),(40,90,140)).save(source)
        registry=Registry(self.p/'auth-failures.sqlite3')
        with SDK(Watermarker(),self.identity(timeout=.2),registry,
                 trust_anchors=self.p/'root.pem',tsa_trust_anchors=self.p/'root.pem') as sdk:
            for mode in ['401','wrong_imprint','hang']:
                type(self).mode=mode;out=self.p/f'auth-sdk-{mode}.png'
                with self.subTest(mode=mode),self.assertRaises(AriadneError):sdk.mark(source,out,example_record())
                self.assertFalse(out.exists());self.assertFalse(out.with_name(out.name+'.receipt.json').exists())
        with registry.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM assets').fetchone()[0],0)
