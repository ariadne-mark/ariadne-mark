"""Export only after real watermark and C2PA read-back succeed."""

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from ariadne_mark.errors import AriadneError, UnsupportedMedia, VerificationFailed
from ariadne_mark.provenance import ProvenanceRecord
from ariadne_mark.signing import SigningIdentity, sign_file, MIME
from ariadne_mark.verification.media import open_image, verify_file, inspect_c2pa
from ariadne_mark.watermark import new_token
from ariadne_mark.videoseal import VideoSealWatermarker


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class SDK:
    marker: object
    identity: SigningIdentity | None = None
    registry: object | None = None
    trust_anchors: Path | None = None

    video_marker: object = field(default_factory=VideoSealWatermarker)

    def verify(self, path: Path) -> dict:
        return verify_file(path, marker=self.marker, video_marker=self.video_marker, registry=self.registry, trust_anchors=self.trust_anchors)

    def mark(self, source: Path, destination: Path, record: ProvenanceRecord, *, visible=False, audio_kind="unknown") -> dict:
        source, destination = Path(source).resolve(), Path(destination).resolve()
        if self.identity is None:
            raise AriadneError("A signing identity is required; unsigned export is not supported")
        if not source.is_file() or source.suffix.lower() not in MIME or destination.suffix.lower() not in MIME:
            raise UnsupportedMedia("Supported files: PNG, JPEG and MP4")
        video = source.suffix.lower() == ".mp4"
        if video != (destination.suffix.lower() == ".mp4") or record.media_kind.value != ("video" if video else "image"):
            raise UnsupportedMedia("Input, output and provenance media kinds must match")
        if audio_kind not in {"original", "synthetic", "unknown", "none"}:
            raise ValueError("audio_kind must be original, synthetic, unknown or none")
        receipt_path = destination.with_name(destination.name + ".receipt.json")
        if destination.exists() or receipt_path.exists() or source == destination:
            raise AriadneError("Output already exists; choose a new destination")
        parent_status = inspect_c2pa(source)
        if parent_status["status"] in {"invalid", "not_checked"}:
            raise VerificationFailed("Input C2PA is invalid or could not be checked")
        parent = source if parent_status["status"] == "verified_claim" or record.action.value == "altered" else None
        token = new_token()
        while self.registry is not None and self.registry.contains(token):
            token = new_token()
        start = time.monotonic()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ariadne-", dir=destination.parent) as temporary:
            work = Path(temporary)
            marked = work / ("watermarked" + destination.suffix.lower())
            signed = work / ("signed" + destination.suffix.lower())
            details = {}
            audio = "none"
            if video:
                from ariadne_mark.video import encode_video, probe
                if probe(source)["audio"] and audio_kind == "none":
                    raise UnsupportedMedia("Input contains audio; select its provenance explicitly")
                details = encode_video(source, marked, self.video_marker, token, visible=visible, altered=record.action.value == "altered")
                audio = audio_kind if details["audio"] != "none" else "none"
            else:
                from ariadne_mark.disclosure import apply_label
                image = open_image(source)
                if visible:
                    image = apply_label(image, altered=record.action.value == "altered")
                alpha = image.getchannel("A") if "A" in image.getbands() else None
                image = self.marker.encode(image, token)
                if alpha is not None:
                    if marked.suffix.lower() != ".png":
                        raise UnsupportedMedia("Preserving transparency requires PNG output")
                    image.putalpha(alpha)
                if marked.suffix.lower() in {".jpg", ".jpeg"}:
                    image.save(marked, "JPEG", quality=95, subsampling=0)
                else:
                    image.save(marked, "PNG")
            engine = self.video_marker if video else self.marker
            sign_file(marked, signed, record, token, self.identity, parent=parent, disclosure=visible, audio=audio,
                      algorithm=getattr(engine, "algorithm", "adobe.trustmark.Q.bch5"),
                      payload_format=getattr(engine, "payload_format", "ariadne-v1"))
            checked = self.verify(signed)
            samples = checked["watermark"].get("samples", [])
            if (checked["c2pa"]["status"] != "verified_claim" or checked["c2pa"].get("token") != token
                    or checked["c2pa"].get("record") != record.to_dict()
                    or checked["watermark"].get("status") != "recovered_claim"
                    or checked["watermark"].get("token") != token
                    or not samples
                    or (not video and any(row["token"] != token for row in samples))):
                matches = sum(row["token"] == token for row in samples)
                raise VerificationFailed(f"Final read-back failed: C2PA={checked['c2pa']['status']}, watermark={checked['watermark']['status']}, matching frames={matches}/{len(samples)}; no output published")
            digest = file_hash(signed)
            receipt = {"schema_version": 1, "sdk_version": "0.3.0a0", "asset_id": str(record.asset_id),
                       "token": token, "sha256": digest, "seconds": round(time.monotonic() - start, 3),
                       "development_identity": self.identity.development, "audio_kind": audio,
                       "video": details, "verification": checked}
            receipt["registry_recorded"] = self.registry is not None
            checked["recovery"] = {"status": "not_attempted", "reason": "export_readback_before_registry_commit"}
            # Hard-link publication is atomic and refuses overwrite, including races.
            os.link(signed, destination)
            receipt_created = False
            try:
                with receipt_path.open("x") as file:
                    receipt_created = True
                    json.dump(receipt, file, indent=2)
                if self.registry is not None:
                    self.registry.add(token, record, digest, receipt)
            except Exception:
                destination.unlink(missing_ok=True)
                if receipt_created:
                    receipt_path.unlink(missing_ok=True)
                raise
        return receipt
