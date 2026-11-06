"""Media tests isolate color conversions from neural watermark residuals."""
import os
import unittest
from types import SimpleNamespace
from ariadne_mark.video.color import ColorPolicy
from ariadne_mark.errors import UnsupportedMedia


class ColorPolicyTests(unittest.TestCase):
    def test_untagged_fallback_and_unsupported_matrix(self):
        def frame(matrix, rng, fmt='yuv420p'):
            return SimpleNamespace(colorspace=matrix,color_range=rng,format=SimpleNamespace(name=fmt))
        self.assertEqual(ColorPolicy.from_frame(frame(2,0)),ColorPolicy(6,1))
        self.assertEqual(ColorPolicy.from_frame(frame(2,0,'yuvj420p')),ColorPolicy(6,2))
        with self.assertRaises(UnsupportedMedia):ColorPolicy.from_frame(frame(9,1))
        with self.assertRaises(UnsupportedMedia):ColorPolicy(1,1).check(frame(1,2))


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires PyAV and numpy')
class ColorRoundtripTests(unittest.TestCase):
    def test_limited_full_601_709_match_ffmpeg_and_do_not_darken(self):
        import av,numpy as np,subprocess
        from PIL import Image
        from ariadne_mark.video.color import ColorConverter
        # Smooth, unsaturated chromatic ramp: isolates rounding and coefficients.
        y,x=np.mgrid[:320,:512]
        pixels=np.stack([40+x*.3,50+y*.4,60+x*.15+y*.12],axis=-1).astype('uint8')
        for matrix,name in [(1,'bt709'),(6,'bt601')]:
            for rng,range_name in [(1,'tv'),(2,'pc')]:
                with self.subTest(matrix=matrix,range=rng):
                    convert=ColorConverter(ColorPolicy(matrix,rng))
                    original=convert.frame(Image.fromarray(pixels))
                    rgb=np.asarray(convert.image(original))
                    reference=subprocess.run(['ffmpeg','-v','error','-threads','1','-f','rawvideo','-pixel_format','yuv420p','-video_size','512x320','-i','pipe:0','-vf',f'scale=in_color_matrix={name}:out_color_matrix={name}:in_range={range_name}:out_range=pc:flags=bilinear+accurate_rnd+full_chroma_int','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],input=original.to_ndarray().tobytes(),capture_output=True,check=True).stdout
                    ref=np.frombuffer(reference,dtype='uint8').reshape(320,512,3)
                    self.assertLess(float(abs(rgb.astype(float)-ref).mean()),.25)
                    before=original.to_ndarray()[:320,:512].astype(float)
                    after=convert.frame(convert.image(original)).to_ndarray()[:320,:512].astype(float)
                    self.assertLess(abs(float((after-before).mean())),.1)
                    self.assertLess(float(abs(after-before).mean()),.2)

    def test_export_preserves_matrix_range_and_nearly_constant_identity_luma(self):
        import av,json,numpy as np,subprocess,tempfile
        from pathlib import Path
        from PIL import Image
        from ariadne_mark.video import encode_video
        from ariadne_mark.video.color import ColorConverter
        class Identity:
            profile='economy_5s'
            batch_size=1
            def encode_frames(self,images,token):return images
        y,x=np.mgrid[:320,:512]
        pixels=np.stack([40+x*.3,50+y*.4,60+x*.15+y*.12],axis=-1).astype('uint8')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for matrix,name in [(1,'bt709'),(6,'smpte170m')]:
                for rng,range_name in [(1,'tv'),(2,'pc')]:
                    with self.subTest(matrix=matrix,range=rng):
                        raw=ColorConverter(ColorPolicy(matrix,rng)).frame(Image.fromarray(pixels)).to_ndarray().tobytes()
                        source=root/'source.mp4';dest=root/'export.mp4'
                        subprocess.run(['ffmpeg','-v','error','-y','-threads','1','-f','rawvideo','-pix_fmt','yuv420p','-s','512x320','-r','2','-i','pipe:0','-c:v','libx264','-crf','18','-colorspace',name,'-color_range',range_name,str(source)],input=raw*4,capture_output=True,check=True)
                        receipt=encode_video(source,dest,Identity(),'014d123456789abc')
                        with av.open(str(dest)) as c:
                            cc=c.streams.video[0].codec_context
                            self.assertEqual(cc.colorspace,matrix)
                            self.assertEqual(cc.color_range,rng)
                            means=[float(f.to_ndarray()[:f.height,:f.width].mean()) for f in c.decode(video=0)]
                        self.assertEqual(len(means),4)
                        self.assertLess(abs(means[0]-sum(means[1:])/3),.2)
                        self.assertEqual(receipt['marked_frames'],1)
