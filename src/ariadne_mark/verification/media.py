"""Inspect actual media; keep cryptographic evidence and recovery separate."""

import json
from pathlib import Path

from ariadne_mark.c2pa_types import declared_source_types
from ariadne_mark.errors import AriadneError, UnsupportedMedia, C2paRuntimeMismatch
from ariadne_mark.provenance import ProvenanceRecord
from ariadne_mark.signing import ASSERTION, MIME, read_manifest
from ariadne_mark.watermark import valid_token


def inspect_c2pa(path: Path, *, trust_anchors: Path | None = None, tsa_trust_anchors: Path | None = None) -> dict:
    try:
        raw = read_manifest(path, trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors)
    except C2paRuntimeMismatch as exc:
        return {"status": "not_checked", "reason": "c2pa_runtime_unqualified",
                "signature": "not_checked", "issuer_trust": "not_checked", "runtime": exc.report}
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
    result["manifest_id"] = raw.get("active_manifest")
    result["declared_source_types"] = declared_source_types(manifest)
    assertions = [a.get("data") for a in manifest.get("assertions", [])
                  if isinstance(a, dict) and a.get("label") == ASSERTION]
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


REPORT_SCHEMA_VERSION = 2
MAX_IDS = 16
MAX_POSITIONS = 32
MAX_REGISTRY_LOOKUPS = 8
PASS_FIELDS = ("pass", "algorithm", "implementation", "selection", "preprocessing", "coverage", "requested_positions",
               "unique_frames", "observations", "time_range_s", "stop_reason", "complete")
VIDEO_VIEW = "decoded_rgb_display_orientation"
IMAGE_VIEW = "exif_transposed_rgb"


def _implementation(engine):
    return getattr(engine, "implementation", type(engine).__name__)


def _annotate(rows, frames, pass_index, algorithm):
    """Attach scheme, pass and decoded-frame identity to one pass's rows.

    Identity is copied only when the adapter returned one row per frame;
    otherwise it is left unknown rather than guessed.
    """
    identities = [getattr(item, "identity", None) for item in frames] if len(rows) == len(frames) else []
    result = []
    for index, row in enumerate(rows):
        row = {**row, "algorithm": algorithm, "pass": pass_index}
        if identities and identities[index] and "frame" not in row:
            row["frame"] = identities[index]
        result.append(row)
    return result


def _frame_key(row, index):
    """Exact frame identity when known, else float time, else the row itself."""
    frame = row.get("frame")
    if isinstance(frame, dict) and type(frame.get("pts")) is int and frame.get("time_base"):
        return ("pts", frame.get("stream", 0), frame["pts"], frame["time_base"])
    if isinstance(row.get("time"), (int, float)):
        return ("time", row["time"])
    return ("row", index)


def _pass_summary(pass_index, engine, name, rows, *, selection, preprocessing, coverage, requested=None, search=None):
    times = [row["time"] for row in rows if isinstance(row.get("time"), (int, float))]
    summary = {"pass": pass_index, "algorithm": name, "implementation": _implementation(engine),
               "selection": selection, "preprocessing": preprocessing, "coverage": coverage,
               "unique_frames": len({_frame_key(row, i) for i, row in enumerate(rows)}),
               "observations": len(rows), "time_range_s": [min(times), max(times)] if times else None}
    if requested is not None:
        summary["requested_positions"] = requested
    if search is not None:
        summary["stop_reason"] = search.get("reason")
        summary["complete"] = bool(search.get("file_exhausted") and search.get("hypotheses_complete"))
    return summary


def _evidence_scope(passes, unavailable, *, video):
    """What was actually examined. Nothing is inferred about the rest.

    ``whole_file_examined`` means at least one scheme decoded every frame (or
    the input is a single image); ``full_decode_schemes`` names them. Content
    counts as fully examined only when every pass was exhaustive and every
    configured scheme ran.
    """
    full = {"full_decode", "whole_image"}
    exhaustive = sorted({p["algorithm"] for p in passes if p["coverage"] in full})
    every = bool(passes) and all(p["coverage"] in full for p in passes) and not unavailable
    return {"passes": [{k: p[k] for k in PASS_FIELDS if k in p} for p in passes][:8],
            "whole_file_examined": bool(exhaustive), "full_decode_schemes": exhaustive,
            "unavailable_schemes": [u["algorithm"] for u in unavailable],
            "positions_scope": "observed_positions_only",
            "unexamined_content": "none" if every else "not_established"}


