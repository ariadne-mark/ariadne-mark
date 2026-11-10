"""Bounded blind video search with one CNN pass and cached-logit recovery.

No expected ID, signed profile, known schedule or registry is used by search.
The small benchmark is not a calibration of this multiple-hypothesis detector.
"""
import math
import time
from collections import Counter

from ariadne_mark.errors import UnsupportedMedia


def phase_groups(times, *, max_hypotheses=512):
    """Bounded unknown-phase bank, independent of timestamp denominators.

    Up to 64 observed phase representatives per second (15.625 ms bins) for
    periods 1/2/5s: at most 512 candidates. Fractional FPS no longer creates
    thousands of almost identical hypotheses. This is a discrete search bank,
    not exhaustive coverage of continuous phase or a population FPR guarantee.
    Recovery windows are 93.75ms inside the encoder's 125ms windows, leaving
    room for the phase quantization instead of averaging adjacent clean frames.
    """
    if not times:
        return
    relative = [t - times[0] for t in times]
    seen = set()
    yielded = 0
    for period in (1, 2, 5):
        bins = {}
        for timestamp in relative:
            phase = timestamp % period
            bucket = min(int(phase * 64), period * 64 - 1)
            # Choose an observed phase nearest the bin center, deterministically.
            rank = (abs(phase - (bucket + .5) / 64), phase)
            if bucket not in bins or rank < bins[bucket][0]:
                bins[bucket] = (rank, phase)
        for _, phase in sorted(bins.values(), key=lambda item: item[1]):
            indices = tuple(i for i, t in enumerate(relative) if (t - phase + 1e-6) % period < .09375)
            if len(indices) < 2:
                continue
            if len(indices) > 20:
                indices = tuple(indices[round((len(indices) - 1) * i / 19)] for i in range(20))
            if indices in seen:
                continue
            seen.add(indices)
            if yielded >= max_hypotheses:
                yield None
                return
            yielded += 1
            yield period, phase, indices


def scan_video(path, marker, *, max_frames=2000, max_seconds=120, max_hypotheses=512):
    import av
    from ariadne_mark.video import probe, validate_decoder_streams, _orient
    from ariadne_mark.video.color import frame_image
    if type(max_frames) is not int or not 1 <= max_frames <= 18000:
        raise ValueError("max_frames must be1–18000")
    if not isinstance(max_seconds, (int, float)) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 3600:
        raise ValueError("max_seconds must be finite and between0 and3600")
    if type(max_hypotheses) is not int or not 1 <= max_hypotheses <= 512:
        raise ValueError("max_hypotheses must be1–512")
    info = probe(path)
    start = time.monotonic()
    observations, logits, timestamps = [], [], []
    counts = Counter()
    complete = False
    reason = None
    direct = None
    with av.open(str(path), format="mp4", options={"protocol_whitelist": "file", "codec_whitelist": "h264,hevc,aac", "enable_drefs": "0"}) as container:
        validate_decoder_streams(container)
        last = None
        for frame in container.decode(video=0):
            if len(observations) >= max_frames or time.monotonic() - start >= max_seconds:
                reason = "frame_or_time_budget"
                break
            if frame.pts is None or frame.time_base is None:
                raise UnsupportedMedia("Blind video search requires timestamps")
            timestamp = float(frame.pts * frame.time_base)
            if not math.isfinite(timestamp) or last is not None and timestamp <= last:
                raise UnsupportedMedia("Non-monotonic blind-search timestamps")
            last = timestamp
            token, values = marker.decode_logits(_orient(frame_image(frame), info["rotation"]))
            if len(values) != 100 or not all(math.isfinite(x) for x in values):
                raise ValueError("Invalid decoder logits")
            observations.append({"time": timestamp, "token": token})
            timestamps.append(timestamp)
            logits.append(values)
            if token:
                counts[token] += 1
                if len(counts) > 1:
                    reason = "conflicting_individual_ids"
                    break
                if counts[token] >= 2:
                    direct = token
                    reason = "two_concordant_ids"
                    break
        else:
            complete = True
    if not observations:
        raise UnsupportedMedia("No decodable video frames within the search budget")
    aggregates, attempts = [], []
    candidates = set(counts)
    aggregate_candidates = set()
    hypotheses_complete = True
    if not direct and len(candidates) <= 1:
        for group in phase_groups(timestamps, max_hypotheses=max_hypotheses):
            if group is None or time.monotonic() - start >= max_seconds:
                hypotheses_complete = False
                reason = reason or "aggregate_budget"
                break
            period, phase, indices = group
            token = marker.aggregate_logits([logits[i] for i in indices])
            attempts.append({"period_s": period, "phase_s": phase, "samples": len(indices), "token": token})
            if token:
                aggregate_candidates.add(token)
                candidates.add(token)
        aggregates = [{"token": t} for t in sorted(aggregate_candidates)]
    # A single individual observation is retained, not promoted to confirmation.
    # An exhausted search is only a bounded negative for this one scheme.
    if len(candidates) > 1:
        status, token = "invalid", None
        reason = "conflicting_ids"
    elif direct or aggregate_candidates and hypotheses_complete:
        status, token = "recovered_claim", next(iter(candidates))
    elif not complete or not hypotheses_complete:
        status, token = "not_checked", None
        reason = reason or "incomplete_search"
    elif candidates:
        status, token = "single_observation", None
    else:
        status, token = "not_found", None
    return {"status": status, "token": token, "samples": observations, "aggregates": aggregates,
            "search": {"reason": reason, "frames_decoded": len(observations),
                       "file_exhausted": complete, "hypotheses_complete": hypotheses_complete,
                       "max_frames": max_frames, "max_seconds": max_seconds,
                       "max_hypotheses": max_hypotheses, "aggregate_attempts": attempts,
                       "phase_bank": "observed_bins_v2", "phase_resolution_s": 1 / 64, "aggregate_window_s": .09375,
                       "observed_ids": sorted(candidates), "expected_id_supplied": False,
                       "signed_profile_or_registry_used": False, "cnn_passes": 1,
                       "whole_video_coverage": "not_established",
                       "detector_calibration": "exploratory_not_population_calibrated"}}
