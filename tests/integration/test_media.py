"""Real engines, real signed media. Enable with ARIADNE_MEDIA_TESTS=1."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("ARIADNE_MEDIA_TESTS") == "1", "requires media extra and provisioned models")
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ariadne_mark.watermark import Watermarker
        from ariadne_mark.signing import create_development_identity, SigningIdentity
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        create_development_identity(cls.root / "identity")
        cls.identity = SigningIdentity.from_directory(cls.root / "identity", allow_dev=True)
        cls.marker = Watermarker()
        from ariadne_mark.videoseal import VideoSealWatermarker
        cls.video_marker = VideoSealWatermarker()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        from ariadne_mark.registry import Registry
        from ariadne_mark.pipeline import SDK
        self.directory = tempfile.TemporaryDirectory(dir=self.root)
        self.path = Path(self.directory.name)
        self.sdk = SDK(self.marker, self.identity, Registry(self.path / "registry.sqlite3"), video_marker=self.video_marker)

    def tearDown(self):
        self.directory.cleanup()

    def record(self, media="image", action="created"):
        from ariadne_mark.provenance import ProvenanceRecord, GenerativeSystem, MediaKind, Action
        return ProvenanceRecord.create(publisher="Test Publisher", system=GenerativeSystem("Fixture", "1"),
            media_kind=MediaKind(media), action=Action(action), created_at=datetime.now(timezone.utc))

    def image(self, name="input.png", *, alpha=False):
        from PIL import Image, ImageDraw
        image = Image.new("RGBA" if alpha else "RGB", (640, 512), "#24536a")
        drawing = ImageDraw.Draw(image)
        drawing.ellipse((20, 40, 400, 440), fill="#eac270")
        drawing.rectangle((300, 280, 600, 480), fill="#bc5577")
        if alpha:
            image.putalpha(180)
        path = self.path / name
        image.save(path)
        return path

    def ffmpeg(self, *args):
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *map(str, args)], check=True, capture_output=True, timeout=60)

    def video(self, *, vertical=False, audio=True, vfr=False, pattern="texture"):
        path = self.path / "input.mp4"
        size = "320x512" if vertical else "512x320"
        if pattern == "testsrc":
            args = ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate=12:duration=2"]
        else:
            # Reproducible unsaturated texture. The old saturated color-bar fixture
            # is deliberately retained below as a fail-closed edge case.
            import numpy as np
            from PIL import Image
            width, height = map(int, size.split("x"))
            rng = np.random.default_rng(42)
            pixels = np.zeros((height, width, 3), dtype=np.float32)
            for side, amplitude in ((4, 35), (16, 30), (64, 20), (256, 10)):
                noise = Image.fromarray(rng.integers(0, 256, (side, side, 3), dtype=np.uint8))
                pixels += (np.asarray(noise.resize((width, height), Image.Resampling.BICUBIC), dtype=np.float32) - 128) * amplitude / 128
            fixture = self.path / "texture.png"
            Image.fromarray(np.clip(128 + pixels, 0, 255).astype("uint8")).save(fixture)
            args = ["-loop", "1", "-framerate", "12", "-i", str(fixture)]
        if audio:
            args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
        if vfr:
            args += ["-vf", "select='if(lt(n,12),1,not(mod(n,2)))'", "-fps_mode", "vfr"]
        args += ["-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio:
            args += ["-c:a", "aac"]
        self.ffmpeg(*args, path)
        return path

    def product_profile(self):
        from ariadne_mark.profiles import template
        config = template()
        config.update(publisher="Test Publisher", system={"name": "Fixture", "version": "1"}, role="provider")
        config["sdk"]["audio_kind"] = "none"
        config["deployment"]["disclosure"] = "baked_in"
        return config

    def test_profile_cli_signed_image_and_receipt_persistence(self):
        from contextlib import redirect_stdout
        from ariadne_mark.cli import main
        import io
        source, output = self.image(), self.path / "profile.png"
        config_path = self.path / "product.json"
        config_path.write_text(json.dumps(self.product_profile()))
        with redirect_stdout(io.StringIO()) as stdout:
            code = main(["mark", str(source), str(output), "--profile", str(config_path),
                "--created-at", "2026-11-03T00:00:00Z", "--identity", str(self.root / "identity"),
                "--allow-dev", "--registry", str(self.sdk.registry.path)])
        self.assertEqual(code, 0)
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt, json.loads(output.with_name(output.name + ".receipt.json").read_text()))
        with self.sdk.registry.connect() as db:
            stored = json.loads(db.execute("SELECT receipt FROM assets WHERE token=?", (receipt["token"],)).fetchone()[0])
        self.assertEqual(receipt, stored)
        self.assertEqual(receipt["verification"]["c2pa"]["status"], "verified_claim")
        self.assertTrue(receipt["profile_assessment"]["sdk_options"]["visible"])
        self.assertTrue(receipt["verification"]["c2pa"]["visible_disclosure"])
        self.assertTrue(receipt["export_settings"]["visible_disclosure"])
        self.assertEqual(receipt["profile_assessment"]["legal_determination"], "not_performed")
        self.assertEqual(receipt["verification"]["c2pa"]["record"]["publisher"], "Test Publisher")

    def test_profile_video_roundtrip(self):
        output = self.path / "profile.mp4"
        receipt = self.sdk.mark(self.video(audio=False), output, self.record("video"), profile=self.product_profile())
        self.assertEqual(receipt["audio_kind"], "none")
        self.assertEqual(self.sdk.verify(output)["watermark"]["token"], receipt["token"])
        self.assertEqual(receipt["profile_assessment"]["configuration_status"], "valid")

    def test_profile_mismatch_fails_before_publication(self):
        output = self.path / "conflict.png"
        config = self.product_profile(); config["publisher"] = "Wrong Publisher"
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.sdk.mark(self.image(), output, self.record(), profile=config)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + ".receipt.json").exists())
        with self.sdk.registry.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM assets").fetchone()[0], 0)

    def test_png_jpeg_alpha_signed_roundtrip_and_trust(self):
        from PIL import Image
        from ariadne_mark.verification.media import verify_file
        for ext, alpha in (("png", False), ("jpg", False), ("png", True)):
            with self.subTest(ext=ext, alpha=alpha):
                source = self.image(f"in-{ext}-{alpha}.png", alpha=alpha)
                output = self.path / f"out-{ext}-{alpha}.{ext}"
                receipt = self.sdk.mark(source, output, self.record(), visible=True)
                report = self.sdk.verify(output)
                self.assertEqual(report["c2pa"]["status"], "verified_claim")
                self.assertEqual(report["c2pa"]["issuer_trust"], "untrusted")
                self.assertEqual(report["watermark"]["token"], receipt["token"])
                self.assertEqual(report["recovery"]["status"], "found")
                trusted = verify_file(output, trust_anchors=self.root / "identity/trust.pem")
                self.assertEqual(trusted["c2pa"]["issuer_trust"], "trusted")
                if alpha:
                    with Image.open(output) as image:
                        self.assertEqual(image.getchannel("A").getextrema(), (180, 255))

    def test_metadata_loss_recovers_record_without_claiming_signature(self):
        from PIL import Image
        output = self.path / "marked.png"
        receipt = self.sdk.mark(self.image(), output, self.record())
        stripped = self.path / "stripped.jpg"
        with Image.open(output) as image:
            image.convert("RGB").save(stripped, quality=75)
        report = self.sdk.verify(stripped)
        self.assertEqual(report["c2pa"]["status"], "not_found")
        self.assertEqual(report["watermark"]["token"], receipt["token"])
        self.assertEqual(report["recovery"]["status"], "found")

    def test_parent_manifest_is_preserved(self):
        first, second = self.path / "first.png", self.path / "second.png"
        self.sdk.mark(self.image(), first, self.record())
        self.sdk.mark(first, second, self.record(action="altered"))
        self.assertGreaterEqual(self.sdk.verify(second)["c2pa"]["ingredient_count"], 1)

    def test_signature_tampering_is_invalid(self):
        import struct, zlib
        output = self.path / "marked.png"
        self.sdk.mark(self.image(), output, self.record())
        data = bytearray(output.read_bytes())
        offset = 8
        while offset < len(data):
            size = struct.unpack(">I", data[offset:offset+4])[0]
            if data[offset+4:offset+8] == b"caBX":
                where = data.find(b"Test Publisher", offset, offset + 8 + size)
                self.assertNotEqual(where, -1)
                data[where] = ord("B")
                crc = zlib.crc32(data[offset+4:offset+8+size])
                data[offset+8+size:offset+12+size] = struct.pack(">I", crc)
                break
            offset += 12 + size
        else:
            self.fail("No C2PA PNG chunk found")
        corrupt = self.path / "tampered.png"
        corrupt.write_bytes(data)
        self.assertEqual(self.sdk.verify(corrupt)["c2pa"]["status"], "invalid")

    def test_failed_watermark_publishes_nothing(self):
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.errors import VerificationFailed
        class BrokenMarker:
            def encode(self, image, token): return image
            def decode(self, image): return None
        output = self.path / "failed.png"
        with self.assertRaises(VerificationFailed):
            SDK(BrokenMarker(), self.identity).mark(self.image(), output, self.record())
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + ".receipt.json").exists())

    def test_video_roundtrip_audio_timestamps_and_rotation(self):
        import av
        from ariadne_mark.video import probe
        for scenario in ("cfr", "vfr", "vertical", "rotation"):
            with self.subTest(scenario=scenario):
                source = self.video(vertical=scenario == "vertical", vfr=scenario == "vfr")
                if scenario == "rotation":
                    rotated = self.path / "rotated.mp4"
                    self.ffmpeg("-display_rotation", "90", "-i", source, "-c", "copy", rotated)
                    source = rotated
                    self.assertEqual(probe(source)["rotation"], 90)
                output = self.path / f"{scenario}.mp4"
                receipt = self.sdk.mark(source, output, self.record("video"), audio_kind="original")
                with av.open(str(source)) as a, av.open(str(output)) as b:
                    source_frames = [(float(f.pts * f.time_base), float(f.duration * f.time_base)) for f in a.decode(video=0)]
                    output_frames = [(float(f.pts * f.time_base), float(f.duration * f.time_base)) for f in b.decode(video=0)]
                    source_times = [row[0] for row in source_frames]
                    output_times = [row[0] for row in output_frames]
                self.assertEqual(len(source_times), len(output_times))
                for x, y in zip(source_times, output_times):
                    self.assertAlmostEqual(x, y, places=3)
                self.assertAlmostEqual(max(t + d for t, d in source_frames),
                                       max(t + d for t, d in output_frames), places=3)
                self.assertTrue(probe(output)["audio"])
                # Compare compressed AAC payloads, not only presence of an audio stream.
                def audio_packets(path):
                    with av.open(str(path)) as clip:
                        return [(p.pts, p.dts, bytes(p)) for p in clip.demux(audio=0) if p.size]
                self.assertEqual(audio_packets(source), audio_packets(output))
                self.assertEqual(receipt["verification"]["c2pa"]["status"], "verified_claim")
                if scenario == "rotation":
                    self.assertEqual((probe(output)["width"], probe(output)["height"]), (320, 512))
                    self.assertEqual(probe(output)["rotation"], 0)

    def test_video_recompression_recovery(self):
        source = self.video(audio=False)
        marked, compressed = self.path / "marked.mp4", self.path / "compressed.mp4"
        receipt = self.sdk.mark(source, marked, self.record("video"))
        self.ffmpeg("-i", marked, "-c:v", "libx264", "-crf", "28", "-map_metadata", "-1", compressed)
        result = self.sdk.verify(compressed)
        self.assertEqual(result["c2pa"]["status"], "not_found")
        self.assertEqual(result["watermark"]["token"], receipt["token"])

    def test_legacy_video_and_new_engine_metadata_dispatch(self):
        from ariadne_mark.pipeline import SDK
        from unittest.mock import patch
        old = SDK(self.marker, self.identity, video_marker=self.marker)
        output = self.path / "legacy.mp4"
        receipt = old.mark(self.video(audio=False), output, self.record("video"))
        with patch.object(self.video_marker, "decode_frames", side_effect=AssertionError("Wrong dispatch")):
            report = self.sdk.verify(output)
        self.assertEqual(report["watermark"]["token"], receipt["token"])
        stripped = self.path / "legacy-stripped.mp4"
        self.ffmpeg("-i", output, "-c:v", "libx264", "-crf", "28", "-map_metadata", "-1", stripped)
        self.assertEqual(self.sdk.verify(stripped)["watermark"]["token"], receipt["token"])

    def test_videoseal_tail_batch_negative_and_fail_closed(self):
        from ariadne_mark.errors import VerificationFailed
        from unittest.mock import patch
        source = self.video(audio=False, vfr=True)  # 18 frames: final batch has two.
        self.assertEqual(self.sdk.verify(source)["watermark"]["status"], "not_found")
        output = self.path / "tail.mp4"
        receipt = self.sdk.mark(source, output, self.record("video"))
        self.assertEqual(receipt["video"]["frames_encoded"], 18)
        self.assertEqual(receipt["video"]["batch_size"], 4)
        self.assertEqual(receipt["verification"]["c2pa"]["watermark_algorithm"], "meta.videoseal.1.0.bch20")
        with patch.object(self.video_marker, "decode_frames", return_value=([{"time": 0, "token": None}], None)):
            failed = self.path / "failed-video.mp4"
            with self.assertRaises(VerificationFailed):
                self.sdk.mark(source, failed, self.record("video"))
            self.assertFalse(failed.exists())
            self.assertFalse(failed.with_name(failed.name + ".receipt.json").exists())

    def test_saturated_test_pattern_is_not_silently_published(self):
        from ariadne_mark.errors import VerificationFailed
        from unittest.mock import patch
        output = self.path / "saturated.mp4"
        # Known difficult content: default VideoSeal cannot survive H.264 here.
        with patch("ariadne_mark.pipeline.new_token", return_value="014d123456789abc"):
            with self.assertRaises(VerificationFailed):
                self.sdk.mark(self.video(audio=False, pattern="testsrc"), output, self.record("video"))
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + ".receipt.json").exists())

    def test_explicit_development_opt_in(self):
        from ariadne_mark.signing import SigningIdentity
        from ariadne_mark.errors import AriadneError
        with self.assertRaises(AriadneError):
            SigningIdentity.from_directory(self.root / "identity")

    def test_public_api_runs_real_verification(self):
        import http.client, threading
        from ariadne_mark.server import make_server
        marked = self.path / "api.png"
        receipt = self.sdk.mark(self.image(), marked, self.record())
        server = make_server(self.sdk, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(*server.server_address, timeout=30)
            connection.request("POST", "/verify?format=png", body=marked.read_bytes())
            response = connection.getresponse()
            report = json.loads(response.read())
            connection.close()
            self.assertEqual(response.status, 200)
            self.assertEqual(report["c2pa"]["status"], "verified_claim")
            self.assertEqual(report["watermark"]["token"], receipt["token"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_registry_error_removes_export_and_receipt(self):
        from ariadne_mark.pipeline import SDK
        class FailedRegistry:
            def contains(self, token): return False
            def get(self, token): return None
            def add(self, *args): raise OSError("registry unavailable")
        output = self.path / "db-error.png"
        with self.assertRaises(OSError):
            SDK(self.marker, self.identity, FailedRegistry()).mark(self.image(), output, self.record())
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + ".receipt.json").exists())

    def test_cli_mark_verify_and_refuse_overwrite(self):
        import sys
        source, output = self.image(), self.path / "cli.png"
        command = [sys.executable, "-m", "ariadne_mark.cli", "mark", str(source), str(output),
                   "--publisher", "CLI fixture", "--system", "Fixture", "--system-version", "1",
                   "--created-at", "2026-11-03T10:00:00Z", "--identity", str(self.root / "identity"), "--allow-dev"]
        marked = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(marked.returncode, 0, marked.stderr)
        receipt = json.loads(marked.stdout)
        checked = subprocess.run([sys.executable, "-m", "ariadne_mark.cli", "verify", str(output)], capture_output=True, text=True, timeout=60)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["watermark"]["token"], receipt["token"])
        original = output.read_bytes()
        again = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
