# Changelog

## 0.7.3a3 (candidate, not published)

- Complete authenticated RFC 3161 timestamps on the unchanged pinned C2PA pair via a per-operation loopback relay and owner-only bearer file.
- Bound credential reads, requests/replies and response time; reject redirects and preserve native token/trust validation and fail-closed publication.
- Add offline authenticated HTTPS TSA, kit-configuration and relay regressions; document deployment and the remaining live-provider qualification.
- Preserve Economy5s default, Economy2s and Resilient, including 0.7.3a2 verifier, installation and shared-worker fixes.

## 0.7.3a2 (candidate, not published)

- Trusted C2PA claims can no longer switch off the operator's primary watermark scan; out-of-scope claims keep primary evidence and stay `not_checked` on a negative (review P-01). `completed_schemes` ⊆ `declared_schemes`, new `supplemental_completed_schemes` (P-02). `SDK.mark` refuses an encoder outside its own verification scope (P-03).
- One Node video worker per SDK for all presets: mixed-preset peak resident memory 2.44 → 1.33 GiB on the qualification host (ISS-12).
- Kit pins the SDK image by immutable ID (`pin-image.sh`, `ariadne runtime identity`) and refuses a mismatched SDK version before work (ISS-05/01). `kit serve --host/--port`, loopback by default on hosts (ISS-09). Production origins reject all RFC 2606/6761 reserved names (ISS-16).
- Runtime caches honour `XDG_CACHE_HOME`; existing caches are reused, never moved; no `~/.npm` writes (ISS-08).
- TSA URL must be HTTPS without credentials/query/fragment; failed timestamp calls are redacted and publish nothing; `sign_file` removes a failed output. Direct native TSA authorization is unavailable; the optional authenticated relay is added in 0.7.3a3.
- Docs: disk budget, image identity, host bind, mixed-preset memory, verification cost, TSA boundary.

## 0.7.3a1 (candidate, not published)

- Prevent untrusted C2PA claims from suppressing independent watermark scans.
- Report format-specific negative scope, required-decoder failures and tri-state signed-ID observations.
- Refuse unsupported/incomplete content resolver searches; clarify UI observation positions.
- Auto-select current models for bare commands, preserve strict explicit setup and warn on legacy-kit migration.
- Update active candidate documentation while retaining historical benchmark evidence.

## 0.7.3a0 — candidate, not published

- Default model provisioning and source Docker build use current image/video models only; legacy VideoSeal remains explicit.
- Add declared operator scope (`all` / `current`) through SDK, CLI, isolated worker and kit; preserve incomplete results for unavailable required techniques.
- Add finite directional Python-Q video decoder compatibility for signed-manifest recovery; crypto and token checks remain mandatory.
- Show single-ID positions/scope and independent `signed_id_observed`; development signatures retain incomplete watermark wording.
- Missing video-mode choice blocks profiled video export; optional selection rationale is recorded. Direct SDK default remains Economy5s; all three modes/cadence/strength are preserved.
- [Migration, known issues and evidence boundaries](docs/operations/release-0.7.3a0.md).

- Include the legal requirement matrix CSV in source distributions; verify documentation/UI from the extracted sdist.

### Schema-2 verifier block

- Verification report `schema_version` 2: several distinct watermark IDs give `watermark.status=multiple_ids` with every ID in `watermark.ids` (scheme, basis, observed positions) instead of a general `invalid`. No ID is preferred; a genuinely invalid C2PA signature is still `invalid`.
- Observations record integer PTS/time base, scheme and pass; one decoded frame read twice never counts as two confirmations. `watermark.evidence_scope` states what each pass examined. Search order, frequency and budgets are unchanged.
- Registry recovery and `/matches/byContent` work per confirmed ID; `recover --id` selects one ID after detection. CLI `verify` exits 0 only for `recovered_claim`/`not_found`.
- Apply `/matches/byContent` result limits after public/scheme filtering; label unconfirmed ID evidence without implying a single-frame read.
- Export gate unchanged: Economy known-window and Resilient/legacy sample read-back, ID/record checks and no publication on failure.

## 0.7.2a1 — external-review follow-up

- Reject generation timestamps over five minutes in the future at batch/export/signing boundaries; parsing external claims remains possible.
- Check production issuer chains against configured roots with C2PA signer EKUs; local checks remain distinct from enrollment and production readiness.
- Preflight MP4 audio declarations across the batch before any export; explicitly document one system/version per kit.
- Headline incomplete negative checks as `Check incomplete`, preserving invalid/positive evidence.
- Separate California chapter commencement and supported-amendment dates.
- Extend acceptance fixtures to six seconds and assert distinct Economy schedules and full-frame Resilient coverage.
- Clarify tested metadata-only recovery and retain the full-range 4:4:4 chroma, crop, short-excerpt and remover limitations.
- Preserve all three profiles, default Economy5s, cadence, payload, models, strength and native-runtime pins.

## 0.7.2a0 — SDK / verifier / registry deployment kit

- Add explicit kit init/check/render/export/serve commands, batch SDK reuse and operator-owned Compose deployment.
- Separate provider, verifier-report and edge TLS keys; registry is read-only in the verifier; production init generates no fake credentials.
- Add pinned TLS edge, reviewed public provenance configuration, persistent recovery and feedback, and end-to-end server acceptance.
- Preserve model, payload, strength, all video modes and Economy5s default.
- Add decoder-stride and startup-warning regressions, video lock composition check, stable source-archive instructions and accurate CI policy.

## 0.7.1a2 — public-alpha review fixes

- Preserve full-range YUV420 sample values on Economy bypass frames; explicit encoder format avoids implicit range squeeze. Add per-frame contrast/plane regressions.
- Reject 10/12/16-bit decoded input rather than silently quantizing unsupported SDR.
- Add explicit wheel-based `setup media` / `setup video` with packaged hash locks and the unchanged native C2PA bootstrap.
- Keep core SDK construction lazy; media methods and service startup enforce runtime qualification.
- Legacy single-frame results remain `single_observation`; CA planning surfaces reviewed public provenance configuration; verifier startup reports withheld fields.
- Document upstream-C2PA relay limits and measured detector scope; maintainer-dispatched CI runs SDK tests on a temporary EC2 runner only.

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
