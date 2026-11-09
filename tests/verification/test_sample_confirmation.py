import unittest
from ariadne_mark.verification.media import summarize_watermarks

TOKEN='014d123456789abc'

class SampleConfirmationTests(unittest.TestCase):
    def test_legacy_single_sample_is_not_a_confirmed_video_claim(self):
        result=summarize_watermarks([{'time':0,'token':TOKEN,'algorithm':'legacy'}],[],video=True)
        self.assertEqual(result['status'],'single_observation');self.assertNotIn('token',result)
        self.assertEqual(result['sample_coverage']['matched_frames'],1)
        self.assertEqual(result['sample_coverage']['confirmation_status'],'single_observation')

    def test_two_samples_or_aggregate_confirm_one_scheme(self):
        rows=[{'time':0,'token':TOKEN,'algorithm':'legacy'},{'time':1,'token':TOKEN,'algorithm':'legacy'}]
        self.assertEqual(summarize_watermarks(rows,[],video=True)['token'],TOKEN)
        self.assertEqual(summarize_watermarks(rows[:1],[{'token':TOKEN,'algorithm':'legacy'}],video=True)['token'],TOKEN)
        self.assertEqual(summarize_watermarks(rows[:1],[],video=False)['token'],TOKEN)

    def test_different_schemes_do_not_double_count_one_observation_each(self):
        rows=[{'time':0,'token':TOKEN,'algorithm':'a'},{'time':1,'token':TOKEN,'algorithm':'b'}]
        self.assertEqual(summarize_watermarks(rows,[],video=True)['status'],'single_observation')
