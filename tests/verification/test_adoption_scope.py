"""ADOPTION-OPT-01: trust routing, scope projections and export/verify scope (P-01..P-03)."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ariadne_mark.errors import AriadneError
from ariadne_mark.verification.media import verify_file

Q = 'adobe.trustmark.Q.variax-bch5'
P = 'adobe.trustmark.Q.bch5'
VS = 'meta.videoseal.1.0.bch20'
A = '014d123456789abc'   # operator's ID in the pixels
B = '014d000000000001'   # ID asserted by a third-party signed claim


def trusted(alg, token=B):
    # A public-CA-trusted, non-development third-party signer (P-01 trigger).
    return {'status': 'verified_claim', 'issuer_trust': 'trusted', 'watermark_algorithm': alg, 'token': token}


class TrustedRouting(unittest.TestCase):
    def probe(self, claim, *, primary='positive', scope='current', video=True):
        calls = []

        class Video:
            algorithm = Q
            def scan_video(self, path):
                calls.append(Q)
                if primary == 'missing':
                    raise AriadneError('primary missing')
                token = A if primary == 'positive' else None
                return {'samples': [{'time': t, 'token': token} for t in [0., 1.]], 'aggregates': [],
                        'status': 'recovered_claim' if token else 'not_found',
                        'search': {'reason': 'file_exhausted', 'file_exhausted': True, 'hypotheses_complete': True}}

        class Python:
            algorithm = P
            def decode(self, image):
                calls.append(P)
                return None

        class Legacy:
            algorithm = VS
            def decode_frames(self, frames):
                calls.append(VS)
                return [{'time': t, 'token': None} for _, t in frames], None

        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / ('x.mp4' if video else 'x.png')
            p.touch()
            with patch('ariadne_mark.verification.media.inspect_c2pa', return_value=claim), \
                 patch('ariadne_mark.video.sample_frames', return_value=[(object(), 0.), (object(), 1.)]), \
                 patch('ariadne_mark.verification.media.open_image', return_value=object()):
                r = verify_file(p, marker=Python(), video_marker=Video(), legacy_video_marker=Legacy(),
                                verification_scope=scope)
        return r, calls

    def test_trusted_python_q_claim_cannot_switch_off_operator_video_scan(self):
        # Review P-01 q2: before the fix only Python-Q ran and the operator ID was hidden.
        r, calls = self.probe(trusted(P))
        w = r['watermark']
        self.assertIn(Q, calls)
        self.assertEqual(w['token'], A)
        self.assertTrue(r['token_mismatch'])  # conflict with the signed claim is visible
        self.assertEqual(w['declared_schemes'], [Q, P])

    def test_trusted_out_of_scope_claim_still_scans_primary(self):
        # Review P-01 q3: before the fix nothing ran and the result was not_checked.
        r, calls = self.probe(trusted(VS))
        w = r['watermark']
        self.assertEqual(calls.count(Q), 1)
        self.assertNotIn(VS, calls)  # the out-of-scope technique itself is still not run
        self.assertEqual(w['token'], A)
        self.assertEqual(w['signed_scheme_unchecked'], VS)

    def test_trusted_out_of_scope_claim_negative_stays_unknown(self):
        r, calls = self.probe(trusted(VS), primary='negative')
        w = r['watermark']
        self.assertIn(Q, calls)
        self.assertEqual((w['status'], w['reason']), ('not_checked', 'signed_scheme_out_of_operator_scope'))

    def test_trusted_legacy_claim_in_all_scope_scans_primary_and_claimed(self):
        r, calls = self.probe(trusted(VS), scope='all', primary='negative')
        self.assertEqual(sorted(set(calls)), sorted({Q, VS}))
        self.assertNotIn(P, calls)  # only *other* legacy schemes may be skipped
        self.assertEqual(r['watermark']['declared_schemes'], [Q, VS])

    def test_trusted_primary_claim_keeps_the_fast_path(self):
        r, calls = self.probe(trusted(Q, A), scope='all')
        self.assertEqual(calls, [Q])
        self.assertEqual(r['watermark']['declared_schemes'], [Q])

    def test_missing_primary_under_trusted_claim_is_incomplete(self):
        r, calls = self.probe(trusted(P), primary='missing')
        self.assertEqual(r['watermark']['status'], 'not_checked')


class Projections(unittest.TestCase):
    def test_completed_is_subset_of_declared_and_supplemental_is_separate(self):
        # Review P-02: current-scope MP4 listed Python-Q as completed and out of scope at once.
        r, _ = TrustedRouting.probe(self, {'status': 'not_found'}, primary='negative')
        w = r['watermark']
        self.assertTrue(set(w['completed_schemes']) <= set(w['declared_schemes']))
        self.assertEqual(w['completed_schemes'], [Q])
        self.assertEqual(w['supplemental_completed_schemes'], [P])
        self.assertIn(P, w['out_of_operator_scope'])
        self.assertFalse(set(w['completed_schemes']) & set(w['out_of_operator_scope']))

    def test_positive_early_stop_is_not_a_completed_negative(self):
        class Early:
            algorithm = Q
            def scan_video(self, path):
                return {'samples': [{'time': 0., 'token': A}, {'time': .04, 'token': A}], 'aggregates': [],
                        'status': 'recovered_claim',
                        'search': {'reason': 'two_concordant_ids', 'file_exhausted': False, 'hypotheses_complete': True}}
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'x.mp4'
            p.touch()
            with patch('ariadne_mark.verification.media.inspect_c2pa', return_value={'status': 'not_found'}), \
                 patch('ariadne_mark.video.sample_frames', return_value=[(object(), 0.)]):
                w = verify_file(p, video_marker=Early(), verification_scope='current')['watermark']
        self.assertEqual(w['token'], A)
        self.assertEqual(w['completed_schemes'], [])

    def test_public_projection_keeps_new_fields(self):
        from ariadne_mark.public_verifier import public_report
        r, _ = TrustedRouting.probe(self, trusted(VS))
        public = public_report(r)['watermark']
        self.assertEqual(public['signed_scheme_unchecked'], VS)
        self.assertIn('supplemental_completed_schemes', public)


class ExportScope(unittest.TestCase):
    def test_mark_refuses_encoder_outside_own_verification_scope(self):
        # Review P-03: a VideoSeal encoder in current scope produced marks its own verifier cannot detect.
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.provenance import MediaKind
        from ariadne_mark.signing import SigningIdentity
        from tests.provenance.test_records import example_record

        class FakeVideoSeal:
            algorithm = VS
            profile = 'legacy'
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'in.mp4'
            source.write_bytes(b'not decoded before refusal')
            sdk = SDK(identity=SigningIdentity(Path('c'), Path('k'), True), video_marker=FakeVideoSeal(),
                      verification_scope='current')
            with patch.object(SDK, 'check_runtime'), \
                 patch('ariadne_mark.pipeline.inspect_c2pa', side_effect=AssertionError('media touched')):
                with self.assertRaisesRegex(ValueError, 'outside this SDK'):
                    sdk.mark(source, Path(folder) / 'out.mp4', example_record(media_kind=MediaKind.VIDEO))
            self.assertFalse((Path(folder) / 'out.mp4').exists())

    def test_image_export_needs_python_q_in_scope(self):
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.signing import SigningIdentity
        from tests.provenance.test_records import example_record
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'in.png'
            source.write_bytes(b'x')
            sdk = SDK(identity=SigningIdentity(Path('c'), Path('k'), True), verification_scope=[Q])
            with patch.object(SDK, 'check_runtime'):
                with self.assertRaisesRegex(ValueError, 'outside this SDK'):
                    sdk.mark(source, Path(folder) / 'out.png', example_record())
