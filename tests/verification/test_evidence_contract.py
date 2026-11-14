"""B06 contract matrix on controlled observations (semantics, not media durability).

The real blind search (video.detection.scan_video) and verify_file run here;
only the decoded frames, decoder outputs and the C2PA reader are recorded
stubs. Real-media integration for the same cases is a separate server plan.
"""
import json
import tempfile
import types
import unittest
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from ariadne_mark.errors import MissingModel
from ariadne_mark.video import SampledFrame
from ariadne_mark.verification.media import summarize_watermarks, verify_file
from ariadne_mark.videoq import ALGORITHM as Q
from ariadne_mark.videoseal.payload import ALGORITHM as VS

A = '014d123456789abc'
B = '014d000000000001'
FPS = 24


def frame_id(pts):
    return {'stream': 0, 'pts': pts, 'time_base': f'1/{FPS}'}


class QScanner:
    """Per-frame decoder outputs replayed through the real sequential search."""
    algorithm = Q
    implementation = 'recorded-observations'

    def __init__(self, tokens, aggregates=(), **limits):
        self.tokens, self.aggregates, self.limits, self.calls = tokens, list(aggregates), limits, 0

    def decode_logits(self, image):
        index = self.calls
        self.calls += 1
        return self.tokens[index], [float(index + 1)] * 100

    def aggregate_logits(self, rows):
        return self.aggregates.pop(0) if self.aggregates else None

    def scan_video(self, path):
        from ariadne_mark.video.detection import scan_video
        tokens = self.tokens

        class Frame:
            def __init__(self, i):
                self.pts, self.time_base = i, Fraction(1, FPS)

        class Container:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def decode(self, **kwargs): return iter(Frame(i) for i in range(len(tokens)))
        with patch.dict('sys.modules', av=types.SimpleNamespace(open=lambda *a, **k: Container())), \
             patch('ariadne_mark.video.probe', return_value={'rotation': 0}), \
             patch('ariadne_mark.video.validate_decoder_streams'), \
             patch('ariadne_mark.video.color.frame_image', side_effect=lambda f: object()):
            return scan_video(path, self, **self.limits)


class SampledDecoder:
    """Legacy-scheme decoder on the distributed sample (5 requested targets)."""
    algorithm = VS
    implementation = 'recorded-observations'

    def __init__(self, tokens_by_pts=None, error=None):
        self.tokens_by_pts, self.error = tokens_by_pts or {}, error

    def decode_frames(self, frames):
        if self.error:
            raise self.error
        rows = [{'time': t, 'token': self.tokens_by_pts.get(item.identity['pts'])} for item in frames for t in [item[1]]]
        return rows, None


class NullImageDecoder:
    algorithm = 'adobe.trustmark.Q.bch5'

    def decode(self, image):
        return None


class Registry:
    def __init__(self, entries=None):
        self.entries, self.calls = entries or {}, []

    def get(self, token):
        self.calls.append(token)
        return self.entries.get(token)


SAMPLES = [SampledFrame(object(), pts / FPS, frame_id(pts)) for pts in (0, 60, 120, 180, 239)]


def run(c2pa, scanner=None, legacy=None, marker=NullImageDecoder(), registry=None, suffix='.mp4'):
    with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
        path = Path(folder) / ('fixture' + suffix)
        path.write_bytes(b'fixture')
        stack.enter_context(patch('ariadne_mark.verification.media.inspect_c2pa', return_value=json.loads(json.dumps(c2pa))))
        stack.enter_context(patch('ariadne_mark.video.sample_frames', return_value=list(SAMPLES)))
        stack.enter_context(patch('ariadne_mark.verification.media.open_image', return_value=object()))
        return verify_file(path, marker=marker, video_marker=scanner,
                           legacy_video_marker=legacy or SampledDecoder(), registry=registry)


SIGNED_A = {'status': 'verified_claim', 'signature': 'valid', 'issuer_trust': 'untrusted', 'token': A,
            'watermark_algorithm': None, 'record': {'action': 'created'}}
UNSIGNED = {'status': 'not_found', 'signature': 'not_checked', 'issuer_trust': 'not_checked'}


def ids(report):
    return {entry['token']: entry for entry in report['watermark']['ids']}


