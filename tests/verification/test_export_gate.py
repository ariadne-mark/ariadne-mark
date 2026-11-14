"""SDK.mark export gate after the B06 result changes (stubbed media only).

The public verifier now reports several IDs as multiple_ids instead of invalid.
These tests pin that the export read-back gate still refuses every such case,
never publishes on failure, and keeps the Economy known-window and
Resilient/legacy sample rules. Real media read-back stays on the server plan.
"""
import shutil
import tempfile
import types
import unittest
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from ariadne_mark.errors import VerificationFailed
from ariadne_mark.pipeline import SDK
from ariadne_mark.provenance import MediaKind
from ariadne_mark.signing import SigningIdentity
from ariadne_mark.videoq import VideoWatermarker
from tests.provenance.test_records import example_record

T = '014d000000000001'
U = '014d0000000000ff'


class Image:
    def getbands(self): return ('R', 'G', 'B')
    def save(self, path, *args, **kwargs): Path(path).write_bytes(b'content')


class Marker:
    def encode(self, image, token): return image


class ExportGateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def checked(self, record, *, watermark, c2pa_token=T):
        return {'c2pa': {'status': 'verified_claim', 'token': c2pa_token, 'record': record.to_dict()},
                'watermark': watermark}

    def mark(self, kind, checked=None, *, profile='economy_5s', windows=(0,), chain=None):
        record = example_record(media_kind=MediaKind.VIDEO if kind == 'video' else MediaKind.IMAGE)
        suffix = '.mp4' if kind == 'video' else '.png'
        source, output = self.path / ('in' + suffix), self.path / ('out' + suffix)
        source.write_bytes(b'source')
        sdk = SDK(Marker(), SigningIdentity(Path('c'), Path('k'), True), None,
                  video_marker=VideoWatermarker(profile=profile))
        with ExitStack() as stack:
            stack.enter_context(patch.object(SDK, 'check_runtime'))
            stack.enter_context(patch('ariadne_mark.pipeline.inspect_c2pa', return_value={'status': 'not_found'}))
            stack.enter_context(patch('ariadne_mark.pipeline.open_image', return_value=Image()))
            stack.enter_context(patch('ariadne_mark.pipeline.new_token', return_value=T))
            stack.enter_context(patch('ariadne_mark.pipeline.sign_file', side_effect=lambda a, b, *x, **k: shutil.copyfile(a, b)))
            stack.enter_context(patch('ariadne_mark.video.probe', return_value={'audio': False}))
            stack.enter_context(patch('ariadne_mark.video.encode_video', side_effect=lambda s, d, *a, **k: (
                Path(d).write_bytes(b'marked'), {'audio': 'none', 'watermark_windows': [{'index': i} for i in windows]})[1]))
            if kind == 'image':
                stack.enter_context(patch.object(SDK, 'verify', return_value=checked(record) if callable(checked) else checked))
            elif chain is None:
                stack.enter_context(patch('ariadne_mark.verification.media.verify_video_export',
                                          return_value=checked(record) if callable(checked) else checked))
            else:
                chain(stack, record)
            try:
                receipt = sdk.mark(source, output, record, audio_kind='none')
            finally:
                sdk.close()
        return receipt, output

    def assert_refused(self, kind, checked, **options):
        with self.assertRaisesRegex(VerificationFailed, 'Final read-back failed'):
            self.mark(kind, checked, **options)
        suffix = '.mp4' if kind == 'video' else '.png'
        self.assertFalse((self.path / ('out' + suffix)).exists())
        self.assertFalse((self.path / ('out' + suffix + '.receipt.json')).exists())

    def economy(self, status, samples, *, all_windows=True, token=T):
        def build(record):
            watermark = {'status': status, 'samples': samples, 'export_window_readback': {'all_windows_have_id': all_windows}}
            if token:
                watermark['token'] = token
            return self.checked(record, watermark=watermark)
        return build

    def test_economy_known_window_pass_publishes(self):
        receipt, output = self.mark('video', self.economy('recovered_claim', [{'token': T}, {'token': None}]))
        self.assertTrue(output.exists())
        self.assertEqual(receipt['token'], T)

    def test_multiple_ids_never_publish(self):
        self.assert_refused('video', self.economy('multiple_ids', [{'token': T}, {'token': U}], token=None))
        self.assert_refused('image', lambda r: self.checked(r, watermark={'status': 'multiple_ids', 'samples': [{'token': T}, {'token': U}]}))

    def test_conflicting_sample_or_missing_window_refuses(self):
        self.assert_refused('video', self.economy('recovered_claim', [{'token': T}, {'token': U}]))
        self.assert_refused('video', self.economy('recovered_claim', [{'token': T}], all_windows=False))

    def test_single_observation_and_signed_id_mismatch_refuse(self):
        self.assert_refused('video', self.economy('single_observation', [{'token': T}], token=None))
        self.assert_refused('image', lambda r: self.checked(r, watermark={'status': 'recovered_claim', 'token': T,
                                                                       'samples': [{'token': T}]}, c2pa_token=U))

    def test_resilient_requires_every_returned_sample_but_not_five(self):
        def sample(tokens):
            return lambda r: self.checked(r, watermark={'status': 'recovered_claim', 'token': T,
                                                        'samples': [{'token': t} for t in tokens]})
        self.assert_refused('video', sample([T, T, None]), profile='resilient')
        receipt, output = self.mark('video', sample([T, T, T]), profile='resilient')
        self.assertTrue(output.exists())

    def real_readback(self, decoded):
        """Run the real verify_video_export on recorded window decodes."""
        def install(stack, record):
            frames = [(types.SimpleNamespace(pts=i, time_base=Fraction(1, 24)), i / 24, i, 0) for i in range(len(decoded))]
            stack.enter_context(patch('ariadne_mark.video.selected_window_frames', return_value=frames))
            stack.enter_context(patch('ariadne_mark.video.color.frame_image', return_value=object()))
            stack.enter_context(patch('ariadne_mark.verification.media.inspect_c2pa',
                                      return_value={'status': 'verified_claim', 'issuer_trust': 'untrusted',
                                                    'token': T, 'record': record.to_dict()}))
            calls = iter(decoded)
            stack.enter_context(patch.object(VideoWatermarker, 'decode_frames',
                                             side_effect=lambda frames: ([{'time': frames[0][1], 'token': next(calls)}], None)))
        return install

    def test_real_window_readback_with_two_ids_is_refused(self):
        # Each window holds *an* ID, but not the same one: multiple_ids.
        self.assert_refused('video', None, windows=(0, 1), chain=self.real_readback([T, U]))

    def test_real_one_window_readback_still_publishes(self):
        receipt, output = self.mark('video', None, windows=(0,), chain=self.real_readback([T]))
        self.assertTrue(output.exists())
        watermark = receipt['verification']['watermark']
        self.assertEqual(watermark['ids'][0]['reclassified']['basis'], 'known_schedule_export_readback')
        self.assertEqual(watermark['samples'][0]['frame'], {'stream': 0, 'pts': 0, 'time_base': '1/24'})
