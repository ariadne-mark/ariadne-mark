import os,unittest
from . import test_media as fixtures
@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires real video engine')
class MotionRefreshTests(unittest.TestCase):
 setUp=fixtures.MediaTests.setUp;tearDown=fixtures.MediaTests.tearDown
 setUpClass=classmethod(fixtures.MediaTests.setUpClass.__func__);tearDownClass=classmethod(fixtures.MediaTests.tearDownClass.__func__)
 video=fixtures.MediaTests.video;image=fixtures.MediaTests.image;record=fixtures.MediaTests.record;ffmpeg=fixtures.MediaTests.ffmpeg
 def test_fast_refreshes_when_anchor_content_moves(self):
  from PIL import Image
  from ariadne_mark.pipeline import SDK
  from ariadne_mark.videoq import VideoWatermarker
  import numpy as np
  rng=np.random.default_rng(5);w,h=512,320;pixels=np.zeros((h*2,w*2,3),np.float32)
  for side,amplitude in ((4,35),(16,30),(64,20),(256,10)):
   noise=Image.fromarray(rng.integers(0,256,(side,side,3),dtype=np.uint8)).resize((w*2,h*2),Image.Resampling.BICUBIC)
   pixels+=(np.asarray(noise,np.float32)-128)*amplitude/128
  texture=self.path/'texture.png';Image.fromarray(np.clip(128+pixels,0,255).astype('uint8')).save(texture)
  source=self.path/'pan.mp4';self.ffmpeg('-loop','1','-framerate','24','-i',texture,'-vf',f'crop={w}:{h}:x=t*48:y=t*27','-t','2','-c:v','libx264','-crf','20','-pix_fmt','yuv420p',source)
  marker=VideoWatermarker(profile='fast');sdk=SDK(self.marker,self.identity,video_marker=marker)
  try:
   receipt=sdk.mark(source,self.path/'out.mp4',self.record('video'))
   coverage=receipt['verification']['watermark']['sample_coverage']
   self.assertEqual(coverage['matched_frames'],coverage['sampled_frames'])
   self.assertGreater(receipt['video']['watermark_stats']['motion_refreshes'],0)
  finally:sdk.close()