class SeveralIdsTests(unittest.TestCase):
    def test_a_plus_b_keeps_both_ids_and_does_not_invalidate_signature(self):
        tokens = [A] + [None] * 119 + [B] + [None] * 119
        report = run(SIGNED_A, QScanner(tokens))
        watermark = report['watermark']
        self.assertEqual(watermark['status'], 'multiple_ids')
        self.assertNotIn('token', watermark)
        self.assertEqual(set(ids(report)), {A, B})
        self.assertEqual(report['c2pa']['status'], 'verified_claim')
        self.assertNotIn('Invalid', report['label'])
        self.assertIn('Multiple watermark IDs', report['label'])
        self.assertTrue(ids(report)[A]['matches_signed_claim'])
        self.assertFalse(ids(report)[B]['matches_signed_claim'])
        self.assertEqual(ids(report)[B]['first_time_s'], 120 / FPS)
        self.assertFalse(report['token_mismatch'])
        self.assertEqual(report['schema_version'], 2)

    def test_second_scheme_reveals_b_after_scan_stopped_on_a(self):
        # Sequential scan stops after two A reads; the distributed legacy
        # sample still sees B later. Both stay, each with its own scheme.
        report = run(UNSIGNED, QScanner([A, A] + [None] * 238), SampledDecoder({180: B, 239: B}))
        self.assertEqual(report['watermark']['status'], 'multiple_ids')
        a, b = ids(report)[A], ids(report)[B]
        self.assertEqual((a['status'], a['bases'][0]['algorithm']), ('confirmed', Q))
        self.assertEqual((b['status'], b['bases'][0]['algorithm']), ('confirmed', VS))
        self.assertIn('sampled video evidence only', report['label'])

    def test_registry_lookup_per_confirmed_id_without_choosing_one(self):
        registry = Registry({A: {'record': {'action': 'created'}, 'sha256': '0' * 64}})
        report = run(UNSIGNED, QScanner([A, A] + [None] * 238), SampledDecoder({180: B, 239: B}), registry=registry)
        recovery = report['recovery']
        self.assertEqual(recovery['status'], 'per_id')
        self.assertEqual(recovery['automatic_selection'], 'none')
        per_id = {row['token']: row for row in recovery['per_id']}
        self.assertEqual(per_id[A]['status'], 'found')
        self.assertEqual(per_id[A]['algorithms'], [Q])
        self.assertEqual(per_id[A]['content_binding'], 'not_verified')
        self.assertEqual(per_id[B]['status'], 'unknown_id')
        self.assertEqual(sorted(registry.calls), sorted([A, B]))

    def test_unconfirmed_reads_are_not_looked_up(self):
        registry = Registry({A: {'record': {}, 'sha256': '0' * 64}, B: {'record': {}, 'sha256': '0' * 64}})
        report = run(UNSIGNED, QScanner([A] + [None] * 119 + [B] + [None] * 119), registry=registry)
        self.assertEqual({row['reason'] for row in report['recovery']['per_id']}, {'id_not_confirmed'})
        self.assertEqual(registry.calls, [])

    def test_signed_and_watermark_id_mismatch_is_a_conflict_not_invalid_signature(self):
        report = run(SIGNED_A, QScanner([B, B] + [None] * 238))
        self.assertTrue(report['token_mismatch'])
        self.assertEqual(report['c2pa']['status'], 'verified_claim')
        self.assertTrue(report['label'].startswith('Conflicting provenance claims'))


