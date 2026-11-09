"""E1b: BCH5 miscorrection on MARKED Economy video (concrete hypothesis from E1).

E1 observed, on the positive control crowd_economy_5s, 2 of 291 valid random-subset
aggregates decoding to a codeword whose 13-bit prefix is 0x114d instead of 0x14d, i.e. the
canonical BCH5 guard accepted a WRONG codeword (miscorrection) and only the prefix
rejected it. A miscorrected codeword differs from the true one in >= d_min bits; when
none of them hit the 13 prefix bits, a wrong 48-bit ID passes every check.

Question: how often do aggregates of marked + unmarked/weak frames yield a prefix-valid
ID different from the export's token, (a) for random subsets (2..20 frames) and (b) for
the production phase hypothesis bank (what scan_video actually evaluates)?

Positive controls only (expected token from the export receipt, embedded in file name).
Usage: python exp_miscorr.py <positive_dir> <out.jsonl>
"""
import json, random, sys, time, hashlib
from pathlib import Path
import numpy as np
from ariadne_mark.videoq import VideoWatermarker
from ariadne_mark.video.detection import phase_groups
from ariadne_mark.video import probe, validate_decoder_streams, _orient
from ariadne_mark.video.color import frame_image
from ariadne_mark.watermark.canonical import CanonicalBCH5
from trustmark.datalayer import DataLayer
import av

pos_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
log = out.open("a")
def emit(**row):
    log.write(json.dumps(row) + "\n"); log.flush(); print(json.dumps(row)[:600], flush=True)

dl = CanonicalBCH5(DataLayer(100, False, 1))
def decode(words):
    out = []
    for bits, valid, _ in dl.decode_bitstream(np.asarray(words, dtype=np.int64).reshape(-1, 100), MODE="binary"):
        out.append(("%016x" % int(bits, 2)) if valid else None)
    return out

marker = VideoWatermarker(threads=2)
for p in sorted(pos_dir.glob("*economy*.mp4")):
    expected = p.name.split("__")[0]
    info = probe(p); times, L = [], []
    with av.open(str(p), format="mp4", options={"protocol_whitelist": "file", "codec_whitelist": "h264,hevc,aac", "enable_drefs": "0"}) as c:
        validate_decoder_streams(c)
        for f in c.decode(video=0):
            _, lg = marker.decode_logits(_orient(frame_image(f), info["rotation"]))
            times.append(float(f.pts * f.time_base)); L.append(lg)
    L = np.asarray(L, dtype=np.float32)
    def tally(tokens):
        valid = [t for t in tokens if t]
        pref = [t for t in valid if int(t, 16) >> 48 == 0x14D]
        wrong = sorted({t for t in pref if t != expected})
        return {"n": len(tokens), "valid": len(valid), "prefix_valid": len(pref),
                "correct": sum(t == expected for t in pref), "wrong_prefix_valid": len(pref) - sum(t == expected for t in pref),
                "wrong_ids": wrong[:10], "prefix_rejected_tops": sorted({hex(int(t, 16) >> 48) for t in valid if int(t, 16) >> 48 != 0x14D})}
    # (a) production hypothesis bank: Python decoder AND production Node aggregator
    groups = [g for g in phase_groups(times, max_hypotheses=512) if g is not None]
    hyp = decode([(L[list(i)].sum(0) > 0).astype(int).tolist() for _, _, i in groups])
    worker = [marker.aggregate_logits(L[list(i)].tolist()) for _, _, i in groups]
    # (b) random subsets 2..20 frames
    r = random.Random(20261109); mc = []
    for _ in range(20000):
        k = r.randint(2, 20); idx = r.sample(range(len(times)), k)
        mc.append((L[idx].sum(0) > 0).astype(int).tolist())
    mcd = decode(mc)
    # (c) single frames
    fr = decode((L > 0).astype(int).tolist())
    emit(file=p.name, expected=expected, frames=len(times), frames_tally=tally(fr), hyp_tally=tally(hyp),
         hyp_worker={"ids": sorted({t for t in worker if t}), "n_with_id": sum(1 for t in worker if t)}, mc_tally=tally(mcd))
marker.close()
emit(kind="done", utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
