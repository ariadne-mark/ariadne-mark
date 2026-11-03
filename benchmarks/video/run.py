"""Full SDK stock-video regression. Media/identities stay in the output folder.

Input: a manifest with items containing kind/name/input/sha256. No downloads.
Only publish report.json, never the identity or complete output directory.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import resource
import subprocess
import time
from unittest.mock import patch

from ariadne_mark.pipeline import SDK
from ariadne_mark.provenance import ProvenanceRecord, GenerativeSystem, MediaKind, Action
from ariadne_mark.signing import SigningIdentity, create_development_identity
from ariadne_mark.watermark import Watermarker
from ariadne_mark.videoseal import VideoSealWatermarker, SHA256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.corpus / "manifest.json").read_text())
    create_development_identity(args.output / "identity")
    tm, vs = Watermarker(), VideoSealWatermarker()
    start = time.perf_counter()
    with vs._lock:
        vs._load()
    cold = time.perf_counter() - start
    sdk = SDK(tm, SigningIdentity.from_directory(args.output / "identity", allow_dev=True), video_marker=vs)
    report = {"version": "0.3.0a0", "model_sha256": SHA256, "model_load_seconds": cold,
              "protocol": "Full SDK; CPU threads=2; 4-frame VideoSeal batches; 5-frame verifier; 3 tokens per clip; transforms on first token only; no legal qualification",
              "exports": [], "transforms": [], "negatives": []}
    rng = random.Random(20261103)
    def save():
        report["peak_python_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        (args.output / "report.json").write_text(json.dumps(report, indent=2))
    for item in manifest["items"]:
        if item["kind"] != "video":
            continue
        source = args.corpus / item["input"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item["sha256"]
        check = sdk.verify(source)
        report["negatives"].append({"fixture": item["name"], "watermark": check["watermark"]})
        for repeat in range(3):
            token = f"{(0x14d << 48) | rng.getrandbits(48):016x}"
            output = args.output / f"{item['name']}-{repeat}.mp4"
            record = ProvenanceRecord.create(publisher="Engineering fixture; stock original is not AI generated",
                system=GenerativeSystem("Watermark test", "0.3"), media_kind=MediaKind.VIDEO, action=Action.CREATED,
                created_at=datetime.now(timezone.utc))
            start = time.perf_counter()
            try:
                with patch("ariadne_mark.pipeline.new_token", return_value=token):
                    receipt = sdk.mark(source, output, record, audio_kind="original")
                export_s = time.perf_counter() - start
                start = time.perf_counter()
                check = sdk.verify(output)
                row = {"fixture": item["name"], "repeat": repeat, "token": token, "export_seconds": export_s,
                       "verify_seconds": time.perf_counter() - start, "c2pa": check["c2pa"]["status"],
                       "exact": check["watermark"].get("token") == token, "watermark": check["watermark"],
                       "input_sha256": item["sha256"], "output_sha256": receipt["sha256"]}
            except Exception as exc:
                row = {"fixture": item["name"], "repeat": repeat, "token": token, "error": str(exc), "exact": False}
            report["exports"].append(row)
            save()
            print(json.dumps({k:v for k,v in row.items() if k != "watermark"}), flush=True)
            if repeat != 0 or not output.exists():
                continue
            for name, vf, crf in [("crf28", None, 28), ("crf35", None, 35),
                                  ("half-crf28", "scale=640:360", 28),
                                  ("crop10-crf28", "crop=1152:648", 28)]:
                transformed = args.output / f"{item['name']}-{name}.mp4"
                command = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(output)]
                if vf:
                    command += ["-vf", vf]
                command += ["-c:v", "libx264", "-threads", "2", "-crf", str(crf), "-an", "-map_metadata", "-1", str(transformed)]
                subprocess.run(command, check=True, capture_output=True, timeout=120)
                start = time.perf_counter()
                check = sdk.verify(transformed)
                report["transforms"].append({"fixture": item["name"], "transform": name,
                    "exact": check["watermark"].get("token") == token,
                    "verify_seconds": time.perf_counter() - start,
                    "c2pa": check["c2pa"]["status"], "watermark": check["watermark"]})
                save()
    save()

if __name__ == "__main__":
    main()
