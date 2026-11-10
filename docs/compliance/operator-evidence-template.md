# Record your product implementation and remaining actions

SDK **0.7.2a1** · source review **2026-11-10**.

Copy this template into your product's internal release evidence. Replace
bracketed entries with actual facts; an unchecked item is an action, not a
passing declaration. Do not publish private keys, user uploads or personal data.

## Owner and applicability

- Product, provider organisation and accountable owner: [fill]
- Generative system name/version; SDK version and exact artifact hashes: [fill]
- EU/California role and geographic scope; rationale: [fill]
- First market-placement date and relevant operative provision: [fill]
- Any exception relied on, its factual grounds and reviewer/date: [fill]
- Chosen EU Code/alternative route and scope of assessment: [fill]

## Content and export scope

- Modalities: [JPEG/PNG, supported SDR MP4, audio assessment]
- Duration, size, FPS, codecs, colour/rendition boundaries: [fill]
- All export/download/API paths using marking, including failures/retries: [fill]
- Profile per content class and rationale: [fill]
- Final crop/resize/overlay completed before marking: [evidence]
- Upstream C2PA input handling: [fill]

An upstream already-credentialed AI output is not automatically supported as a
marking-only relay: the current API requires appropriate altered/parent semantics.
Do not label a provenance-only operation as a new AI alteration without review.
The initial self-generated/final-rendition workflow avoids making that claim.

## Production controls

- [ ] Provider identity/trust supplied; keys protected; no development identity.
- [ ] TSA policy/configuration and actual trusted signing-time check recorded.
- [ ] Public TLS/DNS, verifier entry point and product link tested as applicable.
- [ ] Reviewed public organisation/system fields; no end-user identifiers.
- [ ] Registry persistence, restore plan, feedback and monitoring owner assigned.
- [ ] Proxy/host logs and deployment privacy notice reviewed.
- [ ] Applicable in-app disclosure wording, placement and accessibility checked.
- [ ] Signing/report-key rotation, revocation and detection continuity documented.

Record local `kit check --runtime` and profile output. They do not establish
endpoint reachability, training, accessibility or product-wide legal sufficiency.

## Evidence references

| Evidence | Product-specific entry |
| --- | --- |
| Qualified SDK baseline | Version, tested commit, wheel/sdist hashes and CI URL |
| Integration configuration | Sanitized configuration/hash, publisher/system/version |
| Output coverage | Export paths, representative content, receipts and download checks |
| Reliability | Clean/positive corpus, denominators, correct/wrong IDs and incomplete counts |
| Robustness | Exact ordinary-transform and plausible-attack parameters; failures retained |
| Performance | Machine, threads, cold/warm policy, wall/CPU/memory and stage boundaries |
| Verification | UI/API results and independently checked report/asset binding |
| Interoperability | External C2PA read; supported watermark access/discovery and open items |
| Corrective process | Feedback review, monitoring, known limitations and next review date |

## Decision and follow-up

For each requirement classify: implemented technical measure; verified reference
behavior; verified product behavior; remaining operator action; or out of scope.
Do not substitute a percentage of checked boxes for the applicable legal standard.
Record unresolved issues, owner and date. Export gates require the expected
technical evidence in the returned file; they do not assign a statutory durability
percentage to later transformed content. Retain [protocol records](../benchmarks/protocols.md)
with the release. Separate a report verifier's clock from a trusted TSA timestamp.
