# Changelog

## 0.7.1a1 — C2PA runtime and release-documentation candidate

- Check the actual loaded native C2PA version/path/hash and wrapper pin at media startup; mismatch fails closed with actionable diagnostics.
- Add `ariadne runtime check`; supplied verifier probes its child before HTTP binding, and low-level inspection distinguishes an unsupported runtime from absent/forged evidence.
- Synchronize current guides and document short-clip, excerpt and remover limitations. Historical records remain unchanged.
- Preserve all marking modes, model/payload/strength/cadence and native pins; server-only targeted media rechecks recorded separately.

## 0.7.1a0 — color, fractional FPS and decoder hardening candidate

- Explicit SDR matrix/range on export and read-back; accurate rounding removes conversion-only luma bias; YUV bypass retained for Economy.
- Bounded, timestamp-based unknown-phase bank completes on NTSC rates; narrower recovery windows handle phase quantization.
- Canonical BCH5 re-encode/distance checks around pinned Python and Node decoders, without changing payloads, models, cadence or strength.
- Server-only Linux qualification, before/after identity exports and real fractional-rate transforms logged; ready crop/letterbox approaches documented separately.

## 0.7.0a0 — signed reports and C2PA recovery

- Signed verifier JWS reports, immutable exact C2PA manifests and explicit read-only recovery API; native C2PA 0.91.11.
- Qualified installed wheel on Linux x86-64, 156 tests, zero skips. See the versioned validation record.

## 0.6.0a0 — Economy and verifier launch candidate

- Default Economy5s, configurable Economy2s and per-frame Resilient in one wheel; config, CLI and per-export API selection.
- PTS windows, selected-frame bypass, per-window export gates, AAC/VFR/rotation and read-back failure isolation.
- One-pass blind search with cached-logit recovery and explicit partial/incomplete/conflicting evidence.
- Verification-only service subprocess, total model deadline, process-group cleanup and restart after timeout/crash.
- Packaged verifier UI, OpenAPI, anonymous aggregate feedback and reviewed public-source output controls.
- Operator registry resolver, deployable Compose/TLS-edge recipes and privacy/data-handling documentation.
- Rechecked EU/California primary sources plus conditional Connecticut/New York navigator; known temporal-removal limitation is explicit.

## 0.5.3a0 — external-review follow-up candidate

- Fresh-export sample gate and anchor-aware Fast v2 refresh; motion can reduce the speed advantage.
- Total HTTP header deadline, stricter production CA configuration and development-signature headlines.
- Scoped image negatives without Node; actual PyAV decoder-context validation.
- Hash-locked bootstrap/full CPU dependency graph; npm scripts disabled and native ONNX integrity receipts.
- Bundled PyAV binary inventory, upstream notices and corrected statutory transition source type.


## 0.5.2a0 — release-readiness candidate

- Explicit SHA-verified upstream C2PA 0.38.3/native 0.91.7 bootstrap; pip 26.3 and patched adm-zip dependency policy.
- Multi-stage runtime with Node 24 and no npm/build toolchain in the final image.
- Temporary decoder cleanup, non-retaining exit handlers and startup trust-file validation.
- H.264/HEVC/AAC decoder allowlist for supported MP4 inputs.
- California source catalog reconciled to official consolidated/chaptered text; partial-coverage statements retained.


## 0.5.1a0 — audit follow-up

- Bounded upload slots/deadline separated from inference; production trust configuration and strict CLI verification.
- Clear unverified-issuer, expired-credential, registry-ID binding and partial video-sample results.
- Trusted timestamp expiry regression; custom roots preserve C2PA/TSA defaults.
- Registry and fsynced receipt precede media publication; process-death regressions; read-only verifier registry.
- 512 MiB export/upload alignment, pinned MP4 demux, explicit ICC conversion and credentialed-input action handling.
- Test product supports both video profiles and bounded worker retries.

## 0.5.0a0 — 2026-11-04

- Fast and Resilient CPU video profiles, persistent binary Node/ONNX bridge.
- Explicit runtime/model provisioning with integrity checks, separate video extra.
- New payload routing and bounded 5→20 sample verification; legacy decoding retained.
- Shared exporter preserves AAC, PTS, duration and rotation; signed profile identifier and per-export statistics.
- Lazy image models, concurrent export isolation, wheel/Docker and real-media validation.


## 0.2.0a0 — Developer preview

- Local CPU TrustMark-Q image and video watermarking, pinned model hashes and explicit setup.
- C2PA ES256 signing/read-back, created/altered provenance, parent ingredients and separate issuer trust.
- Timestamp-preserving H.264 export, VFR/rotation handling and AAC remux; synthetic audio is declared but not independently watermarked.
- Optional SQLite recovery registry, JSON receipts and visible disclosures.
- CLI, Python API, Docker/Compose and self-hosted upload/API verifier without accounts.
- Real-engine tests and a reproducible durability/performance smoke benchmark.
- Explicit scope and legal mapping limitations; no automatic compliance verdict.

## 0.1.0a0 — SDK core

- Installable dependency-free provenance/result contracts and strict JSON parsing.
- Python 3.11–3.14 tests, 15 requirement records and traceability CI.
- Contribution, security and community guidance.
