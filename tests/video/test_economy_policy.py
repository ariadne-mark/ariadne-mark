import unittest
from fractions import Fraction

from ariadne_mark.video.policy import WindowSelector
from ariadne_mark.videoq import VideoWatermarker
from ariadne_mark.pipeline import SDK
from ariadne_mark.profiles import template, validate, evaluate


class EconomyPolicyTests(unittest.TestCase):
    def test_nonzero_timebase_and_window_boundaries(self):
        for profile, expected in [('economy_5s', 6), ('economy_2s', 15), ('resilient', 240)]:
            selector = WindowSelector(profile)
            rows = [selector.select(Fraction(700, 3) + Fraction(i, 24)) for i in range(240)]
            self.assertEqual(sum(selected for selected, _ in rows), expected)
            self.assertEqual(rows[3][0], profile == 'resilient')

    def test_vfr_gap_does_not_skip_an_occupied_period(self):
        selector = WindowSelector('economy_5s')
        rows = [selector.select(Fraction(t)) for t in ['9', '9.2', '14.3', '14.4', '25.8']]
        self.assertEqual(rows, [(True, 0), (False, 0), (True, 1), (False, 1), (True, 3)])

    def test_lazy_default_and_per_export_worker_selection(self):
        with SDK() as sdk:
            self.assertEqual(sdk.video_marker.profile, 'economy_5s')
            self.assertIsNone(sdk.video_marker._process)
            two = sdk._select_video_marker('economy_2s')
            self.assertIs(two, sdk._select_video_marker('economy_2s'))
            self.assertEqual(two.profile, 'economy_2s')
            self.assertIsNone(two._process)
            self.assertEqual(sdk._select_video_marker('resilient').profile, 'resilient')
        for bad in ['economy_1s', 'compliant', 5, None]:
            with self.assertRaises(ValueError):
                VideoWatermarker(profile=bad)

    def test_old_config_defaults_without_mutating_input_and_new_config_is_fingerprinted(self):
        config = template()
        del config['sdk']['video_profile']
        default = validate(config)
        self.assertEqual(default['sdk']['video_profile'], 'economy_5s')
        self.assertNotIn('video_profile', config['sdk'])
        base_hash = evaluate(default)['configuration_sha256']
        default['sdk']['video_profile'] = 'economy_2s'
        self.assertNotEqual(evaluate(default)['configuration_sha256'], base_hash)
        self.assertEqual(evaluate(default)['sdk_options']['video_profile'], 'economy_2s')
        default['sdk']['video_profile'] = 'economy_1s'
        with self.assertRaises(ValueError):
            validate(default)
