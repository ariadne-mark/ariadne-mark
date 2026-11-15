# CJ-05 reference measurement harness

Measured on 2026-11-15, installed SDK 0.7.3a4. See the
[versioned results](../../../docs/benchmarks/0.7.3a4-performance-2026-11-15.md)
for corpus, scope, cold/warm repeats and complete resource definitions.

The reference files are byte-identical copies from the sealed experiment;
`REFERENCE_SHA256.json` identifies each one. They include fixture preparation,
the frozen primary observer/worker/campaign, mixed/idle controls and data analysis.
No keys, registry, models, media or SSH credentials are included.

These are experimental drivers, **not a ready-to-run SDK integration example**.
The captured defaults name the owned test workspace and its provisioned Docker
image/legacy cache. To reproduce elsewhere, inspect and adapt those paths to a
new owned workspace; retain the image/runtime/legacy-model identities, UID,
2 vCPU/4 GiB limits and shared qualification lock. Provision dependencies/models
before timing. Generate new development credentials and regenerate the inputs
from the captured commands; output IDs/timestamps will differ.

Run instrumentation calibration before collecting timings: cgroup v2 must support
the same-FD `memory.peak` reset/read method. Then freeze the adapted source hashes
before execution. Do not run another build/media job alongside the measurements.
Keep failures/incomplete scans. Analyze only after all timed sessions stop.

This separately frozen campaign uses cold n=1 and warm n=3 per matrix cell;
the 60-second budget probe uses one cold and one warm observation. It does not
estimate cold-start variance or production tail latency. Raw per-operation
records and 100 ms timelines were retained in the maintainer's sealed evidence
archive (SHA-256 `85e714d18cba75553d39e96537d3cb00ae14196bbd8532f67c8cb1bfd1f1ec90`).
The published CSV/outcome files are the readable per-operation evidence.
