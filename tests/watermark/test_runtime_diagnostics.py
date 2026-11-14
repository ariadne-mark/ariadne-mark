"""B14: bounded worker diagnostics and a named setup for video-only installs."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ariadne_mark.errors import AriadneError, MissingModel

NOISY_WORKER = r'''
import sys
sys.stderr.write("x" * 100000)
sys.stderr.write("\nFINAL-CAUSE model file unreadable\n")
sys.stderr.flush()
sys.exit(3)
'''


class WorkerDiagnosticsTests(unittest.TestCase):
    def test_worker_stderr_tail_is_bounded_and_kept_out_of_the_message(self):
        from ariadne_mark import videoq
        real = subprocess.Popen
        launched = []

        def popen(command, **kwargs):
            launched.append(kwargs)
            return real([sys.executable, '-c', NOISY_WORKER], **kwargs)
        marker = videoq.VideoWatermarker(timeout=30)
        with patch.object(videoq, 'check_models'), patch.object(videoq.subprocess, 'Popen', side_effect=popen):
            with self.assertRaises(AriadneError) as caught:
                marker._load()  # waits for the worker's ready frame
        self.assertEqual(launched[0]['stderr'], subprocess.PIPE)
        self.assertLessEqual(len(marker.last_error.encode()), videoq.STDERR_TAIL)
        self.assertTrue(marker.last_error.endswith('FINAL-CAUSE model file unreadable'))
        self.assertNotIn('FINAL-CAUSE', str(caught.exception))  # never echoed to callers/public output
        self.assertIsInstance(caught.exception.__cause__, EOFError)  # original cause retained
        self.assertIsNone(marker._process)  # recoverable: next request starts a fresh worker


class VideoOnlyInstallTests(unittest.TestCase):
    def test_image_call_without_torch_names_the_media_setup(self):
        from ariadne_mark.watermark import LazyWatermarker, Watermarker
        with patch.dict('sys.modules', {'torch': None}):
            with self.assertRaisesRegex(MissingModel, 'ariadne setup media'):
                Watermarker()
            with self.assertRaisesRegex(MissingModel, 'video-only'):
                LazyWatermarker().decode(object())

    def test_image_verification_reports_unavailable_engine_not_a_raw_import_error(self):
        from ariadne_mark.verification.media import verify_file
        from ariadne_mark.watermark import LazyWatermarker
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'plain.png'
            path.write_bytes(b'x')
            with patch.dict('sys.modules', {'torch': None}), \
                 patch('ariadne_mark.verification.media.open_image', return_value=object()), \
                 patch('ariadne_mark.verification.media.inspect_c2pa', return_value={'status': 'not_found'}):
                report = verify_file(path, marker=LazyWatermarker())
        watermark = report['watermark']
        self.assertEqual(watermark['status'], 'not_checked')
        self.assertEqual(watermark['unavailable_engines'], [{'algorithm': 'adobe.trustmark.Q.bch5', 'reason': 'MissingModel'}])
        self.assertEqual(report['label'], 'Check incomplete')
