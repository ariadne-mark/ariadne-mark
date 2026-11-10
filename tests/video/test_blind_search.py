"""Search boundaries and verdicts independent of a real neural decoder."""
import types
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from ariadne_mark.video.detection import scan_video

A = '014d123456789abc'
B = '014d000000000001'


class BlindSearchTests(unittest.TestCase):
    def run_scan(self, tokens, aggregates=(), **limits):
        calls = []
        aggregates = iter(aggregates)
        class Frame:
            def __init__(self, i):
                self.pts, self.time_base = i, Fraction(1, 24)
            def to_image(self): return object()
        class Container:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def decode(self, **kwargs): return iter(Frame(i) for i in range(len(tokens)))
        class Marker:
            def decode_logits(self, image):
                index = len(calls)
                calls.append(index)
                return tokens[index], [float(index + 1)] * 100
            def aggregate_logits(self, rows):
                self_test.assertTrue(all(len(r) == 100 for r in rows))
                return next(aggregates, None)
        self_test = self
        with patch.dict('sys.modules', av=types.SimpleNamespace(open=lambda *a, **k: Container())), \
             patch('ariadne_mark.video.probe', return_value={'rotation': 0}), \
             patch('ariadne_mark.video.validate_decoder_streams'), \
             patch('ariadne_mark.video.color.frame_image', side_effect=lambda f: f.to_image()):
            result = scan_video(Path('fixture.mp4'), Marker(), **limits)
        return result, calls

    def test_full_negative_and_single_observation_are_distinct(self):
        result, calls = self.run_scan([None] * 10)
        self.assertEqual(result['status'], 'not_found')
        self.assertTrue(result['search']['file_exhausted'])
        self.assertEqual(len(calls), 10)
        result, _ = self.run_scan([A] + [None] * 9)
        self.assertEqual(result['status'], 'single_observation')
        self.assertIsNone(result['token'])

    def test_cached_aggregation_does_not_run_a_second_cnn_pass(self):
        result, calls = self.run_scan([None] * 10, [A])
        self.assertEqual(result['status'], 'recovered_claim')
        self.assertEqual(result['token'], A)
        self.assertEqual(len(calls), 10)
        self.assertEqual(result['search']['cnn_passes'], 1)
        self.assertFalse(result['search']['expected_id_supplied'])

    def test_conflicting_aggregate_never_chooses_a_preferred_id(self):
        result, _ = self.run_scan([None] * 10, [A, B])
        self.assertEqual(result['status'], 'invalid')
        self.assertIsNone(result['token'])
        result, _ = self.run_scan([A, B])
        self.assertEqual(result['status'], 'invalid')

    def test_budgets_cannot_turn_a_partial_search_into_absence(self):
        result, calls = self.run_scan([None] * 20, max_frames=5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(result['status'], 'not_checked')
        self.assertFalse(result['search']['file_exhausted'])
        result, _ = self.run_scan([None] * 20, [A], max_hypotheses=1)
        self.assertEqual(result['status'], 'not_checked')
        self.assertFalse(result['search']['hypotheses_complete'])

    def test_direct_early_stop_does_not_claim_complete_video_coverage(self):
        result, calls = self.run_scan([A, A] + [None] * 18)
        self.assertEqual(result['status'], 'recovered_claim')
        self.assertEqual(len(calls), 2)
        self.assertFalse(result['search']['file_exhausted'])
        self.assertEqual(result['search']['whole_video_coverage'], 'not_established')
