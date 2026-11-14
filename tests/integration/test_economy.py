"""Real CPU encoder, C2PA and failure gates for selectable Economy presets."""
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import test_media as fixtures


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS') == '1', 'requires provisioned video runtime')
class EconomyIntegrationTests(unittest.TestCase):
    video = fixtures.MediaTests.video
    ffmpeg = fixtures.MediaTests.ffmpeg
    record = fixtures.MediaTests.record
    product_profile = fixtures.MediaTests.product_profile

    def setUp(self):
        from ariadne_mark.signing import create_development_identity, SigningIdentity
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        create_development_identity(self.path / 'id')
        self.identity = SigningIdentity.from_directory(self.path / 'id', allow_dev=True)
        self.sdk = SDK(identity=self.identity, registry=Registry(self.path / 'registry.sqlite'))

    def tearDown(self):
        self.sdk.close()
        self.temp.cleanup()

    def long_video(self, *, vfr=False, audio=True):
        source = self.video(audio=audio, vfr=vfr)
        target = self.path / 'six-seconds.mp4'
        self.ffmpeg('-stream_loop', '2', '-i', source, '-t', '6', '-c', 'copy', target)
        return target

    def test_same_sdk_default_config_and_explicit_resilient_preserve_audio_timing_and_ids(self):
        import av
        source = self.long_video()
        def packets(path):
            with av.open(str(path)) as c:
                return [(p.pts, p.dts, bytes(p)) for p in c.demux(audio=0) if p.size]
        def times(path):
            with av.open(str(path)) as c:
                return [float(f.pts * f.time_base) for f in c.decode(video=0)]
        receipts = []
        for mode in ['economy_5s', 'economy_2s', 'resilient']:
            with self.subTest(mode=mode):
                options = {'audio_kind': 'original'}
                if mode == 'economy_2s':
                    config = self.product_profile()
                    config['sdk'].update(audio_kind='original', video_profile=mode)
                    config['deployment']['disclosure'] = 'none'
                    options = {'profile': config}
                elif mode == 'resilient':
                    options['video_profile'] = mode
                output = self.path / (mode + '.mp4')
                receipt = self.sdk.mark(source, output, self.record('video'), **options)
                receipts.append(receipt)
                self.assertEqual(receipt['video']['profile'], mode)
                self.assertEqual(receipt['verification']['c2pa']['watermark_profile'],
                                 self.sdk._select_video_marker(mode).profile_id)
                self.assertEqual(packets(source), packets(output))
                for a, b in zip(times(source), times(output)):
                    self.assertAlmostEqual(a, b, places=3)
                self.assertEqual(len(times(source)), len(times(output)))
                if mode.startswith('economy'):
                    gate = receipt['verification']['watermark']['export_window_readback']
                    self.assertTrue(gate['all_windows_have_id'])
                    self.assertEqual(len(gate['expected_windows']), 2 if mode == 'economy_5s' else 3)
                    self.assertLess(receipt['video']['marked_frames'], receipt['video']['frames_encoded'])
                else:
                    self.assertEqual(receipt['video']['marked_frames'], receipt['video']['frames_encoded'])
                self.assertEqual(self.sdk.verify(output)['watermark']['token'], receipt['token'])
        self.assertEqual(len({r['token'] for r in receipts}), 3)

    def test_missing_later_window_is_not_published(self):
        from ariadne_mark.errors import VerificationFailed
        source = self.long_video(audio=False)
        marker = self.sdk.video_marker
        original = marker.encode_frames
        calls = 0
        def stop_after_first_window(images, token):
            nonlocal calls
            calls += len(images)
            return original(images, token) if calls <= 2 else images
        marker.encode_frames = stop_after_first_window
        target = self.path / 'partial.mp4'
        with self.assertRaises(VerificationFailed):
            self.sdk.mark(source, target, self.record('video'))
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + '.receipt.json').exists())
        with self.sdk.registry.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM assets').fetchone()[0], 0)

    def test_configured_worker_is_reused_for_verification(self):
        source = self.video(audio=False)
        config = self.product_profile()
        config['sdk']['video_profile'] = 'economy_2s'
        config['deployment']['disclosure'] = 'none'
        output = self.path / 'config-worker.mp4'
        receipt = self.sdk.mark(source, output, self.record('video'), profile=config)
        worker = self.sdk._video_markers['economy_2s']._process
        self.assertIsNotNone(worker)
        # ISS-12: presets share one worker, so no second (default) worker exists.
        self.assertIs(self.sdk.video_marker._process, worker)
        self.assertEqual(self.sdk.verify(output)['watermark']['token'], receipt['token'])
        self.assertIs(self.sdk.video_marker._process, worker)  # verification reused the same process

    def test_worker_death_after_last_selected_frame_fails_before_publication(self):
        from ariadne_mark.errors import AriadneError
        source = self.long_video(audio=False)
        marker = self.sdk.video_marker
        original = marker.encode_frames
        calls = 0
        def die_after_four(images, token):
            nonlocal calls
            result = original(images, token)
            calls += len(images)
            if calls == 4:
                marker._process.kill()
            return result
        marker.encode_frames = die_after_four
        target = self.path / 'dead-worker.mp4'
        with self.assertRaises(AriadneError):
            self.sdk.mark(source, target, self.record('video'))
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + '.receipt.json').exists())

    def test_concurrent_per_export_profiles_do_not_mutate_the_default(self):
        source = self.video(audio=False)
        def export(mode):
            return self.sdk.mark(source, self.path / (mode + '.mp4'), self.record('video'), video_profile=mode)
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(export, ['economy_5s', 'economy_2s']))
        self.assertEqual(self.sdk.video_marker.profile, 'economy_5s')
        self.assertNotEqual(receipts[0]['token'], receipts[1]['token'])
        for mode, receipt in zip(['economy_5s', 'economy_2s'], receipts):
            self.assertEqual(receipt['video']['profile'], mode)
            self.assertEqual(self.sdk.verify(self.path / (mode + '.mp4'))['watermark']['token'], receipt['token'])

    def test_vfr_rotation_and_full_frame_disclosure_in_economy(self):
        import av
        from ariadne_mark.video import probe
        source = self.video(audio=True, vfr=True)
        rotated = self.path / 'rotated.mp4'
        self.ffmpeg('-display_rotation', '90', '-i', source, '-c', 'copy', rotated)
        output = self.path / 'oriented.mp4'
        receipt = self.sdk.mark(rotated, output, self.record('video'), visible=True, audio_kind='original',
                                video_profile='economy_2s')
        self.assertEqual(probe(output)['rotation'], 0)
        self.assertEqual((probe(output)['width'], probe(output)['height']), (320, 512))
        self.assertTrue(receipt['verification']['c2pa']['visible_disclosure'])
        with av.open(str(source)) as c:
            before = [float(f.pts * f.time_base) for f in c.decode(video=0)]
        with av.open(str(output)) as c:
            after = [float(f.pts * f.time_base) for f in c.decode(video=0)]
        self.assertEqual(len(before), len(after))
        for a, b in zip(before, after): self.assertAlmostEqual(a, b, places=3)

    def test_explicit_override_conflict_and_typo_publish_nothing(self):
        source = self.video(audio=False)
        config = self.product_profile()
        for mode in ['economy_2s', 'economy_1s', '']:
            target = self.path / (mode + 'bad.mp4')
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.sdk.mark(source, target, self.record('video'), profile=config, video_profile=mode)
            self.assertFalse(target.exists())
