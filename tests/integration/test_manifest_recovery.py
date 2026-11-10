"""Real C2PA stores, watermark recovery and portable receipts on CPU media."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from urllib.parse import urlencode, quote

from . import test_media as fixtures


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS') == '1', 'requires real media bundle')
class ManifestRecoveryMediaTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.MediaTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MediaTests.tearDownClass.__func__)
    image = fixtures.MediaTests.image
    video = fixtures.MediaTests.video
    ffmpeg = fixtures.MediaTests.ffmpeg
    record = fixtures.MediaTests.record

    def setUp(self):
        import tempfile
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        self.temp = tempfile.TemporaryDirectory(dir=self.root); self.path = Path(self.temp.name)
        self.sdk = SDK(self.marker, self.identity, Registry(self.path/'registry.sqlite'),
                       trust_anchors=self.root/'identity/trust.pem')

    def tearDown(self): self.sdk.close(); self.temp.cleanup()

    def check_store(self, receipt, asset):
        from ariadne_mark.softbinding import inspect_recovered
        bundle = self.sdk.registry.get_manifest(token=receipt['token'])
        self.assertEqual(bundle['id'],receipt['verification']['c2pa']['manifest_id'])
        # A CBOR byte string of length 8 follows the literal "value" key.
        self.assertIn(b'\x65value\x48'+bytes.fromhex(receipt['token']), bundle['bytes'])
        self.assertNotIn(b'\x65value\x88', bundle['bytes'])
        checked = inspect_recovered(bundle['bytes'],asset,bundle['algorithm'],receipt['token'],
                                    trust_anchors=self.root/'identity/trust.pem')
        self.assertEqual(checked['signature'],'valid')
        return bundle, checked

    def test_image_stripping_and_standard_http_recovery_with_signed_report(self):
        from ariadne_mark.server import make_server
        from ariadne_mark.reports import ReportSigner, verify_report
        from ariadne_mark.softbinding import query_value
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from PIL import Image
        output=self.path/'marked.png'
        receipt=self.sdk.mark(self.image(),output,self.record(),publish_manifest=True)
        bundle, checked = self.check_store(receipt, output)
        self.assertEqual(checked['asset_binding'],'valid')
        stripped=self.path/'stripped.png'
        with Image.open(output) as im: im.convert('RGB').save(stripped)
        self.assertEqual(self.sdk.verify(stripped)['c2pa']['status'],'not_found')
        saved=self.path/'recovered.c2pa'
        result=self.sdk.recover_manifest(stripped,saved)
        self.assertEqual(saved.read_bytes(),bundle['bytes'])
        self.assertNotEqual(result['manifest']['asset_binding'],'valid')
        signer=ReportSigner(Ed25519PrivateKey.generate(),'https://verify.example.test')
        server=make_server(self.sdk,port=0,public_manifests=True,report_signer=signer)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        conn=http.client.HTTPConnection(*server.server_address,timeout=120)
        try:
            conn.request('POST','/verify?format=png',stripped.read_bytes());r=conn.getresponse()
            report=json.loads(r.read());self.assertEqual(r.status,200)
            payload=verify_report(report,signer.public_pem(),asset=stripped)
            self.assertEqual(payload['result']['recovery']['manifest']['soft_binding'],'matched')
            query=urlencode({'alg':bundle['algorithm'],'value':query_value(receipt['token'])})
            conn.request('GET','/matches/byBinding?'+query);r=conn.getresponse()
            self.assertEqual(json.loads(r.read())['matches'][0]['manifestId'],bundle['id'])
            conn.request('GET','/manifests/'+quote(bundle['id'],safe=''));r=conn.getresponse()
            self.assertEqual(r.getheader('Content-Type'),'application/c2pa')
            self.assertEqual(r.read(),bundle['bytes'])
            (self.path/'signed-report.json').write_text(json.dumps(report['signed_report']))
            (self.path/'report.pub').write_bytes(signer.public_pem())
            command=[sys.executable,'-m','ariadne_mark.cli','report','verify',str(self.path/'signed-report.json'),
                     '--public-key',str(self.path/'report.pub'),'--asset',str(stripped)]
            p=subprocess.run(command,capture_output=True,text=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout)['signature'],'valid')
        finally: conn.close();server.shutdown();server.server_close();thread.join()

    def test_all_video_modes_keep_their_policies_and_recover_exact_manifest_after_remux(self):
        source=self.video(audio=False)
        for mode in ['economy_5s','economy_2s','resilient']:
            with self.subTest(mode=mode):
                output=self.path/(mode+'.mp4')
                receipt=self.sdk.mark(source,output,self.record('video'),video_profile=mode,publish_manifest=True)
                self.assertEqual(receipt['video']['profile'],mode)
                if mode == 'resilient':
                    self.assertEqual(receipt['video']['marked_frames'],receipt['video']['frames_encoded'])
                else:
                    self.assertLess(receipt['video']['marked_frames'],receipt['video']['frames_encoded'])
                bundle,_=self.check_store(receipt,output)
                stripped=self.path/(mode+'-stripped.mp4')
                self.ffmpeg('-i',output,'-map_metadata','-1','-c','copy',stripped)
                saved=self.path/(mode+'.c2pa')
                recovered=self.sdk.recover_manifest(stripped,saved)
                self.assertEqual(saved.read_bytes(),bundle['bytes'])
                self.assertEqual(recovered['verification']['watermark']['token'],receipt['token'])

    def test_tampered_manifest_is_rejected_by_native_signature_validation(self):
        from ariadne_mark.softbinding import inspect_recovered
        output=self.path/'tamper.png'
        receipt=self.sdk.mark(self.image(),output,self.record())
        bundle,_=self.check_store(receipt,output)
        # Change a signed public assertion without changing the soft-binding ID.
        damaged=bundle['bytes'].replace(b'Test Publisher',b'Fake Publisher',1)
        self.assertNotEqual(damaged,bundle['bytes'])
        try:
            checked=inspect_recovered(damaged,output,bundle['algorithm'],receipt['token'])
        except Exception:
            pass  # Native parser rejection is also a failed verification.
        else:
            self.assertNotEqual(checked['signature'],'valid')