def verify_file(path: Path, *, marker=None, video_marker=None, legacy_video_marker=None, registry=None, trust_anchors: Path | None = None, tsa_trust_anchors: Path | None = None, verification_scope="all") -> dict:
    from ariadne_mark.verification.scope import normalize_scope, ALL_SCHEMES, CURRENT_SCHEMES
    declared_schemes = normalize_scope(verification_scope)
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in MIME:
        raise UnsupportedMedia("Provide a local JPEG, PNG or MP4 file")
    c2pa = inspect_c2pa(path, trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors)
    video = path.suffix.lower() == ".mp4"
    watermark = {"status": "not_checked", "reason": "watermark_engine_not_loaded"}
    if marker is not None or video_marker is not None:
        try:
            video = path.suffix.lower() == ".mp4"
            algorithm = c2pa.get("watermark_algorithm") if c2pa["status"] == "verified_claim" else None
            if algorithm and algorithm not in declared_schemes:
                raise _NoDecoder("signed_scheme_out_of_operator_scope")
            if video:
                from ariadne_mark.video import sample_frames
                frames = list(sample_frames(path))
            else:
                frames = [(open_image(path), None)]
            selection = "uniform_positions" if video else "whole_image"
            coverage = "sampled_positions" if video else "whole_image"
            view = VIDEO_VIEW if video else IMAGE_VIEW
            candidates = []
            owned_engines = []
            # Signed engine identifiers route directly; stripped metadata needs
            # explicit new + legacy decoding. Never relabel an old bit layout.
            if "adobe.trustmark.Q.variax-bch5" in declared_schemes and (algorithm == "adobe.trustmark.Q.variax-bch5" or (algorithm is None and video)):
                from ariadne_mark.videoq import VideoWatermarker
                engine = video_marker if getattr(video_marker, "algorithm", None) == VideoWatermarker.algorithm else VideoWatermarker()
                candidates.append(engine)
                if engine is not video_marker:
                    owned_engines.append(engine)
            if "meta.videoseal.1.0.bch20" in declared_schemes and algorithm in {None, "meta.videoseal.1.0.bch20"} and video:
                from ariadne_mark.videoseal import VideoSealWatermarker
                engine = video_marker if getattr(video_marker, "algorithm", None) == VideoSealWatermarker.algorithm else (legacy_video_marker or VideoSealWatermarker())
                candidates.append(engine)
            if "adobe.trustmark.Q.bch5" in declared_schemes and algorithm in {None, "adobe.trustmark.Q.bch5"} and marker is not None:
                candidates.append(marker)
            observations, aggregates, engines, unavailable, attempts = [], [], [], [], []
            search_results, confirmed_engines, auxiliary_unavailable = [], [], []
            if not candidates:
                # A signed legacy scheme whose decoder is not loaded is not
                # checked; another bit layout never stands in for it.
                raise _NoDecoder("no_decoder_for_signed_scheme" if algorithm else "watermark_engine_not_loaded")
            for engine in candidates:
                name = getattr(engine, "algorithm", "custom")
                try:
                    if video and hasattr(engine, "scan_video"):
                        result = engine.scan_video(path)
                        rows = _annotate(result["samples"], [], len(attempts), name)
                        aggregates.extend({**a, "algorithm": name} for a in result["aggregates"])
                        attempts.append({"algorithm": name, "samples": rows, "status": result["status"], "search": result["search"],
                                         **_pass_summary(len(attempts), engine, name, rows, selection="sequential_from_start",
                                                         preprocessing=VIDEO_VIEW, search=result["search"],
                                                         coverage="full_decode" if result["search"].get("file_exhausted") else "prefix_until_stop")})
                        search_results.append(result)
                        if result["status"] == "recovered_claim":
                            confirmed_engines.append(name)
                        observations.extend(rows)
                    elif hasattr(engine, "decode_frames"):
                        raw, aggregate = engine.decode_frames(frames)
                        rows = _annotate(raw, frames, len(attempts), name)
                        first = summarize_watermarks(rows, [aggregate] if aggregate else [], video=video)
                        attempts.append({"algorithm": name, "samples": rows, "aggregate": aggregate, "status": first["status"],
                                         **_pass_summary(len(attempts), engine, name, rows, selection=selection, preprocessing=view,
                                                         coverage=coverage, requested=5 if video else None)})
                        # Every pass's primary observations stay in the trace;
                        # a repeated frame is one unique frame, not two reads.
                        observations.extend(rows)
                        if (video and name == "adobe.trustmark.Q.variax-bch5"
                                and first["status"] == "not_found"):
                            from ariadne_mark.video import sample_frames
                            more = list(sample_frames(path, samples=20))
                            raw, aggregate = engine.decode_frames(more)
                            rows = _annotate(raw, more, len(attempts), name)
                            attempts.append({"algorithm": name, "samples": rows, "aggregate": aggregate,
                                             "status": summarize_watermarks(rows, [aggregate] if aggregate else [], video=video)["status"],
                                             **_pass_summary(len(attempts), engine, name, rows, selection=selection, preprocessing=view,
                                                             coverage=coverage, requested=20)})
                            observations.extend(rows)
                        if aggregate:
                            aggregates.append({**aggregate, "algorithm": name})
                        if summarize_watermarks(rows, [aggregate] if aggregate else [], video=video)['status'] == 'recovered_claim':
                            confirmed_engines.append(name)
                    else:
                        raw = [{"time": timestamp, "token": engine.decode(frame)} for frame, timestamp in frames]
                        rows = _annotate(raw, frames, len(attempts), name)
                        attempts.append({"algorithm": name, "samples": rows,
                                         **_pass_summary(len(attempts), engine, name, rows, selection=selection, preprocessing=view,
                                                         coverage=coverage, requested=5 if video else None)})
                        observations.extend(rows)
                        if summarize_watermarks(rows, [], video=video)['status'] == 'recovered_claim':
                            confirmed_engines.append(name)
                    engines.append(name)
                except (AriadneError, OSError, ValueError, ImportError) as exc:
                    issue = {"algorithm": name, "reason": type(exc).__name__}
                    # In current-only video scope Python Q is an additional
                    # decoder for the same qualified payload, not another required
                    # technique. A missing primary Q decoder is always incomplete.
                    if video and set(declared_schemes) == set(CURRENT_SCHEMES) and name == "adobe.trustmark.Q.bch5":
                        auxiliary_unavailable.append(issue)
                    else:
                        unavailable.append(issue)
                finally:
                    if any(engine is owned for owned in owned_engines):
                        close = getattr(engine, "close", None)
                        if close:
                            close()
            watermark = summarize_watermarks(observations, aggregates, video=video)
            if search_results and any(r["search"]["reason"] == "two_concordant_ids" for r in search_results):
                watermark["sample_coverage"]["interpretation"] = "early_stop_evidence"
            if search_results and not confirmed_engines and watermark["status"] not in {"invalid", "multiple_ids"}:
                if any(r["status"] == "not_checked" for r in search_results):
                    watermark.update(status="not_checked", reason="incomplete_video_search")
                elif any(r["status"] == "single_observation" for r in search_results):
                    watermark.update(status="single_observation", reason="id_not_confirmed")
                watermark.pop("token", None)
            watermark.update(algorithm_scope="configured_video_schemes" if video else "signed_scheme" if algorithm else "trustmark_image_scheme",
                             engines_checked=engines, unavailable_engines=unavailable,
                             unavailable_auxiliary_engines=auxiliary_unavailable,
                             checked_frames=len({_frame_key(row, i) for i, row in enumerate(observations)}),
                             attempts=attempts, evidence_scope=_evidence_scope(attempts, unavailable, video=video))
            if unavailable and watermark["status"] == "not_found":
                watermark.update(status="not_checked", reason="incomplete_engine_coverage")
            elif unavailable:
                watermark["coverage"] = "partial"
        except _NoDecoder as exc:
            watermark = {"status": "not_checked", "reason": exc.reason,
                         **({"signed_algorithm": algorithm} if algorithm else {})}
        except (AriadneError, OSError, ValueError, ImportError) as exc:
            watermark = {"status": "not_checked", "reason": type(exc).__name__}
    watermark["declared_schemes"] = list(declared_schemes)
    watermark["out_of_operator_scope"] = [s for s in ALL_SCHEMES if s not in declared_schemes]
    if isinstance(watermark.get("evidence_scope"), dict):
        watermark["evidence_scope"].update(declared_schemes=list(declared_schemes),
            out_of_operator_scope=watermark["out_of_operator_scope"])
    return _verification_result(path, c2pa, watermark, registry=registry, video=video, trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors)


