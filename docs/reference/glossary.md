# Terms and evidence boundaries

SDK **0.7.3a2 candidate** · documentation updated **2026-11-14**.

Versioned benchmark and legal-source review dates below remain historical evidence;
they are not a new qualification or legal approval of this candidate.

| Term | Meaning in this toolkit |
| --- | --- |
| Marking | Adding a machine-readable indication to an output |
| Watermark | An imperceptible signal embedded in visual samples, carrying a recoverable ID |
| C2PA credential | Signed manifest/assertions bound to an asset; not proof that every assertion is factually true |
| Provenance | Claims about origin and history; separate from factual truth, consent and ownership |
| Issuer trust | Validation against a configured trust policy; mathematical signature validity alone is different |
| Provider key | Signs content credentials; mounted only by the exporter |
| Report key | Signs the verifier's result; distinct from content and TLS identities |
| TSA | Timestamp authority used under the current production signing policy |
| Registry | Operator-owned ID/record/manifest associations; not a global discovery service |
| Soft binding | A recoverable association through a watermark, distinct from cryptographic file binding |
| Metadata-only recovery | Recovery after tested metadata removal without re-encoding media; broader edits need separate evidence |
| Economy | Fresh marking on selected 125 ms windows, with 5 s or 2 s periods |
| Resilient | Fresh per-frame marking; five-position export read-back, not an unremovable mark |
| Negative | Scoped completed detection with no supported mark; does not establish human creation |
| Incomplete | Operational/budget/engine limit; not evidence of absence |
| Robustness | Performance under stated transformations/threats, with parameters and failures reported |
| Compliance mapping | Connection between an applicable norm, technical measure, evidence and operator action |
| Qualification | Exact-version engineering checks within a stated scope; not product-wide legal approval |

Ariadne detects supported markings, not every AI-generated file. Unknown
provider watermarks require their own detectors. No universal confidence score
is calibrated across engines. See [verification results](../implementation/verification-results.md).
