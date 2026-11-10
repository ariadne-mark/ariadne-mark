from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from ariadne_mark.verification.media import verify_file
class ImageScopeTests(unittest.TestCase):
 def test_unsigned_image_negative_needs_no_node_worker(self):
  class Images:
   algorithm='adobe.trustmark.Q.bch5'
   def decode(self,image):return None
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'plain.png';file.touch()
   with patch('ariadne_mark.verification.media.open_image',return_value=object()),patch('ariadne_mark.verification.media.inspect_c2pa',return_value={'status':'not_found'}),patch('ariadne_mark.videoq.VideoWatermarker',side_effect=AssertionError('Node must not be required')):
    report=verify_file(file,marker=Images())
   self.assertEqual(report['watermark']['status'],'not_found')
   self.assertEqual(report['watermark']['algorithm_scope'],'trustmark_image_scheme')
 def test_development_claim_is_never_headlined_as_trusted(self):
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'dev.png';file.touch()
   claim={'status':'verified_claim','issuer_trust':'trusted','development_identity':True,'record':{'action':'created'}}
   with patch('ariadne_mark.verification.media.inspect_c2pa',return_value=claim):report=verify_file(file)
   self.assertNotIn('trusted',report['label']);self.assertEqual(report['c2pa']['record_scope'],'development_signer_claim')
