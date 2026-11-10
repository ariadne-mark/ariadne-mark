"""Media tests isolate color conversions from neural watermark residuals."""
import os
import unittest
from types import SimpleNamespace
from ariadne_mark.video.color import ColorPolicy
from ariadne_mark.errors import UnsupportedMedia


class ColorPolicyTests(unittest.TestCase):
    def test_untagged_fallback_and_unsupported_matrix(self):
        def frame(matrix, rng, fmt='yuv420p'):
            return SimpleNamespace(colorspace=matrix,color_range=rng,format=SimpleNamespace(name=fmt,components=[SimpleNamespace(bits=8)]))
        self.assertEqual(ColorPolicy.from_frame(frame(2,0)),ColorPolicy(6,1))
        self.assertEqual(ColorPolicy.from_frame(frame(2,0,'yuvj420p')),ColorPolicy(6,2))
        with self.assertRaises(UnsupportedMedia):ColorPolicy.from_frame(frame(9,1))
        with self.assertRaises(UnsupportedMedia):ColorPolicy(1,1).check(frame(1,2))


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires PyAV and numpy')
class ColorRoundtripTests(unittest.TestCase):
    def test_decoder_stride_fallback_preserves_visible_planes_and_timing(self):
        import av,subprocess,tempfile
        from pathlib import Path
        from ariadne_mark.video.color import ColorConverter,ColorPolicy
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            for width,height in [(854,480),(1366,768)]:
                with self.subTest(width=width):
                    source=Path(folder)/'full.mp4'
                    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'testsrc2=size={width}x{height}:rate=24',
                        '-frames:v','1','-c:v','libx264','-threads','2','-pix_fmt','yuvj420p','-color_range','pc',str(source)],
                        check=True,capture_output=True)
                    with av.open(str(source)) as container:frame=next(container.decode(video=0))
                    convert=ColorConverter(ColorPolicy.from_frame(frame))
                    with patch.object(convert,'image',side_effect=AssertionError('RGB bypass')):
                        output=convert.encoder_frame(frame)
                    self.assertNotEqual(frame.planes[0].line_size,output.planes[0].line_size)
                    self.assertEqual((frame.pts,frame.time_base),(output.pts,output.time_base))
                    for before,after in zip(frame.planes,output.planes):
                        for row in range(before.height):
                            self.assertEqual(bytes(before)[row*before.line_size:row*before.line_size+before.width],
                                bytes(after)[row*after.line_size:row*after.line_size+after.width])

    def test_full_range_420_bypass_copies_code_values_without_rgb_or_models(self):
        import av
        from fractions import Fraction
        from unittest.mock import patch
        from ariadne_mark.video.color import ColorConverter,ColorPolicy
        frame=av.VideoFrame(510,318,'yuvj420p')
        frame.colorspace,frame.color_range=1,2
        frame.pts,frame.time_base=42,Fraction(1,24)
        for plane in frame.planes:
            data=bytearray(plane.buffer_size)
            for y in range(plane.height):
                data[y*plane.line_size:y*plane.line_size+plane.width]=bytes((x+y)%256 for x in range(plane.width))
            plane.update(data)
        convert=ColorConverter(ColorPolicy(1,2))
        with patch.object(convert,'image',side_effect=AssertionError('RGB bypass')),patch.object(convert,'frame',side_effect=AssertionError('RGB bypass')):
            output=convert.encoder_frame(frame)
        self.assertEqual(output.format.name,'yuv420p')
        self.assertEqual((output.pts,output.time_base,output.color_range,output.colorspace),(42,Fraction(1,24),2,1))
        for before,after in zip(frame.planes,output.planes):
            for row in range(before.height):
                self.assertEqual(bytes(before)[row*before.line_size:row*before.line_size+before.width],
                                 bytes(after)[row*after.line_size:row*after.line_size+after.width])

    def test_economy_full_range_preserves_contrast_on_all_bypass_frames(self):
        import av,numpy as np,subprocess,tempfile
        from pathlib import Path
        from ariadne_mark.video import encode_video
        class Identity:
            batch_size=1
            def encode_frames(self,images,token):return images
        width,height=512,320
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for matrix,name in [(1,'bt709'),(6,'smpte170m')]:
                for rng,range_name,levels in [(1,'tv',[16,64,192,235]),(2,'pc',[0,64,192,255])]:
                    y=np.tile(np.repeat(np.asarray(levels,dtype='uint8'),width//4),(height,1))
                    raw=y.tobytes()+bytes([128])*(width*height//2)
                    source=root/'source.mp4'
                    subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','yuv420p','-s',f'{width}x{height}',
                        '-r','24','-i','pipe:0','-c:v','libx264','-threads','2','-crf','0','-colorspace',name,'-color_range',range_name,str(source)],
                        input=raw*72,capture_output=True,check=True)
                    with av.open(str(source)) as c:reference=next(c.decode(video=0)).to_ndarray()[:height,:width].astype(float)
                    for profile in ['economy_5s','economy_2s']:
                        with self.subTest(matrix=matrix,range=rng,profile=profile):
                            marker=Identity();marker.profile=profile
                            output=root/'export.mp4';receipt=encode_video(source,output,marker,'014d123456789abc')
                            self.assertEqual(receipt['color_pipeline']['version'],2)
                            count=0
                            with av.open(str(output)) as c:
                                self.assertEqual((c.streams.video[0].codec_context.colorspace,c.streams.video[0].codec_context.color_range),(matrix,rng))
                                for frame in c.decode(video=0):
                                    actual=frame.to_ndarray()[:height,:width].astype(float)
                                    # Mean-only checks miss full->limited around Y=113.
                                    self.assertLess(float(abs(actual-reference).mean()),1.5)
                                    slope=float(((actual-actual.mean())*(reference-reference.mean())).sum()/((reference-reference.mean())**2).sum())
                                    self.assertTrue(.98<slope<1.02,slope)
                                    count+=1
                            self.assertEqual(count,72)

    def test_probe_rejects_twelve_and_sixteen_bit_sdr(self):
        import json
        from types import SimpleNamespace
        from pathlib import Path
        from unittest.mock import patch
        from ariadne_mark.video import probe
        from ariadne_mark.errors import UnsupportedMedia
        import av
        from ariadne_mark.video.color import ColorPolicy
        decoded=av.VideoFrame(512,320,'yuv420p12le');decoded.colorspace,decoded.color_range=1,1
        with self.assertRaisesRegex(UnsupportedMedia,'8-bit'):ColorPolicy.from_frame(decoded)
        for fmt in ['yuv420p10le','yuv420p12le','yuv444p16le']:
            data={'streams':[{'codec_type':'video','codec_name':'hevc','width':512,'height':320,'pix_fmt':fmt}],
                  'format':{'duration':'1'}}
            with self.subTest(fmt=fmt),patch('ariadne_mark.video.subprocess.run',return_value=SimpleNamespace(stdout=json.dumps(data))):
                with self.assertRaisesRegex(UnsupportedMedia,'high-bit-depth'):probe(Path('test.mp4'))

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
