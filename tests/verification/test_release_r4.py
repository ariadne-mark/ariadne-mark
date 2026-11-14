"""R4: untrusted routing, honest negative scope and tri-state observations."""
import contextlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from ariadne_mark.errors import AriadneError
from ariadne_mark.verification.media import verify_file, _verification_result
from ariadne_mark.verification.scope import media_scope, runtime_warnings
from ariadne_mark.softbinding import ALGORITHMS
from ariadne_mark.server import make_server

Q='adobe.trustmark.Q.variax-bch5'
P='adobe.trustmark.Q.bch5'
VS='meta.videoseal.1.0.bch20'
A='014d123456789abc'
B='014d000000000001'

class Routing(unittest.TestCase):
    def probe(self,claim,*,primary='positive',python='negative',scope='current'):
        calls=[]
        class Video:
            algorithm=Q
            def scan_video(self,path):
                calls.append(Q)
                if primary=='missing':raise AriadneError('primary missing')
                token=A if primary=='positive' else None
                return {'samples':[{'time':t,'token':token} for t in [0.,1.]],'aggregates':[],
                        'status':'recovered_claim' if token else 'not_found',
                        'search':{'reason':'file_exhausted','file_exhausted':True,'hypotheses_complete':True}}
        class Python:
            algorithm=P
            def decode(self,image):
                calls.append(P)
                if python=='missing':raise ImportError('Python-Q missing')
                return None
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'x.mp4';p.touch()
            with patch('ariadne_mark.verification.media.inspect_c2pa',return_value=claim),patch('ariadne_mark.video.sample_frames',return_value=[(object(),0.),(object(),1.)]):
                r=verify_file(p,marker=Python(),video_marker=Video(),verification_scope=scope)
        return r,calls

    def test_untrusted_signatures_cannot_hide_primary_ID(self):
        for alg in [VS,P,Q]:
            with self.subTest(alg=alg):
                r,calls=self.probe({'status':'verified_claim','issuer_trust':'untrusted','development_identity':True,'watermark_algorithm':alg,'token':B})
                self.assertIn(Q,calls);self.assertEqual(r['watermark']['token'],A)
                self.assertTrue(r['token_mismatch'])
                self.assertEqual(r['watermark']['signed_routing'],'independent_operator_scan')

    def test_development_identity_never_gets_trusted_fast_path(self):
        r,calls=self.probe({'status':'verified_claim','issuer_trust':'trusted','development_identity':True,'watermark_algorithm':VS,'token':B})
        self.assertIn(Q,calls);self.assertEqual(r['watermark']['token'],A)

    def test_trusted_current_scope_declares_only_primary_obligation(self):
        r,calls=self.probe({'status':'verified_claim','issuer_trust':'trusted','watermark_algorithm':Q,'token':A},scope='current')
        self.assertEqual(calls,[Q]);self.assertEqual(r['watermark']['declared_schemes'],[Q])

    def test_missing_primary_and_successful_auxiliary_negative_is_incomplete(self):
        r,calls=self.probe({'status':'not_found'},primary='missing')
        self.assertIn(P,calls)
        self.assertEqual(r['watermark']['status'],'not_checked')
        self.assertEqual(r['watermark']['reason'],'incomplete_engine_coverage')
        self.assertEqual(r['watermark']['unavailable_engines'][0]['algorithm'],Q)

    def test_missing_python_required_by_signed_claim_is_reported(self):
        r,calls=self.probe({'status':'verified_claim','issuer_trust':'untrusted','watermark_algorithm':P,'token':B},primary='negative',python='missing')
        self.assertIn(Q,calls);self.assertIn(P,calls)
        self.assertEqual(r['watermark']['status'],'not_checked')
        self.assertEqual(r['watermark']['reason'],'incomplete_engine_coverage')
        self.assertEqual(r['watermark']['unavailable_auxiliary_engines'],[])
        self.assertEqual(r['watermark']['unavailable_engines'][0]['algorithm'],P)

    def test_current_negative_does_not_claim_legacy_python_video_coverage(self):
        r,calls=self.probe({'status':'not_found'},primary='negative',python='missing')
        w=r['watermark'];self.assertEqual(w['status'],'not_found')
        self.assertEqual(w['declared_schemes'],[Q]);self.assertEqual(w['completed_schemes'],[Q])
        self.assertIn(P,w['unavailable_auxiliary_engines'][0]['algorithm'])
        self.assertEqual(media_scope('current',video=False),(P,))
        self.assertIn(P,media_scope('all',video=True))

