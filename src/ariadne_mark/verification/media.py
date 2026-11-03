"""Inspect actual media; keep cryptographic evidence and recovery separate."""

import json
from pathlib import Path

from ariadne_mark.errors import AriadneError, UnsupportedMedia
from ariadne_mark.provenance import ProvenanceRecord
from ariadne_mark.signing import ASSERTION, MIME, read_manifest
from ariadne_mark.watermark import valid_token


def inspect_c2pa(path: Path, *, trust_anchors: Path | None = None) -> dict:
    try:
        raw = read_manifest(path, trust_anchors=trust_anchors)
    except Exception as exc:
        if type(exc).__name__ == "_C2paManifestNotFound":
            return {"status": "not_found", "signature": "not_checked", "issuer_trust": "not_checked"}
        if isinstance(exc, (ImportError, OSError)):
            return {"status": "not_checked", "reason": "c2pa_unavailable", "signature": "not_checked", "issuer_trust": "not_checked"}
        return {"status": "invalid", "reason": "c2pa_read_failed", "signature": "invalid", "issuer_trust": "not_checked"}
    active = raw.get("validation_results", {}).get("activeManifest", {})
    successes = {item.get("code") for item in active.get("success", [])}
    failures = {item.get("code") for item in active.get("failure", [])}
    substantive = failures - {"signingCredential.untrusted"}
    binding = {"assertion.dataHash.match", "assertion.bmffHash.match", "assertion.boxesHash.match"}
    valid = not substantive and "claimSignature.validated" in successes and bool(binding & successes)
    result = {
        "status": "verified_claim" if valid else "invalid", "signature": "valid" if valid else "invalid",
        "issuer_trust": ("trusted" if "signingCredential.trusted" in successes else "untrusted") if valid else "not_checked",
        "validation_codes": sorted(x for x in successes | failures if x),
        "revocation": "not_checked_offline",
    }
    manifest = raw.get("manifests", {}).get(raw.get("active_manifest"), {})
    assertions = [a.get("data") for a in manifest.get("assertions", []) if a.get("label") == ASSERTION]
    result["ingredient_count"] = len(manifest.get("ingredients", []))
    if len(assertions) == 1:
        try:
            claim = assertions[0]
            record = ProvenanceRecord.from_json(json.dumps(claim["record"]))
            token = claim["watermark"]["token"]
            formats = {"ariadne-v1": "adobe.trustmark.Q.bch5", "ariadne-vs1": "meta.videoseal.1.0.bch20"}
            fmt = claim["watermark"]["format"]
            if not valid_token(token) or formats.get(fmt) != claim["watermark"].get("algorithm"):
                raise ValueError("Unknown payload")
            result.update(record=record.to_dict(), token=token, watermark_algorithm=formats[fmt], development_identity=claim.get("development_identity", False),
                          audio=claim.get("audio", "unknown"), visible_disclosure=claim.get("visible_disclosure", False))
        except (KeyError, TypeError, ValueError):
            result.update(status="invalid", reason="invalid_ariadne_assertion")
    elif len(assertions) > 1:
        result.update(status="invalid", reason="ambiguous_ariadne_assertions")
    else:
        result["claim_scope"] = "external_c2pa_manifest"
    return result


def open_image(path: Path):
    from PIL import Image, ImageOps
    try:
        with Image.open(path) as original:
            if original.format not in {"JPEG", "PNG"} or getattr(original, "n_frames", 1) != 1:
                raise UnsupportedMedia("Only single-frame JPEG and PNG images are supported")
            if min(original.size) < 256 or max(original.size) > 4096:
                raise UnsupportedMedia("Image dimensions must be 256–4096 pixels")
            if original.mode not in {"RGB", "RGBA", "L", "LA", "P"}:
                raise UnsupportedMedia("Convert image to 8-bit RGB/RGBA explicitly first")
            return ImageOps.exif_transpose(original).convert("RGBA" if "transparency" in original.info or "A" in original.getbands() else "RGB")
    except UnsupportedMedia:
        raise
    except Exception as exc:
        raise UnsupportedMedia("Cannot decode image") from exc


