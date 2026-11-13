"""Release R3 contracts: explicit scope, compatible recovery and independent claims."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ariadne_mark.verification.media import verify_file, _verification_result, _registry_recovery
from ariadne_mark.verification.scope import normalize_scope
from ariadne_mark.softbinding import ALGORITHMS, compatible_manifest_algorithms
from ariadne_mark.profiles import template, evaluate
from ariadne_mark.errors import AriadneError

Q = 'adobe.trustmark.Q.variax-bch5'
P = 'adobe.trustmark.Q.bch5'
VS = 'meta.videoseal.1.0.bch20'
A = '014d123456789abc'
B = '014d000000000001'

class ReleaseR3(unittest.TestCase):
    def test_scope_validation(self):
        self.assertIn(VS, normalize_scope('all'))
        self.assertNotIn(VS, normalize_scope('current'))
        for bad in ('', [], [Q, Q], ['custom'], 3):
            with self.assertRaises(ValueError): normalize_scope(bad)

    def check_video(self, *, signed=None, q_missing=False, scope='current'):
        class Scan:
            algorithm = Q
            def scan_video(self, path):
                if q_missing: raise AriadneError('missing_primary')
                return {'samples': [{'time':0.0,'token':None}], 'aggregates': [], 'status': 'not_found',
                        'search': {'reason': 'file_exhausted', 'file_exhausted': True, 'hypotheses_complete': True}}
        class PythonQ:
            algorithm = P
            def decode(self, image): raise ImportError('optional_python_q_not_installed')
        class Legacy:
            algorithm = VS
            def decode_frames(self, frames): raise AssertionError('out-of-scope legacy must not run')
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder)/'file.mp4'; file.touch()
            claim = {'status':'verified_claim','watermark_algorithm':VS,'issuer_trust':'trusted'} if signed else {'status':'not_found'}
            with patch('ariadne_mark.verification.media.inspect_c2pa', return_value=claim), patch('ariadne_mark.video.sample_frames',return_value=[(object(),0)]):
                return verify_file(file, marker=PythonQ(), video_marker=Scan(), legacy_video_marker=Legacy(), verification_scope=scope)

    def test_clean_current_scope_is_completed_without_legacy_and_aux_python(self):
        r=self.check_video();w=r['watermark']
        self.assertEqual(w['status'],'not_found')
        self.assertIn(VS,w['out_of_operator_scope'])
        self.assertEqual(w['unavailable_engines'],[])
        self.assertEqual(w['unavailable_auxiliary_engines'][0]['algorithm'],P)

    def test_missing_primary_and_signed_out_of_scope_stay_incomplete(self):
        self.assertEqual(self.check_video(q_missing=True)['watermark']['status'],'not_checked')
        r=self.check_video(signed=True)
        self.assertEqual(r['watermark']['status'],'not_checked')
        self.assertEqual(r['watermark']['reason'],'signed_scheme_out_of_operator_scope')

    def test_compatibility_is_directional_video_only_and_never_videoseal(self):
        self.assertIn(ALGORITHMS[Q],compatible_manifest_algorithms([P],video=True))
        self.assertNotIn(ALGORITHMS[Q],compatible_manifest_algorithms([P],video=False))
        self.assertNotIn(ALGORITHMS[P],compatible_manifest_algorithms([Q],video=True))
        self.assertNotIn(ALGORITHMS[VS],compatible_manifest_algorithms([P],video=True))

    def test_compatible_recovery_still_validates_actual_algorithm_and_signature(self):
        class Registry:
            def get(self,token): return {'record':{},'sha256':'abc'}
            def get_manifest(self,token):return {'algorithm':ALGORITHMS[Q],'bytes':b'store','sha256':'sha','public':True}
        with patch('ariadne_mark.softbinding.inspect_recovered',return_value={'soft_binding':'matched','signature':'valid'}) as inspect:
            r=_registry_recovery(Path('video.mp4'),B,[P],Registry(),lambda:'other')
            self.assertEqual(r['manifest']['signature'],'valid')
            self.assertEqual(inspect.call_args.args[2],ALGORITHMS[Q])
            self.assertEqual(inspect.call_args.args[3],B)
            self.assertEqual(r['content_binding'],'not_verified')

    def test_signed_id_observed_is_independent_of_multiple_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'x.mp4';file.touch()
            r=_verification_result(file,{'status':'verified_claim','token':A},
                {'status':'multiple_ids','samples':[{'time':0,'token':B}], 'ids':[{'token':B,'status':'observed','bases':[]}]},registry=None,video=True)
            self.assertFalse(r['signed_id_observed'])
            self.assertFalse(r['token_mismatch'])

    def test_dev_identity_label_keeps_incomplete_watermark_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'x.png';file.touch()
            r=_verification_result(file,{'status':'verified_claim','development_identity':True},
                {'status':'not_checked'},registry=None,video=False)
            self.assertIn('watermark check incomplete',r['label'])

    def test_missing_profile_mode_requires_explicit_choice_and_preserves_sdk_default(self):
        c=template(); c.update(publisher='Example',system={'name':'Generator','version':'1'}); c['sdk']['audio_kind']='none'; c['sdk'].pop('video_profile')
        self.assertFalse(evaluate(c)['export_supported'])
        for mode in ('economy_5s','economy_2s','resilient'):
            c['sdk'].update(video_profile=mode,video_profile_reason='Measured cost and delivery transforms')
            r=evaluate(c); self.assertTrue(r['export_supported'])
            self.assertEqual(r['sdk_options']['video_profile_reason'],c['sdk']['video_profile_reason'])