class Observation(unittest.TestCase):
    def result(self,w,**claim):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'x.png';p.touch()
            return _verification_result(p,{'status':'verified_claim','token':A,'issuer_trust':'untrusted',**claim},w,registry=None,video=False)
    def test_no_attempt_is_unknown_not_absent(self):
        r=self.result({'status':'not_checked','ids':[]})
        self.assertIsNone(r['signed_id_observed']);self.assertIn('watermark check incomplete',r['label'])
    def test_partial_positive_keeps_observation(self):
        r=self.result({'status':'not_checked','ids':[{'token':A}],'samples':[{'token':A}]})
        self.assertIs(r['signed_id_observed'],True)
    def test_performed_negative_is_false(self):
        r=self.result({'status':'not_found','ids':[],'samples':[{'token':None}]})
        self.assertIs(r['signed_id_observed'],False)

class ResolverScope(unittest.TestCase):
    def request(self,alg,report,scope='current'):
        class SDK:
            verification_scope=scope
            calls=0
            def verify(self,p):self.calls+=1;return report
        sdk=SDK()
        with patch('ariadne_mark.verification.scope.runtime_warnings',return_value=[]):server=make_server(sdk,port=0,public_manifests=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            conn=http.client.HTTPConnection(*server.server_address,timeout=5)
            conn.request('POST','/matches/byContent?format=mp4&alg='+ALGORITHMS[alg],body=b'x')
            response=conn.getresponse();result=(response.status,json.loads(response.read()),sdk.calls);conn.close();return result
        finally:server.shutdown();server.server_close();thread.join()
    def test_explicit_outside_scope_is_refused_before_inference(self):
        status,body,calls=self.request(VS,{})
        self.assertEqual((status,calls),(422,0));self.assertEqual(body['status'],'not_checked')
    def test_negative_requires_completed_requested_scheme(self):
        r={'watermark':{'status':'not_found','completed_schemes':[Q]}}
        self.assertEqual(self.request(VS,r,scope='all')[0],503)
        self.assertEqual(self.request(Q,r)[0],200)

class ModelSelection(unittest.TestCase):
    def run_models(self,*args):
        from ariadne_mark.cli import main
        stdout=io.StringIO();stderr=io.StringIO()
        original=importlib.util.find_spec
        def spec(name,*a,**kw):return None if name=='trustmark' else original(name,*a,**kw)
        with patch('importlib.util.find_spec',side_effect=spec),patch('ariadne_mark.videoq.check_models',return_value={'ok':True}),patch('ariadne_mark.watermark.check_models',side_effect=AriadneError('media missing')),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            code=main(['models','check',*args])
        return code,stdout.getvalue(),stderr.getvalue()
    def test_bare_check_selects_video_but_explicit_media_is_strict(self):
        code,out,err=self.run_models();self.assertEqual(code,0);self.assertEqual(json.loads(out)['selection']['selected'],'video')
        self.assertNotEqual(self.run_models('--engine','media')[0],0)
    def test_legacy_warning_does_not_download_or_change_scope(self):
        with patch('ariadne_mark.videoseal.check_models',side_effect=AriadneError('missing')):
            self.assertEqual(runtime_warnings('current'),[])
            self.assertEqual(runtime_warnings('all')[0]['code'],'legacy_decoder_unavailable')

class PublicScope(unittest.TestCase):
    def test_declared_completed_and_routing_survive_public_projection(self):
        from ariadne_mark.public_verifier import public_report
        w={'status':'not_found','configured_schemes':[P,Q],'declared_schemes':[Q],
           'completed_schemes':[Q],'signed_routing':'independent_operator_scan',
           'unavailable_engines':[]}
        self.assertEqual(public_report({'watermark':w})['watermark'],w)

class ExportScope(unittest.TestCase):
    def test_local_export_scope_comes_from_the_configured_encoder(self):
        from ariadne_mark.pipeline import SDK
        class Encoder:algorithm=VS
        with SDK() as sdk,patch('ariadne_mark.pipeline.verify_file',return_value={'fixture':True}) as verify:
            self.assertEqual(sdk._verify_export(Path('export.mp4'),Encoder()),{'fixture':True})
            self.assertEqual(verify.call_args.kwargs['verification_scope'],(VS,))
