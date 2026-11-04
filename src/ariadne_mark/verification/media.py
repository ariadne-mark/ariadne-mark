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
        try:
            from c2pa import C2paError
            absent = isinstance(exc, C2paError.ManifestNotFound)
            malformed = isinstance(exc, tuple(getattr(C2paError, name) for name in
                ("InvalidAsset", "InvalidClaim", "InvalidContent", "InvalidSignature", "AssertionDecoding")
                if hasattr(C2paError, name)))
        except ImportError:
            absent = malformed = False
        if absent:
            return {"status": "not_found", "signature": "not_checked", "issuer_trust": "not_checked"}
        # Runtime failures, allocation failures and unknown native errors never
        # become a successful negative or a claim that a signature was forged.
        return {"status": "invalid" if malformed else "not_checked",
                "reason": "malformed_c2pa" if malformed else "c2pa_read_failed",
                "signature": "invalid" if malformed else "not_checked", "issuer_trust": "not_checked"}
    active = raw.get("validation_results", {}).get("activeManifest", {})
    successes = {item.get("code") for item in active.get("success", [])}
    failures = {item.get("code") for item in active.get("failure", [])}
    informational = {item.get("code") for item in active.get("informational", [])}
    substantive = failures - {"signingCredential.untrusted"}
    expired_only = substantive == {"signingCredential.expired"}
    timestamp_trusted = ("timeStamp.trusted" in successes and "timeStamp.validated" in successes
                         and not any(code and code.startswith("timeStamp.") for code in failures)
                         and "timeStamp.untrusted" not in informational)
    # Native validation decides validity at a trusted timestamp. Never suppress
    # expiry merely because a timestamp digest validated (an untrusted TSA can
    # issue any time). An unresolved expiry is not labelled content tampering.
    binding = {"assertion.dataHash.match", "assertion.bmffHash.match", "assertion.boxesHash.match"}
    valid = not substantive and "claimSignature.validated" in successes and bool(binding & successes)
    result = {
        "status": "verified_claim" if valid else "expired_credential" if expired_only else "invalid",
        "signature": "valid" if valid else "not_checked" if expired_only else "invalid",
        "timestamp_trust": "trusted" if timestamp_trusted else "untrusted" if "timeStamp.validated" in successes else "not_present_or_invalid",
        "credential_time": "expired_without_trusted_signing_time" if expired_only else "valid" if valid else "not_verified",
        "issuer_trust": ("trusted" if "signingCredential.trusted" in successes else "untrusted") if valid else "not_checked",
        "validation_codes": sorted(x for x in successes | failures | informational if x),
        "revocation": "not_checked_offline",
    }
    if expired_only:
        result["reason"] = "signing_credential_expired_without_trusted_time"
    manifest = raw.get("manifests", {}).get(raw.get("active_manifest"), {})
    assertions = [a.get("data") for a in manifest.get("assertions", []) if a.get("label") == ASSERTION]
    result["ingredient_count"] = len(manifest.get("ingredients", []))
    if len(assertions) == 1:
        try:
            claim = assertions[0]
            record = ProvenanceRecord.from_json(json.dumps(claim["record"]))
            token = claim["watermark"]["token"]
            formats = {"ariadne-v1": "adobe.trustmark.Q.bch5", "ariadne-vs1": "meta.videoseal.1.0.bch20", "ariadne-vq1": "adobe.trustmark.Q.variax-bch5"}
            fmt = claim["watermark"]["format"]
            if not valid_token(token) or formats.get(fmt) != claim["watermark"].get("algorithm"):
                raise ValueError("Unknown payload")
            result.update(record=record.to_dict(), token=token, watermark_algorithm=formats[fmt], development_identity=claim.get("development_identity", False),
                          watermark_profile=claim["watermark"].get("profile"),
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
            if original.info.get("icc_profile"):
                raise UnsupportedMedia("ICC-tagged input requires explicit conversion to sRGB before marking/checking")
            return ImageOps.exif_transpose(original).convert("RGBA" if "transparency" in original.info or "A" in original.getbands() else "RGB")
    except UnsupportedMedia:
        raise
    except Exception as exc:
        raise UnsupportedMedia("Cannot decode image") from exc


def verify_file(path: Path, *, marker=None, video_marker=None, legacy_video_marker=None, registry=None, trust_anchors: Path | None = None) -> dict:
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in MIME:
        raise UnsupportedMedia("Provide a local JPEG, PNG or MP4 file")
    c2pa = inspect_c2pa(path, trust_anchors=trust_anchors)
    video = path.suffix.lower() == ".mp4"
    watermark = {"status": "not_checked", "reason": "watermark_engine_not_loaded"}
    if marker is not None or video_marker is not None:
        try:
            video = path.suffix.lower() == ".mp4"
            algorithm = c2pa.get("watermark_algorithm") if c2pa["status"] == "verified_claim" else None
            if video:
                from ariadne_mark.video import sample_frames
                frames = list(sample_frames(path))
            else:
                frames = [(open_image(path), None)]
            candidates = []
            owned_engines = []
            # Signed engine identifiers route directly; stripped metadata needs
            # explicit new + legacy decoding. Never relabel an old bit layout.
            if algorithm in {None, "adobe.trustmark.Q.variax-bch5"}:
                from ariadne_mark.videoq import VideoWatermarker
                engine = video_marker if getattr(video_marker, "algorithm", None) == VideoWatermarker.algorithm else VideoWatermarker()
                candidates.append(engine)
                if engine is not video_marker:
                    owned_engines.append(engine)
            if algorithm in {None, "meta.videoseal.1.0.bch20"} and video:
                from ariadne_mark.videoseal import VideoSealWatermarker
                engine = video_marker if getattr(video_marker, "algorithm", None) == VideoSealWatermarker.algorithm else (legacy_video_marker or VideoSealWatermarker())
                candidates.append(engine)
            if algorithm in {None, "adobe.trustmark.Q.bch5"} and marker is not None:
                candidates.append(marker)
            observations, aggregates, engines, unavailable, attempts = [], [], [], [], []
            for engine in candidates:
                name = getattr(engine, "algorithm", "custom")
                try:
                    if hasattr(engine, "decode_frames"):
                        rows, aggregate = engine.decode_frames(frames)
                        first = summarize_watermarks(rows, [aggregate] if aggregate else [], video=video)
                        attempts.append({"algorithm": name, "samples": rows, "aggregate": aggregate, "status": first["status"]})
                        if (video and name == "adobe.trustmark.Q.variax-bch5"
                                and first["status"] == "not_found"):
                            from ariadne_mark.video import sample_frames
                            rows, aggregate = engine.decode_frames(list(sample_frames(path, samples=20)))
                            attempts.append({"algorithm": name, "samples": rows, "aggregate": aggregate,
                                             "status": summarize_watermarks(rows, [aggregate] if aggregate else [], video=video)["status"]})
                        if aggregate:
                            aggregates.append({**aggregate, "algorithm": name})
                    else:
                        rows = [{"time": timestamp, "token": engine.decode(frame)} for frame, timestamp in frames]
                        attempts.append({"algorithm": name, "samples": rows})
                    observations.extend({**row, "algorithm": name} for row in rows)
                    engines.append(name)
                except (AriadneError, OSError, ValueError, ImportError) as exc:
                    unavailable.append({"algorithm": name, "reason": type(exc).__name__})
                finally:
                    if any(engine is owned for owned in owned_engines):
                        close = getattr(engine, "close", None)
                        if close:
                            close()
            watermark = summarize_watermarks(observations, aggregates, video=video)
            watermark.update(engines_checked=engines, unavailable_engines=unavailable,
                             checked_frames=len({row.get("time") for attempt in attempts for row in attempt["samples"]}),
                             attempts=attempts)
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
            import hashlib
            with path.open("rb") as content:
                digest = hashlib.file_digest(content, "sha256").hexdigest()
            recovery.update(record=stored["record"],
                            content_binding="exact_registered_file" if digest == stored["sha256"] else "not_verified",
                            record_scope="registry_entry_for_id_not_authenticated_source_of_this_copy")
    mismatch = bool(token and c2pa.get("token") and token != c2pa["token"])
    if c2pa["status"] == "invalid" or watermark["status"] == "invalid" or mismatch:
        label = "Invalid or conflicting provenance"
    elif c2pa["status"] == "expired_credential":
        label = "Signing credential expired; signing time not verified"
    elif c2pa["status"] == "verified_claim" and c2pa.get("record") and c2pa["issuer_trust"] != "trusted":
        label = "Signature valid; issuer unverified"
    elif c2pa["status"] == "verified_claim" and c2pa.get("record"):
        label = "AI-generated" if c2pa["record"]["action"] == "created" else "AI-altered"
        label += " (signed claim; issuer " + c2pa["issuer_trust"] + ")"
    elif recovery["status"] == "found":
        label = "Watermark ID found in registry; content match unverified" if recovery.get("content_binding") != "exact_registered_file" else "Watermark ID matches the registered file"
    elif token:
        label = "Watermark ID recovered; source unverified"
    else:
        label = "Provenance unavailable"
    if video and token and c2pa["status"] != "verified_claim":
        label += "; sampled video evidence only"
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
    if video:
        per_engine = []
        for name in sorted({row.get("algorithm", "custom") for row in observations}):
            rows = [row for row in observations if row.get("algorithm", "custom") == name]
            matches = sum(row.get("token") == result.get("token") for row in rows) if result.get("token") else 0
            per_engine.append({"algorithm": name, "sampled_frames": len(rows), "matched_frames": matches,
                               "matched_fraction": matches / len(rows) if rows else None})
        best = max(per_engine, key=lambda row: row["matched_fraction"] or 0, default=None)
        result["sample_coverage"] = {"by_engine": per_engine,
            "matched_frames": best["matched_frames"] if best else 0,
            "sampled_frames": best["sampled_frames"] if best else 0,
            "interpretation": "all_sampled_frames_match" if best and best["matched_fraction"] == 1 else
                              "partial_sample_evidence" if best and best["matched_frames"] else
                              "aggregate_only_evidence" if result.get("token") else "no_id_recovered",
            "whole_video_coverage": "not_established"}
    return result
