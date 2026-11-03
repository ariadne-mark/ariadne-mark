import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
from ariadne_mark.errors import MissingModel
from ariadne_mark.videoseal import check_models, VideoSealWatermarker
from ariadne_mark.verification.media import summarize_watermarks


class VideoSealPolicyTests(unittest.TestCase):
    def test_missing_and_modified_models_fail_before_deserialization(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.jit"
            with patch.dict(os.environ, {"ARIADNE_VIDEOSEAL_MODEL": str(path)}):
                with self.assertRaises(MissingModel):
                    check_models()
                path.write_bytes(b"not an official model")
                with self.assertRaises(MissingModel):
                    check_models()

    def test_aggregate_cannot_hide_conflicting_frame_id(self):
        rows = [{"token": "014d000000000001"}, {"token": None}]
        report = summarize_watermarks(rows, [{"token": "014d000000000002"}], video=True)
        self.assertEqual(report["status"], "invalid")
        self.assertNotIn("token", report)

    def test_aggregate_recovers_when_individual_frames_do_not(self):
        report = summarize_watermarks([{"token": None}], [{"token": "014d000000000001"}], video=True)
        self.assertEqual(report["status"], "recovered_claim")
        self.assertEqual(report["scope"], "sampled_frames")

    def test_empty_samples_are_not_a_negative_detection(self):
        self.assertEqual(summarize_watermarks([], [], video=True)["status"], "not_checked")

    def test_constructor_is_lazy_and_validates_threads(self):
        self.assertIsNone(VideoSealWatermarker()._engine)
        with self.assertRaises(ValueError):
            VideoSealWatermarker(threads=0)


@unittest.skipUnless(os.environ.get("ARIADNE_MEDIA_TESTS") == "1", "requires pinned TrustMark BCH")
class VideoSealPayloadTests(unittest.TestCase):
    def test_error_correction_integrity_and_negative_packets(self):
        from ariadne_mark.videoseal.payload import Payload
        payload = Payload()
        randomizer = random.Random(41)
        for i in range(20):
            token = f"{(0x14d << 48) | randomizer.getrandbits(48):016x}"
            original = payload.encode(token)
            for errors in range(21):
                bits = original.copy()
                for index in randomizer.sample(range(256), errors):
                    bits[index] ^= 1
                result = payload.decode(bits)
                self.assertEqual(result["token"], token)
                self.assertEqual(result["corrected_bits"], errors)
            bits = original.copy()
            for index in randomizer.sample(range(256), 40):
                bits[index] ^= 1
            self.assertIsNone(payload.decode(bits))
        for _ in range(1000):
            self.assertIsNone(payload.decode([randomizer.randrange(2) for _ in range(256)]))
        with self.assertRaises(ValueError):
            payload.decode([0] * 255)
        with self.assertRaises(ValueError):
            payload.encode("not-a-token")

class VideoRoutingTests(unittest.TestCase):
    def verify(self, claim, video_marker, marker):
        from ariadne_mark.verification.media import verify_file
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.mp4"
            path.touch()
            with patch("ariadne_mark.verification.media.inspect_c2pa", return_value=claim), patch("ariadne_mark.video.sample_frames", return_value=[(object(), 0.0)]):
                return verify_file(path, video_marker=video_marker, marker=marker)

    def test_missing_video_model_is_not_reported_as_absent_mark(self):
        class Missing:
            algorithm = "meta.videoseal.1.0.bch20"
            def decode_frames(self, frames): raise MissingModel("not provisioned")
        class Legacy:
            algorithm = "adobe.trustmark.Q.bch5"
            def decode(self, image): return None
        result = self.verify({"status": "not_found"}, Missing(), Legacy())
        self.assertEqual(result["watermark"]["status"], "not_checked")
        self.assertEqual(result["watermark"]["reason"], "incomplete_engine_coverage")

    def test_signed_videoseal_dispatch_does_not_invoke_legacy_engine(self):
        token = "014d123456789abc"
        class Video:
            algorithm = "meta.videoseal.1.0.bch20"
            def decode_frames(self, frames): return ([{"time": 0, "token": None}], {"token": token})
        class Legacy:
            def decode(self, image): raise AssertionError("unnecessary legacy detector")
        result = self.verify({"status": "verified_claim", "watermark_algorithm": Video.algorithm}, Video(), Legacy())
        self.assertEqual(result["watermark"]["token"], token)
        self.assertEqual(result["watermark"]["engines_checked"], [Video.algorithm])
