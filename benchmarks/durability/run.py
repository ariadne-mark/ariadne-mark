"""Small reproducible CPU smoke benchmark; not a calibrated false-positive study."""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw

from ariadne_mark.pipeline import SDK
from ariadne_mark.provenance import ProvenanceRecord, GenerativeSystem, MediaKind, Action
from ariadne_mark.registry import Registry
from ariadne_mark.signing import SigningIdentity, create_development_identity
from ariadne_mark.watermark import Watermarker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    create_development_identity(root / "identity")
    t = time.monotonic()
    marker = Watermarker()
    cold = time.monotonic() - t
    sdk = SDK(marker, SigningIdentity.from_directory(root / "identity", allow_dev=True), Registry(root / "registry.sqlite3"))
    rng = np.random.default_rng(20261103)
    h, w = 768, 1024
    yy, xx = np.mgrid[:h, :w]
    gradient = np.stack([xx / w * 255, yy / h * 255, (np.sin(xx / 70) + 1) * 110], axis=-1).astype("uint8")
    textured = np.clip(gradient.astype(float) + rng.normal(0, 12, gradient.shape), 0, 255).astype("uint8")
    card = Image.new("RGB", (w, h), "#faf3e3")
    draw = ImageDraw.Draw(card)
    draw.ellipse((100, 100, 700, 700), fill="#ca7355")
    for y in range(80, 600, 50):
        draw.text((100, y), "Ariadne Mark - reproducible synthetic greeting card", fill="#16283a", font_size=24)
    fixtures = {"gradient": Image.fromarray(gradient), "texture": Image.fromarray(textured),
                "card": card, "flat": Image.new("RGB", (w, h), "#397d84")}
    rows, images, negatives, videos = [], [], [], []

    def record(kind):
        return ProvenanceRecord.create(publisher="Ariadne benchmark", system=GenerativeSystem("Procedural fixtures", "1"),
            media_kind=MediaKind(kind), action=Action.CREATED, created_at=datetime.now(timezone.utc))

    for name, image in fixtures.items():
        source, marked = root / (name + ".png"), root / (name + "-marked.png")
        image.save(source)
        negative = sdk.verify(source)
        negatives.append({"fixture": name, "watermark_found": negative["watermark"].get("token") is not None})
        receipt = sdk.mark(source, marked, record("image"))
        with Image.open(marked) as value:
            altered = value.convert("RGB")
        mse = np.mean((np.asarray(image).astype(float) - np.asarray(altered).astype(float)) ** 2)
        images.append({"fixture": name, "seconds": receipt["seconds"], "psnr_db": round(10 * math.log10(255**2 / mse), 2) if mse else None})
        for transform in ("original", "jpeg_q75", "jpeg_q50", "resize_half", "crop_10pct", "crop_25pct"):
            target = marked
            if transform.startswith("jpeg"):
                target = root / (name + "-" + transform + ".jpg")
                altered.save(target, quality=int(transform[-2:]))
            elif transform == "resize_half":
                target = root / (name + "-resize.png")
                altered.resize((w // 2, h // 2), Image.Resampling.LANCZOS).save(target)
            elif transform.startswith("crop"):
                ratio = .10 if transform == "crop_10pct" else .25
                dx, dy = int(w * ratio / 2), int(h * ratio / 2)
                target = root / (name + "-" + transform + ".png")
                altered.crop((dx, dy, w-dx, h-dy)).save(target)
            report = sdk.verify(target)
            recovered = report["watermark"].get("token")
            rows.append({"fixture": name, "transform": transform, "correct_id": recovered == receipt["token"],
                         "wrong_id": recovered is not None and recovered != receipt["token"], "c2pa": report["c2pa"]["status"]})
        print(name, "done", flush=True)

    for size in ("512x320", "720x1280"):
        source, marked = root / f"video-{size}.mp4", root / f"video-{size}-marked.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=12:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)], check=True)
        receipt = sdk.mark(source, marked, record("video"), audio_kind="original")
        compressed = root / f"video-{size}-crf28.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(marked), "-c:v", "libx264", "-crf", "28", "-c:a", "copy", "-map_metadata", "-1", str(compressed)], check=True)
        report = sdk.verify(compressed)
        videos.append({"size": size, "duration": 2, "frames": receipt["video"]["frames_encoded"], "seconds": receipt["seconds"],
                       "crf28_correct_id": report["watermark"].get("token") == receipt["token"], "checked_frames": report["watermark"]["checked_frames"]})
        print(size, "done", flush=True)

    result = {"scope": "4 synthetic images, 24 transformation checks, 4 negative controls, two 2-second videos; smoke evidence only",
              "environment": {"python": platform.python_version(), "machine": platform.machine(), "torch_threads": 2,
                              "versions": {p: importlib.metadata.version(p) for p in ["torch", "trustmark", "c2pa-python", "Pillow", "av"]}},
              "cold_model_seconds": round(cold, 3), "images": images, "transformations": rows, "negative_controls": negatives, "videos": videos,
              "median_image_seconds": statistics.median(r["seconds"] for r in images),
              "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "limitations": "No calibrated FPR/FNR, adversarial removal guarantee, or legal certification. CPU time excludes initial model loading; video verification samples frames. Synthetic audio is not independently watermarked."}
    (root / "report.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"report": str(root / "report.json"), "recovered": sum(r["correct_id"] for r in rows), "total": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
