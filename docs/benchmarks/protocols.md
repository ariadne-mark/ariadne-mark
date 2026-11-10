# Reproduce and interpret marking verification tests

SDK **0.7.2a1** · documentation review **2026-11-10**.

Use these protocols for a versioned SDK release or a product-specific delivery
chain. Run SDK/model/media work on the designated Linux test server; do not run
it on the maintainer Mac. Record exact inputs, software and failures before
summarising results. A procedure below is not a claim that a new campaign ran.

## Common record

Use the [result schema](results.schema.json) or an equivalent documented record.
Every run needs SDK version/tested commit and artifact hashes; machine/OS/CPU,
CPU/memory limits, threads, wrapper/native/FFmpeg/Node/model hashes; dataset and
licence/source manifest; start/end UTC; commands/config; operator and protocol.
Each observation needs source/output hashes, duration/dimensions/FPS/codec,
profile/ID, transform parameters, outcome and raw-log reference. Omit identifiers
of real users. Keep raw media/keys outside public source/evidence archives.

Dataset units are distinct source assets. Multiple IDs, edits, frames or phase
hypotheses of one source are dependent observations, not independent originals.
Never discard failures or count an incomplete scan as a negative. If a container
or disk limit aborts processing, classify it as operational/incomplete.

## P1 Release and installation qualification

The trusted maintainer runs [server CI](../operations/server-ci.md) for the exact
reviewed SHA. [`scripts/ci_server.sh`](../../scripts/ci_server.sh) builds and tests
the installed wheel, Python core matrix, fresh installs, offline processing,
kit deployment, source/package parity, inventories and artifact hygiene.

```sh
# On the designated EC2 host, in the reviewed checkout with prerequisites.
bash scripts/ci_server.sh
```

This may provision downloads during explicit build/setup. Processing tests use
bounded offline containers. The maintainer-dispatched workflow records commit,
CI run and artifacts. Do not run untrusted public-fork code on the test host.
[0.7.2a1 results](../validation/0.7.2a1-results.md) are an executed example.

## P2 Cadence and fresh-output gate

Use the same supported, unmarked input for all profiles. For a 6 s/12 fps fixture,
expect 72 encoded frames, Economy5s occupied windows `[0,1]`, Economy2s `[0,1,2]`,
and full-frame Resilient. For 10 s/24 fps, nominal selected counts are 6, 15 and
240 respectively. These are specific timelines, not constant percentages.

Use exact PTS, including fractional FPS/VFR/nonzero origins. Confirm output frame
count, timing, audio and display rotation. Check receipt `watermark_windows`,
`marked_frames`, `frames_encoded`, profile and read-back evidence. Economy requires
a decoded matching ID in each occupied scheduled window. Resilient uses five
uniform read-back positions; this does not inspect every frame at export.
Inject missing/incorrect later-window evidence and require no final publication.
A blind verifier must not receive the expected ID, schedule, registry hint or
signed profile as a shortcut to detection; use those only for post-run scoring.

Current regression entry points include
[Economy integration](../../tests/integration/test_economy.py),
[PTS policy](../../tests/video/test_economy_policy.py),
[fractional search](../../tests/video/test_fractional_search.py) and
[installed kit acceptance](../../scripts/ci_kit_acceptance.py).

## P3 Nominal delivery and robustness

Prepare final landscape/portrait renditions before marking. Keep a fresh marked
control and an unmarked control for each source. Test each mode separately.
Report transformations individually, with exact parameters:

- Metadata-only PNG re-save and MP4 remux: distinguish this from pixel/codec edits.
- JPEG quality and scaling; H.264 CRF/resolution changes used by the product.
- Native portrait exports separately from landscape-to-portrait crop/letterbox.
- 23.976/24/25/29.97/30/50/60 fps or actual supported product rates, plus relevant VFR.
- Short exports, leading trims and excerpts inside and between Economy windows.
- Ordinary compositing, overlays and sharing/platform download paths when relevant.

Use original and transformed IDs only for scoring after a blind scan. Record
correct ID, wrong ID, no ID, invalid credential and incomplete independently.
C2PA hash mismatch after editing is distinct from failure to recover a watermark.
An ID copied to another asset is not authenticated source attribution. Registry
association, recovered-manifest signature and current asset binding are separate.

