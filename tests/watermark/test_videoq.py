import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ariadne_mark.videoq import VideoWatermarker,ALGORITHM
from ariadne_mark.verification.media import verify_file
class NewVideoPolicyTests(unittest.TestCase):
 def test_constructor_lazy_and_profile_validation(self):
  self.assertIsNone(VideoWatermarker()._process)
  with self.assertRaises(ValueError):VideoWatermarker(profile='compliant')
 def test_signed_new_engine_routes_and_falls_back_without_expected_id(self):
  token='014d123456789abc';sizes=[]
  class New:
   algorithm=ALGORITHM
   def decode_frames(self,frames):
    sizes.append(len(frames));return ([{'time':t,'token':None} for _,t in frames],{'token':token} if len(frames)==20 else None)
  class Legacy:
   def decode(self,f):raise AssertionError('legacy engine must not be invoked')
  def sample(path,*,samples=5):return [(object(),i) for i in range(samples)]
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'fixture.mp4';p.touch()
   with patch('ariadne_mark.video.sample_frames',side_effect=sample),patch('ariadne_mark.verification.media.inspect_c2pa',return_value={'status':'verified_claim','issuer_trust':'trusted','watermark_algorithm':ALGORITHM}):
    result=verify_file(p,marker=Legacy(),video_marker=New())
  self.assertEqual(sizes,[5,20]);self.assertEqual(result['watermark']['token'],token);self.assertEqual(len(result['watermark']['attempts']),2)
