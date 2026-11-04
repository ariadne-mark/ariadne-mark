"""Regression attacks from the independent 0.4 audit, using real engines."""
import os,json,tempfile,unittest
from pathlib import Path
from . import test_media as fixtures
@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires real media bundle')
class AuditMediaTests(unittest.TestCase):
 setUpClass=classmethod(fixtures.MediaTests.setUpClass.__func__)
 tearDownClass=classmethod(fixtures.MediaTests.tearDownClass.__func__)
 setUp=fixtures.MediaTests.setUp
 tearDown=fixtures.MediaTests.tearDown
 image=fixtures.MediaTests.image
 video=fixtures.MediaTests.video
 ffmpeg=fixtures.MediaTests.ffmpeg
 record=fixtures.MediaTests.record
 def test_foreign_signer_is_not_attributed_and_strict_cli_rejects_it(self):
  from ariadne_mark.pipeline import SDK
  from ariadne_mark.signing import create_development_identity,SigningIdentity
  from ariadne_mark.cli import main
  from contextlib import redirect_stdout
  import io
  create_development_identity(self.path/'attacker')
  attacker=SDK(self.marker,SigningIdentity.from_directory(self.path/'attacker',allow_dev=True))
  out=self.path/'forged.png';attacker.mark(self.image(),out,self.record())
  self.sdk.trust_anchors=self.root/'identity/trust.pem'
  report=self.sdk.verify(out)
  self.assertEqual(report['c2pa']['issuer_trust'],'untrusted')
  self.assertEqual(report['label'],'Signature valid; issuer unverified')
  with redirect_stdout(io.StringIO()):self.assertEqual(main(['verify',str(out),'--strict','--trust-anchors',str(self.sdk.trust_anchors)]),2)
  attacker.close()
 def test_copied_id_is_not_authenticated_as_the_source_content(self):
  from PIL import Image
  a=self.path/'a.png';receipt=self.sdk.mark(self.image(),a,self.record());token=receipt['token']
  copied=self.path/'copied.png';self.marker.encode(Image.effect_noise((640,512),50).convert('RGB'),token).save(copied)
  report=self.sdk.verify(copied)
  self.assertEqual(report['watermark']['token'],token)
  self.assertEqual(report['recovery']['content_binding'],'not_verified')
  self.assertIn('content match unverified',report['label'])
  self.assertEqual(self.sdk.verify(a)['recovery']['content_binding'],'exact_registered_file')
 def test_spliced_new_profile_video_reports_partial_evidence(self):
  from ariadne_mark.pipeline import SDK
  source=self.video(audio=False)
  for profile in ['fast','resilient']:
   with SDK(self.marker,self.identity,self.sdk.registry,video_profile=profile) as sdk:
    out=self.path/(profile+'.mp4');receipt=sdk.mark(source,out,self.record('video'))
    spliced=self.path/(profile+'-spliced.mp4')
    self.ffmpeg('-i',out,'-i',source,'-filter_complex','[0:v]trim=duration=0.5,setpts=PTS-STARTPTS[a];[1:v]trim=duration=1.5,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[v]','-map','[v]','-map_metadata','-1','-c:v','libx264','-crf','18',spliced)
    report=sdk.verify(spliced)
    self.assertEqual(report['watermark']['token'],receipt['token'])
    coverage=report['watermark']['sample_coverage']
    self.assertEqual(coverage['interpretation'],'partial_sample_evidence')
    self.assertLess(coverage['matched_frames'],coverage['sampled_frames'])
    self.assertIn('sampled video evidence only',report['label'])
 def test_icc_input_requires_explicit_color_conversion(self):
  from ariadne_mark.errors import UnsupportedMedia
  from PIL import Image,ImageCms
  path=self.path/'icc.png';Image.new('RGB',(512,512),'white').save(path,icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
  with self.assertRaisesRegex(UnsupportedMedia,'ICC'):self.sdk.mark(path,self.path/'out.png',self.record())
