# External review disposition — 5 November 2026

Priority order: Fast/fresh export and header deadlines; development trust and
actual decoder; image scope; hash-locked provisioning; documentation/traceability.
See [0.5.3 candidate validation](../validation/0.5.3a0.md).

| Review item | Disposition |
| --- | --- |
| P1-1 through P1-6 | Implemented in 0.5.3 candidate; exact-revision media/CI qualification required before release. |
| P2-1 | Covered by P1-6 fresh-output sample gate; no claim every frame was checked. |
| P2-2 | Open: configurable staging outside public output and safe orphan reconciliation. Current adjacent staging and serving constraints documented honestly. |
| P2-3 | Open: process-level inference deadline/isolation; Node requests already have a deadline, but Python legacy inference needs a separate bounded worker design. |
| P2-4 | Dead-worker descriptors explicitly closed; stderr discarded instead of unbounded accumulation. Fork-with-held-lock remains unqualified: create SDKs after forking. |
| P2-5 | Native binary hashes in provisioning receipt, checks before worker load, npm scripts disabled. This detects drift from provisioning; it is not protection if an attacker can rewrite both code and receipt. |
| P2-6 | Distinct not-provisioned message; all-engine provisioning skips absent optional Python engines. Explicitly selected missing engines still fail. |
| P2-7 | Documented: a video-only installation cannot make a negative across uninstalled legacy schemes. |
| P2-8 | Notices included in own wheel, separate PyAV binary inventory, bundled venv/container GPL considerations explicit. |
| P2-9 | Optional CORS remains a product feature; same-origin default and server-client API documented. |
| P2-10 | Verifier size limit and source archive Dockerfile corrected. Historical branch names are not product behavior. |
| P2-11 | JSON record_scope explicitly classifies development/untrusted/trusted signer claims. It does not authenticate factual content. |
| P2-12 | Package description uses labeling/provenance wording. |

Legal metadata: statutory Article 111(4), voluntary Code 3.4(c), California
exception-section reference and licensing-workflow details corrected. The full
Article 50 Guidelines assessment remains a separate source-review task.

## 0.6 follow-up

The CLI public verifier now has a verification-only child process and whole-job
deadline, including process-group cleanup/restart tests, addressing the supplied
service path of P2-3. Direct synchronous `SDK.verify` and custom in-process
`make_server` embeddings remain explicitly outside that process boundary.
The final Article50 Guidelines sections4.2.1–4.2.3 were reviewed for the launch
map. Sparse-window adversarial removal is a documented limitation, not a closed
robustness/legal finding. Other open items above are not silently closed.

## 0.7 review follow-up — 6 November 2026

Work is isolated from the running preview services. All new execution/tests and
media generation are on the Oregon EC2 host; original review files on the Mac
are read-only inputs. See `docs/validation/0.7.1a0.md` for exact qualification.

| Priority | Finding | Disposition / release implication |
| --- | --- | --- |
| P1 | RGB conversion changes marked-frame color/luma | Explicit source matrix/range, accurate rounding/full chroma, consistent read-back and preserved encoder tags; identity-marker and FFmpeg-reference tests isolate the conversion from model residuals |
| P1 | Fractional FPS exhausts phase hypotheses | Deterministic bounded observed-phase bank, documented resolution/window and unknown-phase tests; budgets and honest incomplete verdicts retained |
| P1 | Pre-fix upstream BCH can accept noncanonical words | Instance-local Python guard and Node guard re-encode decoded BCH5 data and enforce correction radius; exact codecs tested with correctable errors and deterministic false-valid controls |
| P1, scope | Extreme portrait crop and letterbox lose recovery | Ready approaches researched; FFmpeg cropdetect feasibility probe kept separate from qualified SDK. No claim these transforms are now supported |
| P1, claims | Resilient is not attack-proof; Economy windows can be removed | Preserve engineering preset names/cadence. Publish measured transformation scope and limitations; no bulletproof/compliance certification claim |
| P2 | Early stop finds an ID before later mixed-ID segments | Explicit observed-evidence/whole-video-coverage limits retained. Whole-asset mixed-source audit is a separate endpoint/mode, not established by current verifier |
| P2 | Long negative videos hit frame/time ceiling | Expected bounded `not_checked`; operators can raise scan budgets in their trusted queue. Do not remove public-service resource limits |
| P2 | Detector FPR and geometry search calibration | Canonical validation is not population calibration. Large held-out clean-content assessment remains open |
| P2 | Dependency/packaging simplification | No unmeasured engine replacement. Future official ONNX-only path and one media stack require their own interoperability/performance/license qualification |
| Operator | Production issuer credentials, trust enrollment, TSA, hosting/privacy | Deployment checklist remains necessary; a development build does not supply a public trusted identity or certify legal compliance |

Do not count a review disk-full export failure as a watermark failure. Deduplicate
matrix snapshots before deriving benchmark denominators. Native portrait exports
and post-export portrait crops must remain distinct.

## 0.7.1a1 runtime/documentation follow-up

- Native drift: actual loaded file, mapped identity, wrapper/native version and
  pinned SHA-256 are checked before media/service startup. Wrong builds fail
  closed; low-level inspection reports `not_checked`. No implicit repair.
- Current entry guides and version references are synchronized; historical
  validation records retain their original environments and versions.
- Short/excerpt and public-remover results are rechecked on qualified Linux
  using paired identity-transcode controls. All presets/defaults are retained.
  Measured temporal/removal limits are documented, not marked technically solved.

See [0.7.1a1 validation](../validation/0.7.1a1.md) for the recorded scope.
