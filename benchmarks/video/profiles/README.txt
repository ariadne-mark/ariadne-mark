Frozen experimental video profile references — 2026-11-04

fast-cpu-v1.json: TrustMark Q sharedResidual, scene threshold .10, max24
frames, strength1. Repeated outputs bit-identical to prior baseline (12/12).

resilient-cpu-candidate-v1.json: TrustMark Q perFrame, strength1. Same
models/payload and detector as fast, a newly calculated signal on every frame.
Candidate selected by added matched-case recovery with no lost fast successes.
It remains provisional until held-out validation.

Selection panel: six known3s720p24 scenes, two IDs each. Fast32/36 vs
perFrame36/36 transforms; correct originals12/12 both. Median export6.21s
vs23.86s. One10s crowds clip:55.13s vs78.20s, CPU2, no GPU. These timings
exclude signing/registry/HTTP and are content-dependent.

These JSON files remain immutable selection references. SDK0.5.0a0 now
implements their settings through CLI --video-profile fast|resilient and
Python SDK(video_profile=...). The JSON itself is not a CLI input.
New integration evidence is docs/validation/0.5.0a0.md. Changes require a new profile version and paired evidence.
90% is only a context annotation, never a legal, release or format cutoff.

Full experiment: project research/profile-selection-2026-11-04/report.html
Protocol, raw logs, all candidates, paired CSV and input/model hashes are there.
Original0.4 SDK VideoSeal/TrustMark payloads need explicit verifier compatibility
when the new reference backend is integrated.
