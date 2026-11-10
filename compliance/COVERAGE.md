# Implementation and operator coverage

Reviewed 10 November 2026 against qualified SDK 0.7.2a1. These 15 records are
engineering/implementation controls, not 15 statutory duties. A component can
be implemented and reference-tested while product deployment or legal acceptance
remains open. The former 8/15 headline is not a readiness or compliance score.

| Control | Component status | Reference evidence | Remaining action |
| --- | --- | --- | --- |
| [REQ-001](../docs/compliance/applicability.md) | implemented | profile/date/scope regressions | Verify real role, geography, dates and exception facts |
| [REQ-002](../docs/implementation/image-marking.md) | implemented | real image/video ID export/read-back | Qualify actual content and transformations |
| [REQ-003](../docs/implementation/provenance.md) | implemented | record validation, future-time guards, system/version scope | Provide truthful public source facts |
| [REQ-004](../docs/implementation/signing.md) | implemented | external C2PA signature/hash/source validation | Production trust/enrollment and lifecycle |
| [REQ-005](../docs/implementation/video.md) | implemented | all three modes, PTS/audio/rotation and read-back gates | Synthetic audio and actual delivery scope |
| [REQ-006](../docs/implementation/recovery.md) | implemented | registry + detached manifest; metadata-only recovery | Permanent operation, restore and edited-copy limits |
| [REQ-007](../docs/implementation/verifier.md) | implemented | HTTPS UI/API, public fields and restart/feedback | Public deployment, accessibility and availability |
| [REQ-008](../docs/implementation/verification-results.md) | implemented | invalid/incomplete/negative/conflicting result regressions | Consumers must interpret evidence within scope |
| [REQ-009](../docs/implementation/disclosure.md) | implemented | visible reference component tested | Disclosure applicability, placement and accessibility |
| [REQ-010](../docs/implementation/provenance-relay.md) | partial | parent ingredient retention for appropriate altered inputs | Marking-only upstream relay semantics remain open |
| [REQ-011](../docs/operations/privacy.md) | partial | reference upload cleanup/minimized output/key isolation | Actual host/proxy processing; no multi-tenant storage claim |
| [REQ-012](../docs/benchmarks/durability.md) | partial | versioned small-corpus protocols/observations | Representative held-out error rates/quality/robustness |
| [REQ-013](../docs/operations/cpu-deployment.md) | implemented | bounded CPU pipeline and failure/publication checks | Product capacity, queue, crash reconciliation and backups |
| [REQ-014](../docs/operations/keys-and-trust.md) | partial | local issuer path/EKU, TSA tests, key-role isolation | Real production identity/TSA, rotation/revocation operations |
| [REQ-015](../docs/operations/releases.md) | partial | artifact manifests, clean installs, source review and docs | Publish exact release and maintain scoped legal/dependency review |

The [machine-readable tracker](requirements.json) retains its earlier broad
acceptance fields and adds explicit technical assessments. New evidence does
not automatically close unmet end-to-end criteria. Use the [legal matrix](../docs/compliance/requirements-matrix.md)
for binding law versus voluntary Code versus SDK policy, and the
[actual qualification record](../docs/validation/0.7.2a1-results.md) for exact
artifacts/tests. Known failures, operator duties and out-of-scope modalities remain
visible. No checkbox total certifies a product.