def verify_file(path: Path, *, marker=None, video_marker=None, registry=None, trust_anchors: Path | None = None) -> dict:
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in MIME:
        raise UnsupportedMedia("Provide a local JPEG, PNG or MP4 file")
    c2pa = inspect_c2pa(path, trust_anchors=trust_anchors)
    watermark = {"status": "not_checked", "reason": "watermark_engine_not_loaded"}
    if marker is not None or video_marker is not None:
        try:
            video = path.suffix.lower() == ".mp4"
            if video:
                from ariadne_mark.video import sample_frames
                frames = list(sample_frames(path))
                algorithm = c2pa.get("watermark_algorithm") if c2pa["status"] == "verified_claim" else None
                candidates = []
                if algorithm != "adobe.trustmark.Q.bch5":
                    if video_marker is None:
                        from ariadne_mark.videoseal import VideoSealWatermarker
                        video_marker = VideoSealWatermarker()
                    candidates.append(video_marker)
                if algorithm != "meta.videoseal.1.0.bch20" and marker is not None:
                    candidates.append(marker)
            else:
                frames = [(open_image(path), None)]
                candidates = [marker] if marker is not None else []
            observations, aggregates, engines, unavailable = [], [], [], []
            for engine in candidates:
                name = getattr(engine, "algorithm", "custom")
                try:
                    if hasattr(engine, "decode_frames"):
                        rows, aggregate = engine.decode_frames(frames)
                        if aggregate:
                            aggregates.append({**aggregate, "algorithm": name})
                    else:
                        rows = [{"time": timestamp, "token": engine.decode(frame)} for frame, timestamp in frames]
                    observations.extend({**row, "algorithm": name} for row in rows)
                    engines.append(name)
                except (AriadneError, OSError, ValueError, ImportError) as exc:
                    unavailable.append({"algorithm": name, "reason": type(exc).__name__})
            watermark = summarize_watermarks(observations, aggregates, video=video)
            watermark.update(engines_checked=engines, unavailable_engines=unavailable,
                             checked_frames=len(frames))
            if unavailable and watermark["status"] == "not_found":
                watermark.update(status="not_checked", reason="incomplete_engine_coverage")
            elif unavailable:
                watermark["coverage"] = "partial"
        except (AriadneError, OSError, ValueError, ImportError) as exc:
            watermark = {"status": "not_checked", "reason": type(exc).__name__}
    recovery = {"status": "not_attempted"}
    token = watermark.get("token")
    if token and registry is not None:
        stored = registry.get(token)
        recovery = {"status": "found" if stored else "unknown_id", "binding": "watermark_only_not_cryptographic"}
        if stored:
            recovery["record"] = stored["record"]
    mismatch = bool(token and c2pa.get("token") and token != c2pa["token"])
    if c2pa["status"] == "invalid" or watermark["status"] == "invalid" or mismatch:
        label = "Invalid or conflicting provenance"
    elif c2pa["status"] == "verified_claim" and c2pa.get("record"):
        label = "AI-generated" if c2pa["record"]["action"] == "created" else "AI-altered"
        label += " (signed claim; issuer " + c2pa["issuer_trust"] + ")"
    elif recovery["status"] == "found":
        label = "Watermark recovered; source record found"
    elif token:
        label = "Watermark recovered; source unknown"
    else:
        label = "Provenance unavailable"
    return {"schema_version": 1, "label": label, "c2pa": c2pa, "watermark": watermark,
            "recovery": recovery, "token_mismatch": mismatch}


def summarize_watermarks(observations, aggregates, *, video):
    """Never let averaged logits hide individually recovered conflicting IDs."""
    tokens = {row["token"] for row in [*observations, *aggregates] if row.get("token") is not None}
    result = {"status": "recovered_claim" if tokens else "not_found", "samples": observations,
              "aggregates": aggregates, "scope": "sampled_frames" if video else "whole_image"}
    if not observations:
        result.update(status="not_checked", reason="no_decodable_frames")
    elif len(tokens) == 1:
        result["token"] = next(iter(tokens))
    elif len(tokens) > 1:
        result.update(status="invalid", reason="multiple_tokens")
    return result