Actual 0.7.2a1 acceptance proves metadata-only recovery, not arbitrary re-encoding
or crop survival. Historical [short/remover observations](../validation/0.7.1a1.md)
retain their original release scope. The old [durability harness](../../benchmarks/durability/README.md)
and [VideoSeal harness](../../benchmarks/video/README.md) are historical tools;
the latter is not a current Economy benchmark.

## P4 Reliability and clean negatives

Use a held-out representative clean corpus, marked positives and, where useful,
other-provider or legacy-scheme controls. Include variety in content, duration,
resolution, motion, texture and semantics. Preserve a source-level split; do not
select only assets known to work. Record available decoder scope and budgets.

For complete, applicable checks, report correct recoveries over marked assets,
false detections over known unmarked assets and wrong-ID attributions separately.
Also report the count of incomplete/unsupported assets against all attempted
assets. Do not remove them silently from denominators. Only report FPR/FNR when
the ground truth, scope and denominator justify those terms; report confidence
intervals only with an appropriate independence/sampling justification.

[Reliability research](../../benchmarks/reliability/README.md) includes executable
production-Node observations and auxiliary Python/random-word analyses. Auxiliary
hypotheses are not new independent videos or production-detector calibration.
Zero recovered IDs in 22 selected clean clips does not establish a population FPR.

## P5 Plausible removal and tampering

Assess relevant threats separately from ordinary delivery: upstream public
remover, scheduled-frame replacement, temporal/spatial edits, ID copying and
conflicting/mixed-ID content. Log the algorithm/version and attacker budget.
Use an identity-transform control with the same decode/encode/metadata policy
so losses are not incorrectly attributed to removal. Retain both successes and
failures, including the cost of the attack. No attack-proof claim follows from a
small matrix. The early-stop verifier is not a whole-video mixed-source audit.

## P6 Performance and resource use

Measure the same source files/settings on one idle qualified machine, with modes
run sequentially. Separate setup/downloads, cold process/model startup, resident
worker export, positive verification, negative full scan and optional recovery.
Time the complete `SDK.mark()` call externally; receipt timing alone need not
include every caller/preflight stage. Record exactly which stages each timer covers.

Keep cold and warm results separate. State warm-up procedure and repetitions;
for a new comparison, predeclare at least 3 cold and 5 warm runs per source/mode
as an engineering protocol choice, not a legal threshold. Preserve individual runs
and report medians/spread, not only a favourable average. Existing two-repeat
results remain two-repeat results.

Record wall seconds, cgroup CPU usage delta and container memory peak. Use the
container's `cpu.stat`/`memory.peak` on cgroup v2 (or equivalent documented host
collector); take counters while the container still exists. `time docker run`
measures the Docker client, not container CPU/RSS. A `docker stats` sample is an
observed snapshot, not a guaranteed peak. Python self-RSS excludes Node/FFmpeg
and concurrent child processes; do not sum separate peak RSS values as if
simultaneous. Mark unavailable metrics null, never zero.

Report real-time factor as export wall/video duration, output size/codec/quality,
threads and concurrency. A positive early-stop verification and an unmarked full
scan have different costs. Measuring one does not establish service throughput.
For stage profiling, record decode, conversion, model, encode/remux, signing/TSA,
read-back and registry/publication without double-counting overlapping stages.

## P7 Product deployment acceptance

Verify a newly installed kit, not just an existing source checkout. Check HTTPS
from outside the host, actual product/CDN downloads, independently pinned report
verification, public-source output, upload cleanup, rate/capacity behavior,
feedback, restart and backup restore. Keep development-credential qualification
separate from real issuer/TSA/public TLS operation. Record in the
[operator evidence template](../compliance/operator-evidence-template.md).

## Acceptance and reporting

Export fail-closed gates are deterministic SDK controls. A scenario annotation
such as 90% may highlight a limitation but must not silently reject a mode,
remove observations or become a statutory pass mark. Set product acceptance
criteria from its scope and threat/delivery model. Publish version, machine,
denominators, transformations, incomplete results and known failures beside
any performance or recovery claim. See the [evidence index](evidence-index.md).