class CoverageTests(unittest.TestCase):
    def test_a_then_clean_reports_where_the_id_was_seen(self):
        report = run(UNSIGNED, QScanner([A, A] + [None] * 238))
        watermark = report['watermark']
        self.assertEqual((watermark['status'], watermark['token']), ('recovered_claim', A))
        scope = watermark['evidence_scope']
        self.assertFalse(scope['whole_file_examined'])
        self.assertEqual(scope['unexamined_content'], 'not_established')
        scan = next(p for p in scope['passes'] if p['algorithm'] == Q)
        self.assertEqual((scan['coverage'], scan['unique_frames'], scan['stop_reason']),
                         ('prefix_until_stop', 2, 'two_concordant_ids'))
        self.assertFalse({'samples', 'search', 'aggregate'} & set(scan))  # bounded summary only
        self.assertEqual(ids(report)[A]['positions_s'], [0.0, 1 / FPS])
        self.assertIn('sampled video evidence only', report['label'])

    def test_clean_then_a_keeps_its_late_position(self):
        report = run(UNSIGNED, QScanner([None] * 200 + [A] * 40))
        self.assertEqual(report['watermark']['token'], A)
        self.assertEqual(ids(report)[A]['first_time_s'], 200 / FPS)
        self.assertFalse(report['watermark']['evidence_scope']['whole_file_examined'])

    def test_short_fragment_single_read_is_kept_but_not_promoted(self):
        registry = Registry({A: {'record': {}, 'sha256': '0' * 64}})
        report = run(UNSIGNED, QScanner([A] + [None] * 239), registry=registry)
        watermark = report['watermark']
        self.assertEqual(watermark['status'], 'single_observation')
        self.assertNotIn('token', watermark)
        self.assertEqual(ids(report)[A]['status'], 'observed')
        self.assertEqual(report['recovery'], {'status': 'not_attempted'})
        self.assertEqual(registry.calls, [])
        scope = watermark['evidence_scope']
        self.assertTrue(scope['whole_file_examined'])
        self.assertEqual(scope['full_decode_schemes'], [Q])
        # Legacy schemes only saw the distributed sample.
        self.assertEqual(scope['unexamined_content'], 'not_established')
        self.assertNotIn('AI-generated', report['label'])

    def test_budget_stop_is_incomplete_and_keeps_the_positive_read(self):
        report = run(UNSIGNED, QScanner([None] * 5 + [A] + [None] * 200, max_frames=20))
        watermark = report['watermark']
        self.assertEqual(watermark['status'], 'not_checked')
        self.assertEqual(ids(report)[A]['status'], 'observed')
        self.assertEqual(report['label'], 'Check incomplete')
        scan = next(p for p in watermark['evidence_scope']['passes'] if p['algorithm'] == Q)
        self.assertEqual(scan['stop_reason'], 'frame_or_time_budget')
        self.assertFalse(scan['complete'])

    def test_unavailable_engine_keeps_positive_reads_and_scope_is_partial(self):
        legacy = SampledDecoder(error=MissingModel('fixture'))
        report = run(UNSIGNED, QScanner([A] + [None] * 239), legacy)
        watermark = report['watermark']
        self.assertEqual(watermark['status'], 'single_observation')
        self.assertEqual(watermark['coverage'], 'partial')
        self.assertEqual(watermark['evidence_scope']['unavailable_schemes'], [VS])
        self.assertEqual(watermark['evidence_scope']['unexamined_content'], 'not_established')
        clean = run(UNSIGNED, QScanner([None] * 240), legacy)['watermark']
        self.assertEqual((clean['status'], clean['reason']), ('not_checked', 'incomplete_engine_coverage'))

    def test_legacy_only_scheme_without_its_decoder_is_not_imitated(self):
        signed_legacy = {**SIGNED_A, 'issuer_trust': 'trusted', 'watermark_algorithm': 'adobe.trustmark.Q.bch5'}
        scanner = QScanner([A] * 240)
        report = run(signed_legacy, scanner, marker=None)
        w = report['watermark']
        # ADOPTION-OPT-01 / review P-01: a trusted claim no longer switches off
        # the operator's primary video-Q scan, so the scanner runs. The
        # protection is unchanged: the missing Python-Q decoder is reported and
        # video-Q evidence never stands in for the claimed Python-Q layout.
        self.assertGreater(scanner.calls, 0)
        self.assertIn('adobe.trustmark.Q.bch5', [u['algorithm'] for u in w['unavailable_engines']])
        self.assertNotIn('adobe.trustmark.Q.bch5', w['completed_schemes'])
        self.assertEqual(w.get('coverage'), 'partial')


class CryptoContextTests(unittest.TestCase):
    def test_corrupt_signature_is_invalid_and_watermark_evidence_survives(self):
        corrupt = {'status': 'invalid', 'signature': 'invalid', 'issuer_trust': 'not_checked',
                   'reason': 'malformed_c2pa'}
        with_scan = run(corrupt, QScanner([A, A] + [None] * 238))
        self.assertEqual(with_scan['label'], 'Invalid or conflicting provenance; sampled video evidence only')
        self.assertEqual(with_scan['c2pa']['status'], 'invalid')
        self.assertEqual(with_scan['watermark']['token'], A)
        # Adding or removing watermark engines never changes the C2PA block
        # evaluated on the same bytes and validation context.
        without_legacy = run(corrupt, QScanner([A, A] + [None] * 238), SampledDecoder(error=MissingModel('x')))
        image_only = run(corrupt, marker=NullImageDecoder(), suffix='.png')
        self.assertEqual(with_scan['c2pa'], without_legacy['c2pa'])
        self.assertEqual(with_scan['c2pa'], image_only['c2pa'])

    def test_copied_id_in_registry_is_not_a_content_match(self):
        class Image:
            algorithm = 'adobe.trustmark.Q.bch5'
            def decode(self, image): return A
        registry = Registry({A: {'record': {'action': 'created'}, 'sha256': 'f' * 64}})
        report = run(UNSIGNED, marker=Image(), registry=registry, suffix='.png')
        self.assertEqual(report['recovery']['status'], 'found')
        self.assertEqual(report['recovery']['content_binding'], 'not_verified')
        self.assertEqual(report['label'], 'Watermark ID found in registry; content match unverified')