class _NoDecoder(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def verify_video_export(path, engine, expected_windows, *, trust_anchors=None, tsa_trust_anchors=None):
    """Known-schedule export read-back, separate from blind public verification.

    At least one independently decoded ID per occupied window. Failed decoder
    observations remain in the receipt. The expected payload is never passed
    to the decoder; SDK.mark compares the returned evidence after this call.
    """
    from ariadne_mark.video import selected_window_frames, sample_frames, _orient, frame_identity
    from ariadne_mark.video.color import frame_image
    if engine.profile not in {"economy_5s", "economy_2s"}:
        frames = list(sample_frames(path))
        raw, aggregate = engine.decode_frames(frames)
        rows = _annotate(raw, frames, 0, engine.algorithm)
        watermark = summarize_watermarks(rows, [aggregate] if aggregate else [], video=True)
        passes = [_pass_summary(0, engine, engine.algorithm, rows, selection="uniform_positions", preprocessing=VIDEO_VIEW,
                                coverage="sampled_positions", requested=5)]
        watermark["evidence_scope"] = _evidence_scope(passes, [], video=True)
        return _verification_result(path, inspect_c2pa(path, trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors),
                                    watermark, registry=None, video=True)
    rows, found, seen = [], set(), set()
    for frame, timestamp, window, rotation in selected_window_frames(path, engine.profile):
        seen.add(window)
        if window in found:
            continue
        identity = frame_identity(frame)
        observations, _ = engine.decode_frames([(_orient(frame_image(frame), rotation), timestamp)])
        if len(observations) != 1:
            raise AriadneError("Incomplete Economy read-back")
        row = {**observations[0], "window": window, "algorithm": engine.algorithm, "pass": 0}
        if identity and "frame" not in row:
            row["frame"] = identity
        rows.append(row)
        if row.get("token"):
            found.add(window)
    watermark = summarize_watermarks(rows, [], video=True)
    all_windows_have_id = seen == set(expected_windows) == found
    # Export diagnostics have a known schedule plus a separately signed exact
    # file/token/record gate in SDK.mark. Do not apply the public blind-search
    # corroboration rule to a one-window file: preserve its per-window read-back
    # contract without giving that exception to verify_file/legacy detection.
    if watermark['status'] == 'single_observation' and all_windows_have_id:
        token = next(row['token'] for row in rows if row.get('token'))
        watermark.update(status='recovered_claim', token=token)
        watermark.pop('reason', None)
        watermark['sample_coverage'].update(confirmation_status='recovered_claim',
            confirmation_basis='known_schedule_export_readback')
        for entry in watermark.get("ids", []):
            if entry["token"] == token:
                entry.update(status="confirmed", confirmation_basis="known_schedule_export_readback",
                             reclassified={"from": "observed", "basis": "known_schedule_export_readback"})
    watermark["export_window_readback"] = {
        "profile": engine.profile, "expected_windows": sorted(expected_windows),
        "observed_windows": sorted(seen), "windows_with_id": sorted(found),
        "all_windows_have_id": all_windows_have_id,
        "interpretation": "known_schedule_export_check_not_blind_search"}
    passes = [_pass_summary(0, engine, engine.algorithm, rows, selection="known_schedule_windows",
                            preprocessing=VIDEO_VIEW, coverage="scheduled_windows")]
    watermark["evidence_scope"] = _evidence_scope(passes, [], video=True)
    c2pa = inspect_c2pa(path, trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors)
    return _verification_result(path, c2pa, watermark, registry=None, video=True)


def _registry_recovery(path, token, schemes, registry, digest, *, trust_anchors=None, tsa_trust_anchors=None):
    """Registry entry for one recovered ID, bound to the schemes that read it."""
    stored = registry.get(token)
    recovery = {"status": "found" if stored else "unknown_id", "binding": "watermark_only_not_cryptographic"}
    if stored:
        recovery.update(record=stored["record"],
                        content_binding="exact_registered_file" if digest() == stored["sha256"] else "not_verified",
                        record_scope="registry_entry_for_id_not_authenticated_source_of_this_copy")
        if hasattr(registry, 'get_manifest'):
            bundle = registry.get_manifest(token=token)
            if bundle is not None:
                from ariadne_mark.softbinding import compatible_manifest_algorithms, inspect_recovered
                if bundle['algorithm'] in compatible_manifest_algorithms(schemes, video=path.suffix.lower() == '.mp4'):
                    try:
                        recovered = inspect_recovered(bundle['bytes'], path, bundle['algorithm'], token,
                                                      trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors)
                        recovery['manifest'] = {**recovered, 'sha256': bundle['sha256'],
                            'public': bool(bundle['public']), 'algorithm_registration': 'provisional_not_registered'}
                    except (ValueError, OSError, ImportError, AriadneError):
                        recovery['manifest'] = {'status': 'not_checked', 'reason': 'manifest_validation_failed'}
    return recovery


def _verification_result(path, c2pa, watermark, *, registry, video, trust_anchors=None, tsa_trust_anchors=None):
    if c2pa.get("record"):
        c2pa["record_scope"] = ("development_signer_claim" if c2pa.get("development_identity") else
                                "trusted_signer_claim" if c2pa.get("issuer_trust") == "trusted" else
                                "claimed_by_untrusted_signer")
    signed_token = c2pa.get("token")
    for entry in watermark.get("ids", []):
        entry["matches_signed_claim"] = (entry["token"] == signed_token) if signed_token else None
    digest_value = []

    def digest():
        if not digest_value:
            import hashlib
            with path.open("rb") as content:
                digest_value.append(hashlib.file_digest(content, "sha256").hexdigest())
        return digest_value[0]

    recovery = {"status": "not_attempted"}
    token = watermark.get("token")
    multiple = watermark.get("status") == "multiple_ids"
    if token and registry is not None:
        schemes = {row.get("algorithm") for row in [*watermark.get("samples", []), *watermark.get("aggregates", [])]
                   if row.get("token") == token}
        recovery = _registry_recovery(path, token, schemes, registry, digest,
                                      trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors)
    elif multiple and registry is not None:
        # One lookup per confirmed ID, each tied to the schemes that read it.
        # No ID is chosen for the file; a single unconfirmed read is not looked up.
        per_id, lookups = [], 0
        for entry in watermark.get("ids", []):
            schemes = sorted({basis["algorithm"] for basis in entry["bases"]})
            row = {"token": entry["token"], "algorithms": schemes}
            if entry["status"] != "confirmed":
                row.update(status="not_attempted", reason="id_not_confirmed")
            elif lookups >= MAX_REGISTRY_LOOKUPS:
                row.update(status="not_attempted", reason="lookup_limit")
            else:
                lookups += 1
                row.update(_registry_recovery(path, entry["token"], schemes, registry, digest,
                                              trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors))
            per_id.append(row)
        recovery = {"status": "per_id", "per_id": per_id, "automatic_selection": "none"}
    signed_id_observed = (any(e["token"] == signed_token for e in watermark.get("ids", []))
                          or token == signed_token) if signed_token else None
    mismatch = bool(token and signed_token and token != signed_token)
    if c2pa["status"] == "invalid" or watermark["status"] == "invalid":
        label = "Invalid or conflicting provenance"
    elif multiple:
        # Several recovered IDs are several claims about parts of the file.
        # They neither invalidate a signature nor name one source for the file.
        label = "Multiple watermark IDs found; each applies only where it was observed"
        if c2pa["status"] == "verified_claim":
            label += "; signature valid"
        elif c2pa["status"] == "expired_credential":
            label += "; signing credential expired"
    elif mismatch:
        label = "Conflicting provenance claims: watermark ID differs from the signed claim"
    elif c2pa["status"] == "expired_credential":
        label = "Signing credential expired; signing time not verified"
    elif c2pa["status"] == "verified_claim" and c2pa.get("development_identity"):
        label = "Development signature; not a production identity"
    elif c2pa["status"] == "verified_claim" and c2pa.get("record") and c2pa["issuer_trust"] != "trusted":
        label = "Signature valid; issuer unverified"
    elif c2pa["status"] == "verified_claim" and c2pa.get("record"):
        label = "AI-generated" if c2pa["record"]["action"] == "created" else "AI-altered"
        label += " (signed claim; issuer " + c2pa["issuer_trust"] + ")"
    elif c2pa["status"] == "verified_claim":
        label = "C2PA signature valid; no supported AI-origin claim"
    elif recovery["status"] == "found":
        label = "Watermark ID found in registry; content match unverified" if recovery.get("content_binding") != "exact_registered_file" else "Watermark ID matches the registered file"
    elif token:
        label = "Watermark ID recovered; source unverified"
    else:
        label = "Provenance unavailable"
    # Keep positive evidence visible, but never headline an incomplete negative
    # scan as an absence. API clients may read only the human-readable label.
    if label == "Provenance unavailable" and (c2pa['status'] == 'not_checked' or watermark['status'] == 'not_checked'):
        label = "Check incomplete"
    if c2pa.get("reason") == "c2pa_runtime_unqualified":
        label = (label + "; signature check unavailable") if token or multiple else "Signature check unavailable; C2PA runtime not qualified"
    if watermark["status"] == "not_checked" and c2pa.get("development_identity") and c2pa["status"] == "verified_claim":
        label += "; watermark check incomplete"
    if video and (token or multiple) and c2pa["status"] != "verified_claim":
        label += "; sampled video evidence only"
    return {"schema_version": REPORT_SCHEMA_VERSION, "label": label, "c2pa": c2pa, "watermark": watermark,
            "recovery": recovery, "token_mismatch": mismatch, "signed_id_observed": signed_id_observed}


def _id_evidence(observations, aggregates, *, video):
    """Every recovered ID with its own basis; nothing is dropped or preferred."""
    found = {}
    for index, row in enumerate(observations):
        token = row.get("token")
        if token is None:
            continue
        scheme = found.setdefault(token, {"individual": {}, "aggregate": {}})["individual"].setdefault(
            row.get("algorithm", "custom"), {"frames": set(), "observations": 0, "times": set()})
        scheme["frames"].add(_frame_key(row, index))
        scheme["observations"] += 1
        if isinstance(row.get("time"), (int, float)):
            scheme["times"].add(row["time"])
    aggregate_ids = {}
    for row in aggregates:
        token = row.get("token")
        if token is None:
            continue
        name = row.get("algorithm", "custom")
        aggregate_ids.setdefault(name, set()).add(token)
        hits = found.setdefault(token, {"individual": {}, "aggregate": {}})["aggregate"]
        hits[name] = hits.get(name, 0) + 1
    ids = []
    for token, evidence in found.items():
        bases, basis = [], None
        for name in sorted(set(evidence["individual"]) | set(evidence["aggregate"])):
            individual = evidence["individual"].get(name)
            unique = len(individual["frames"]) if individual else 0
            hits = evidence["aggregate"].get(name, 0)
            if individual:
                bases.append({"algorithm": name, "basis": "individual", "unique_frames": unique,
                              "observations": individual["observations"]})
            if hits:
                bases.append({"algorithm": name, "basis": "aggregate", "aggregate_hits": hits,
                              "conflicting_aggregate_ids": len(aggregate_ids[name]) > 1})
            if basis is None:
                if individual and not video:
                    basis = "single_image_decode"
                elif unique >= 2:
                    basis = "two_or_more_unique_frames_one_scheme"
                elif hits and len(aggregate_ids[name]) == 1:
                    basis = "unambiguous_aggregate_one_scheme"
        entry = {"token": token, "status": "confirmed" if basis else "observed",
                 "confirmation_basis": basis, "bases": bases}
        if video:
            times = sorted(set().union(*[s["times"] for s in evidence["individual"].values()]))
            entry.update(first_time_s=times[0] if times else None, last_time_s=times[-1] if times else None,
                         positions_s=times[:MAX_POSITIONS])
            if len(times) > MAX_POSITIONS:
                entry["positions_truncated"] = len(times) - MAX_POSITIONS
        ids.append(entry)
    ids.sort(key=lambda e: (e.get("first_time_s") is None, e.get("first_time_s") or 0, e["token"]))
    return ids


def summarize_watermarks(observations, aggregates, *, video):
    """Never let averaged logits hide individually recovered conflicting IDs.

    Several distinct IDs give ``multiple_ids`` with every ID listed in
    ``ids``; none is promoted to the file's ID. Confirmation counts unique
    decoded frames within one payload scheme, so a frame read twice (two
    passes or two views) is one frame, not two.
    """
    tokens = {row["token"] for row in [*observations, *aggregates] if row.get("token") is not None}
    ids = _id_evidence(observations, aggregates, video=video)
    result = {"status": "recovered_claim" if tokens else "not_found", "samples": observations,
              "aggregates": aggregates, "scope": "sampled_frames" if video else "whole_image"}
    if not observations:
        result.update(status="not_checked", reason="no_decodable_frames")
    elif len(tokens) == 1:
        if ids[0]["status"] != "confirmed":
            result.update(status='single_observation', reason='id_not_confirmed')
        else:
            result['token'] = ids[0]["token"]
    elif len(tokens) > 1:
        result.update(status="multiple_ids", reason="multiple_ids_observed")
    result["ids"] = ids[:MAX_IDS]
    if len(ids) > MAX_IDS:
        result["ids_truncated"] = len(ids) - MAX_IDS
    if video:
        per_engine = []
        observed_token = next(iter(tokens)) if len(tokens) == 1 else None
        for name in sorted({row.get("algorithm", "custom") for row in observations}):
            rows = [(i, row) for i, row in enumerate(observations) if row.get("algorithm", "custom") == name]
            sampled = len({_frame_key(row, i) for i, row in rows})
            matches = len({_frame_key(row, i) for i, row in rows if row.get("token") == observed_token}) if observed_token else 0
            per_engine.append({"algorithm": name, "sampled_frames": sampled, "matched_frames": matches,
                               "matched_fraction": matches / sampled if sampled else None})
        best = max(per_engine, key=lambda row: row["matched_fraction"] or 0, default=None)
        result["sample_coverage"] = {"by_engine": per_engine,
            "confirmation_status": result['status'],
            "matched_frames": best["matched_frames"] if best else 0,
            "sampled_frames": best["sampled_frames"] if best else 0,
            "interpretation": "partial_sample_evidence" if result['status'] == 'single_observation' else
                              "multiple_ids_observed" if result['status'] == 'multiple_ids' else
                              "all_sampled_frames_match" if best and best["matched_fraction"] == 1 else
                              "partial_sample_evidence" if best and best["matched_frames"] else
                              "aggregate_only_evidence" if result.get("token") else "no_id_recovered",
            "whole_video_coverage": "not_established"}
    return result
