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
