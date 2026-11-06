"""Timestamp-based recovery bank, including NTSC, VFR and unknown phase."""
from fractions import Fraction
import unittest

from ariadne_mark.video.detection import phase_groups


class FractionalSearchTests(unittest.TestCase):
    def test_supported_rates_exhaust_the_default_bank(self):
        for fps in [24, 25, 30, 60, 120, Fraction(24000,1001), Fraction(30000,1001), Fraction(60000,1001)]:
            with self.subTest(fps=str(fps)):
                times = [float(Fraction(i) / fps) for i in range(int(10*fps))]
                groups = list(phase_groups(times))
                self.assertNotIn(None, groups)
                self.assertLessEqual(len(groups), 512)
                self.assertTrue(groups)
                self.assertTrue(all(2 <= len(g[2]) <= 20 for g in groups))

    def test_unknown_phase_has_a_pure_window_group_for_each_preset(self):
        for fps in [24, 30, Fraction(24000,1001), Fraction(30000,1001)]:
            times = [float(Fraction(i) / fps) for i in range(int(12*fps))]
            for period in [2,5]:
                for phase in [.031, .317, 1.123]:
                    marked = {i for i,t in enumerate(times) if (t-phase) % period < .125}
                    groups = [g for g in phase_groups(times) if g[0] == period]
                    self.assertTrue(any(set(g[2]) <= marked and len({int((times[i]-phase)/period) for i in g[2]}) >= 2 for g in groups), (fps,period,phase))

    def test_vfr_offset_and_duplicate_groups(self):
        times = [i/29.97 for i in range(360) if i%7 != 3]
        a = list(phase_groups(times))
        b = list(phase_groups([t+1234 for t in times]))
        self.assertEqual([g[2] for g in a], [g[2] for g in b])
        self.assertEqual(len(a), len({g[2] for g in a}))
        self.assertNotIn(None, a)

    def test_reduced_budget_is_explicitly_incomplete(self):
        groups = list(phase_groups([i/29.97 for i in range(300)], max_hypotheses=1))
        self.assertEqual(len(groups), 2)
        self.assertIsNone(groups[-1])
