import os,unittest
from pathlib import Path
from unittest.mock import patch
from . import test_media as fixtures
@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires real media runtime')
class ReviewRegressions(unittest.TestCase):
 setUpClass=classmethod(fixtures.MediaTests.setUpClass.__func__)
 tearDownClass=classmethod(fixtures.MediaTests.tearDownClass.__func__)
 setUp=fixtures.MediaTests.setUp;tearDown=fixtures.MediaTests.tearDown
 video=fixtures.MediaTests.video;image=fixtures.MediaTests.image;record=fixtures.MediaTests.record;ffmpeg=fixtures.MediaTests.ffmpeg
 def test_partial_video_export_is_rejected_before_publication(self):
  from ariadne_mark.errors import VerificationFailed
  original=self.sdk._verify_export
  def partial(path,engine):
   report=original(path,engine);report['watermark']['samples'][-1]['token']=None;return report
  target=self.path/'partial.mp4'
  with patch.object(self.sdk,'_verify_export',side_effect=partial),self.assertRaises(VerificationFailed):self.sdk.mark(self.video(audio=False),target,self.record('video'))
  self.assertFalse(target.exists());self.assertFalse(Path(str(target)+'.receipt.json').exists())
 def test_actual_pyav_codec_is_checked_even_if_preflight_is_wrong(self):
  from ariadne_mark.video import sample_frames,probe
  from ariadne_mark.errors import UnsupportedMedia
  source=self.video(audio=False);wrong=self.path/'mpeg4.mp4';self.ffmpeg('-i',source,'-c:v','mpeg4',wrong)
  info=probe(source)
  with patch('ariadne_mark.video.probe',return_value=info),self.assertRaisesRegex(UnsupportedMedia,'PyAV video decoder'):list(sample_frames(wrong))
 def test_production_rejects_real_development_root(self):
  from ariadne_mark.server import make_server
  self.sdk.trust_anchors=self.root/'identity/trust.pem'
  with self.assertRaisesRegex(ValueError,'Development roots'):make_server(self.sdk,port=0,production=True)
