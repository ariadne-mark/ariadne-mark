# EU voluntary Code implementation map

SDK **0.7.2a1** · source review **2026-11-10**.

Use this map when deciding whether to follow the [Code of Practice](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content)
or substantiate alternative measures. The Commission/AI Board recognises the
Code as an adequate voluntary tool; using Ariadne alone is not signing it or
establishing full adherence. This map covers provider Section 1; deployer
Section 2 needs separate product/UI assessment when applicable.

| Measure | Subject | Available in Ariadne | Remaining action | Status |
| --- | --- | --- | --- | --- |
| 1.1.1 | Signed metadata | C2PA AI source assertion, signed record; current production timestamp policy | Provider identity/TSA and secure key operation | partial implementation + operator |
| 1.1.2 | Imperceptible watermark | TrustMark Q ID on images and selected/per-frame video | Known crop, excerpt and remover limits; evaluate intended content | partial evidence |
| 1.2 | Non-removal | Supported parent ingredient retention for appropriate altered inputs | General upstream marking-only relay is not implemented | partial |
| 2.1.1 | Available detection | Open-source decoder, self-hosted UI/API | Make the route usable by its audience; Linux qualified scope | operator deployment |
| 2.1.2 | Access and signed download | UI/API and JWS report with asset hash, verifier ID/time | Public availability/capacity; pin report key independently | reference verified + operator |
| 2.1.3 | Privacy and security | Transient uploads, reviewed public fields, key/process/network isolation | Actual host/proxy retention and applicable data protection | partial + operator |
| 2.1.4 | Retirement | Legacy schemes remain readable in full media setup | Service continuity/retirement plan and backward support | operator process |
| 2.3 | Clear accessible results | Separate signature/trust/watermark/binding and incomplete states | Accessibility and user-understanding evaluation | partial |
| 3.1 | Effectiveness | Working export-to-detection route | Assess whether intended users can access/understand results | partial |
| 3.2 | Reliability | Scoped clean/positive tests and protocol | Representative held-out error-rate assessment | open measurement |
| 3.3 | Robustness | Versioned ordinary-transform and removal experiments | Spatial/temporal/remover failures; plausible threat assessment | known gaps |
| 3.4(a)-(b) | Standards and public instructions | External c2patool reads C2PA; decoder/API docs | Publish actual access details; public trust is separate | partial |
| 3.4(c) | Detection interoperability by 2027-02-02 | Read-only soft-binding API subset; provisional IDs | Provider-agnostic routing/signpost/shared solution not qualified | open |
| 4.1 | Compliance process | Requirements matrix and operator evidence template | Adopt and maintain the product-specific process | operator |
| 4.2 | Testing and monitoring | Exact-version CI, protocol, retained logs and failure records | Test actual delivery, monitor reported shortcomings, keep updates | shared |
| 4.3 | Personnel training | Technical/operator documentation | Proportionate actual staff training and record | operator |
| 4.4 | Cooperation | Export receipts and source-linked documentation | Responsible contact and authority-response process | operator |

The Code's layered route ordinarily combines signed metadata and imperceptible
watermarking for online visual media. Its timestamp wording does not specify
Ariadne's particular external-TSA gate. Its limited closed-environment cases
are not automatically a justification for sparse public entertainment exports.

Measures marked optional in the source include richer provenance (1.3),
perceptible-mark functionality (1.4), forensic detection (2.2), literacy support
(2.4) and advancing the state of the art (3.5). Do not turn these into universal
statutory requirements. Conversely, calling the Code voluntary does not remove
the underlying Article 50 marking/detection duties.

For existing engineering evidence see the [index](../benchmarks/evidence-index.md).
For independent operation use the [deployment checklist](../operations/production-onboarding.md)
and [operator evidence record](operator-evidence-template.md). The relevant
interoperability milestone belongs to this chosen Code route; the SDK does not
claim universal watermark discovery or C2PA conformance-program completion.
