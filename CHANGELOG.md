# Changelog

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
