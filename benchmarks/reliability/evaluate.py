"""E1: false-positive structure of the 0.7.1a1 blind video search on clean content.

Question: the blind search accepts an ID from ONE aggregate of <=20 frames among up to
512 phase hypotheses (video/detection.py:124). Its safety rests on the canonical BCH5
check plus the fixed 13-bit 0x14D prefix. Is the acceptance rate on real clean content
consistent with the random-bits model, or do clean frames/aggregates decode to valid
codewords far more often (structured false positives)?

Runs inside ariadne-mark:0.7.1a1-runtime-candidate, --network none, 2 CPU / 6 GiB.
Usage: python exp_fp.py <clean_dir> <positive_dir> <out.jsonl>
  clean_dir:    unmarked MP4s (stock + synthetic), prepared by prepare_inputs.sh
  positive_dir: SDK 0.7.1a1 exports (positive control for this analysis path)
The expected ID is never given to the scanner; positives are scored afterwards from
the export receipt token in the file name (<token>__*.mp4) where available.
"""
import json, math, random, sys, time, hashlib, platform
from pathlib import Path
import numpy as np

from ariadne_mark.videoq import VideoWatermarker
from ariadne_mark.video.detection import phase_groups
from ariadne_mark.video import probe, validate_decoder_streams, _orient
from ariadne_mark.video.color import frame_image
from ariadne_mark.watermark.canonical import CanonicalBCH5
from trustmark.datalayer import DataLayer

clean_dir, pos_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
log = out.open("a")
def emit(**row):
    log.write(json.dumps(row) + "\n"); log.flush(); print(json.dumps(row)[:400], flush=True)
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

import importlib.metadata as md
emit(kind="env", python=platform.python_version(), ariadne=md.version("ariadne-mark"), trustmark=md.version("trustmark"),
     av=md.version("av"), utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

dl = CanonicalBCH5(DataLayer(100, False, 1))
PREFIX = 0x14D
def py_decode(sign_bits_list):
    """Return list of (valid_any_prefix, valid_with_prefix, top13) per packet."""
    rows = dl.decode_bitstream(np.asarray(sign_bits_list, dtype=np.int64).reshape(-1, 100), MODE="binary")
    res = []
    for bits, valid, schema in rows:
        if valid:
            v = int(bits, 2); top = v >> 48
            res.append((True, top == PREFIX, top))
        else:
            res.append((False, False, None))
    return res

# Baseline: uniformly random 100-bit words through the same canonical decoder.
rng = np.random.default_rng(20261109)
t0 = time.monotonic(); N0 = 200_000; valid0 = pref0 = 0
for start in range(0, N0, 5000):
    batch = rng.integers(0, 2, size=(5000, 100))
    for v, p, _ in py_decode(batch.tolist()):
        valid0 += v; pref0 += p
emit(kind="baseline_uniform", n=N0, valid_any_prefix=valid0, valid_prefix=pref0, seconds=round(time.monotonic() - t0, 1))

marker = VideoWatermarker(threads=2)

def frame_logits(path, limit=240):
    info = probe(path)
    import av
    times, logits, tokens = [], [], []
    with av.open(str(path), format="mp4", options={"protocol_whitelist": "file", "codec_whitelist": "h264,hevc,aac", "enable_drefs": "0"}) as c:
        validate_decoder_streams(c)
        for f in c.decode(video=0):
            if len(times) >= limit:
                break
            tok, lg = marker.decode_logits(_orient(frame_image(f), info["rotation"]))
            times.append(float(f.pts * f.time_base)); logits.append(lg); tokens.append(tok)
    return times, np.asarray(logits, dtype=np.float32), tokens

def analyse(path, kind, expected=None):
    t = time.monotonic()
    scan = marker.scan_video(path)  # production path, blind
    scan_s = time.monotonic() - t
    s = scan["search"]
    emit(kind="scan", set=kind, file=path.name, sha256=sha(path), status=scan["status"], token=scan["token"],
         correct=(scan["token"] == expected) if expected else None, reason=s["reason"],
         frames=s["frames_decoded"], hypotheses=len(s["aggregate_attempts"]), hyp_complete=s["hypotheses_complete"],
         observed_ids=s["observed_ids"], seconds=round(scan_s, 1))
    times, L, tokens = frame_logits(path)
    signs = (L > 0).astype(int)
    fr = py_decode(signs.tolist())
    # Production hypothesis bank, evaluated both by the production Node aggregator and our Python decoder.
    groups = [g for g in phase_groups(times, max_hypotheses=512) if g is not None]
    agg_words, worker_tokens = [], []
    for _, _, idx in groups:
        tot = L[list(idx)].sum(axis=0)
        agg_words.append((tot > 0).astype(int).tolist())
        worker_tokens.append(marker.aggregate_logits(L[list(idx)].tolist()))
    hr = py_decode(agg_words) if agg_words else []
    # Monte Carlo: random subsets (size 2-20) within the same clip -> correlated, realistic aggregates.
    mc_words = []
    r = random.Random(sha(path))
    for _ in range(4000):
        k = r.randint(2, min(20, len(times)))
        idx = r.sample(range(len(times)), k)
        mc_words.append((L[idx].sum(axis=0) > 0).astype(int).tolist())
    mr = py_decode(mc_words)
    # Fraction of near-identical sign words across frames (low diversity => correlated trials).
    uniq = len({tuple(w) for w in signs.tolist()})
    flips = float(np.mean(np.abs(np.diff(signs, axis=0)).sum(axis=1))) if len(signs) > 1 else None
    emit(kind="analysis", set=kind, file=path.name, frames=len(times), unique_sign_words=uniq, mean_bitflips_between_frames=flips,
         mean_abs_logit=float(np.mean(np.abs(L))),
         frame_valid_any=sum(v for v, _, _ in fr), frame_valid_prefix=sum(p for _, p, _ in fr),
         frame_worker_tokens=sorted({x for x in tokens if x}),
         hyp_n=len(hr), hyp_valid_any=sum(v for v, _, _ in hr), hyp_valid_prefix=sum(p for _, p, _ in hr),
         hyp_worker_tokens=sorted({x for x in worker_tokens if x}),
         mc_n=len(mr), mc_valid_any=sum(v for v, _, _ in mr), mc_valid_prefix=sum(p for _, p, _ in mr),
         valid_tops=sorted({hex(t) for _, _, t in fr + hr + mr if t is not None})[:20],
         expected=expected)

for p in sorted(pos_dir.glob("*.mp4")):
    expected = p.name.split("__")[0] if "__" in p.name else None
    analyse(p, "positive_control", expected)
for p in sorted(clean_dir.glob("*.mp4")):
    analyse(p, "clean")
marker.close()
emit(kind="done", utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