class FrameIdentityTests(unittest.TestCase):
    def test_one_frame_read_by_two_passes_is_one_unique_frame(self):
        rows = [{'time': 0.0, 'token': A, 'algorithm': Q, 'pass': 0, 'frame': frame_id(0)},
                {'time': 0.0, 'token': A, 'algorithm': Q, 'pass': 1, 'frame': frame_id(0)}]
        result = summarize_watermarks(rows, [], video=True)
        self.assertEqual(result['status'], 'single_observation')
        basis = result['ids'][0]['bases'][0]
        self.assertEqual((basis['unique_frames'], basis['observations']), (1, 2))
        self.assertEqual(len(result['samples']), 2)  # both views retained
        distinct = rows[:1] + [{**rows[1], 'frame': frame_id(1), 'time': 1 / FPS}]
        self.assertEqual(summarize_watermarks(distinct, [], video=True)['token'], A)

    def test_same_float_time_without_pts_is_not_counted_twice(self):
        rows = [{'time': 0.5, 'token': A, 'algorithm': Q}, {'time': 0.5, 'token': A, 'algorithm': Q}]
        self.assertEqual(summarize_watermarks(rows, [], video=True)['status'], 'single_observation')

    def test_fallback_passes_keep_all_rows_and_count_overlap_once(self):
        class Sampled:
            algorithm = Q
            def decode_frames(self, frames):
                return [{'time': item[1], 'token': None} for item in frames], None

        def sample(path, *, samples=5):
            positions = sorted({round(239 * i / max(samples - 1, 1)) for i in range(samples)})
            return [SampledFrame(object(), p / FPS, frame_id(p)) for p in positions]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture.mp4'
            path.write_bytes(b'x')
            with patch('ariadne_mark.video.sample_frames', side_effect=sample), \
                 patch('ariadne_mark.verification.media.inspect_c2pa', return_value={**SIGNED_A, 'issuer_trust': 'trusted', 'watermark_algorithm': Q}):
                report = verify_file(path, video_marker=Sampled())
        first, second = sample(None), sample(None, samples=20)
        union = {f.identity['pts'] for f in first + second}
        watermark = report['watermark']
        self.assertEqual(len(watermark['samples']), len(first) + len(second))
        self.assertEqual(watermark['checked_frames'], len(union))
        self.assertEqual([p['requested_positions'] for p in watermark['evidence_scope']['passes']], [5, 20])
        self.assertEqual(watermark['status'], 'not_found')

    def test_different_payload_schemes_are_never_merged(self):
        rows = [{'time': 0.0, 'token': A, 'algorithm': Q, 'frame': frame_id(0)},
                {'time': 1.0, 'token': A, 'algorithm': 'adobe.trustmark.Q.bch5', 'frame': frame_id(24)}]
        self.assertEqual(summarize_watermarks(rows, [], video=True)['status'], 'single_observation')


class EvidenceHistoryTests(unittest.TestCase):
    def test_extended_trace_keeps_earlier_ids_and_may_become_more_cautious(self):
        base = [{'time': 0.0, 'token': A, 'algorithm': Q, 'frame': frame_id(0)},
                {'time': 1 / FPS, 'token': A, 'algorithm': Q, 'frame': frame_id(1)}]
        before = summarize_watermarks(base, [], video=True)
        after = summarize_watermarks(base + [{'time': 5.0, 'token': B, 'algorithm': Q, 'frame': frame_id(120)}], [], video=True)
        self.assertEqual(before['status'], 'recovered_claim')
        self.assertEqual(after['status'], 'multiple_ids')
        self.assertLessEqual({e['token'] for e in before['ids']}, {e['token'] for e in after['ids']})
        earlier = next(e for e in after['ids'] if e['token'] == A)
        self.assertEqual(earlier['bases'], before['ids'][0]['bases'])
        self.assertEqual(earlier['status'], 'confirmed')

    def test_conflicting_aggregates_confirm_neither_id(self):
        result = summarize_watermarks([{'time': 0.0, 'token': None, 'algorithm': Q}],
                                      [{'token': A, 'algorithm': Q}, {'token': B, 'algorithm': Q}], video=True)
        self.assertEqual(result['status'], 'multiple_ids')
        self.assertEqual({e['status'] for e in result['ids']}, {'observed'})

    def test_id_list_and_positions_are_bounded(self):
        rows = [{'time': i / FPS, 'token': f'014d{i:012x}', 'algorithm': Q, 'frame': frame_id(i)} for i in range(40)]
        result = summarize_watermarks(rows, [], video=True)
        self.assertEqual(len(result['ids']), 16)
        self.assertEqual(result['ids_truncated'], 24)
