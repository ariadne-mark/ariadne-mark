import unittest
from ariadne_mark.verification.media import summarize_watermarks

TOKEN='014d123456789abc'

class SampleConfirmationTests(unittest.TestCase):
    def test_export_window_readback_is_distinct_from_public_blind_confirmation(self):
        from types import SimpleNamespace
        from pathlib import Path
        from unittest.mock import patch
        from ariadne_mark.verification.media import verify_video_export
        engine=SimpleNamespace(profile='economy_5s',algorithm='test',
            decode_frames=lambda frames:([{'time':0,'token':TOKEN}],None))
        with patch('ariadne_mark.video.selected_window_frames',return_value=[(object(),0,0,0)]),\
             patch('ariadne_mark.video.color.frame_image',return_value=object()),\
             patch('ariadne_mark.video._orient',side_effect=lambda image,rotation:image),\
             patch('ariadne_mark.verification.media.inspect_c2pa',return_value={'status':'not_found'}):
            good=verify_video_export(Path('fixture.mp4'),engine,[0])['watermark']
            self.assertEqual(good['status'],'recovered_claim')
            self.assertEqual(good['token'],TOKEN)
            self.assertEqual(good['sample_coverage']['confirmation_basis'],'known_schedule_export_readback')
            missing=verify_video_export(Path('fixture.mp4'),engine,[0,1])['watermark']
            self.assertEqual(missing['status'],'single_observation')
            self.assertFalse(missing['export_window_readback']['all_windows_have_id'])

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
