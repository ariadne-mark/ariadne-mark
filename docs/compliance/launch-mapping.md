# Requirements → technical controls → deployment evidence

EU/California source review: **10 November 2026**. Connecticut/New York navigator entries retain their **6 November 2026** review scope; they were not re-reviewed in this documentation pass. Scope: visual-content providers using a Python/CPU export pipeline. This is an implementation map, not a legal opinion or a certification of a product. Requirements for platforms, model hosts, capture devices, elections, likeness rights, prohibited content, privacy laws generally and other jurisdictions need separate assessment.

| Source and role | Relevant obligation | Included technical controls | What remains product-specific |
|---|---|---|---|
| [EU AI Act 50(2)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50), provider | Machine-readable marking and detection; effectiveness, interoperability, robustness and reliability as technically feasible | C2PA + recoverable watermark; local verifier/HTTP upload API; explicit evidence states | Actual output coverage, durability and interoperability assessment; audio/text outside the visual SDK |
| [EU 50(4)–(5)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50), relevant deployer | Understandable disclosure of deepfakes by exposure; appropriate treatment of creative works | Optional visible export label; integration examples | Determine scope and disclosure placement/accessibility. Invisible marks alone do not satisfy a visible disclosure duty |
| [EU Article 111(4)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-111) | Provider transition for systems placed on the market before 2 August 2026 | Date-aware product profile | Establish actual first-placement date. That transition ends 2 December 2026; it is not a general postponement of deployer duties |
| [California BPC 22757.2](https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=8.&chapter=25.&part=&lawCode=BPC), covered provider | No-cost public verification, upload **or** URL input, programmatic access, feedback, necessary-only processing | Upload UI + API, category-only feedback, transient uploads, reviewed public system fields, read-only registry resolver | Publish and operate the service, link it from the product where needed, configure reviewed sources/roots, use feedback, review hosts/proxy logs |
| [California BPC 22757.3](https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=8.&chapter=25.&part=&lawCode=BPC), covered provider | Latent disclosure with specified public provenance, durability and compatibility/interoperability | Provider, system/version, creation/alteration time, UUID and action in C2PA; watermark ID; optional operator registry and `/records/{token}` | Persistent accessible hosting/registry, removal resistance, actual integration coverage; copied IDs do not authenticate edited content |
| [Connecticut PA26-15 §15](https://www.cga.ct.gov/2026/act/Pa/pdf/2026PA-00015-R00SB-00005-PA.PDF), conditional covered provider | Provenance data and reasonable tamper/removal resistance, effective 1 October 2026 | C2PA and watermark are available technical measures | More than 1 million monthly users and public consumer personal use; statutory exceptions need assessment. CT is an advisory navigator entry, not an executable SDK jurisdiction profile |
| [New York GBL396-b(3)](https://www.nysenate.gov/legislation/laws/GBS/396-B), relevant advertiser | Conspicuous disclosure of a known synthetic performer in an advertisement | Reference visible-label component | Advertiser must use appropriate wording and placement; exceptions differ. C2PA/watermark alone is insufficient; NY is not an executable jurisdiction profile |

The California consolidated page was read directly in the browser because the text-fetch tool returned403. Its amendment notes show SB 1000, Stats 2026 Ch 861, effective 30 September 2026. The current covered-provider definition has no monthly-user threshold. Do not import Connecticut's threshold into California.

## Cadence is not a legal safe harbor

None of the reviewed marking provisions specifies a mandatory number of marked frames or a 1/2/5-second cadence. That does **not** make every sparse cadence sufficient. The SDK keeps `economy_5s` as a requested engineering default and offers `economy_2s` and `resilient`; the requirement planner retains a durability-review finding for Economy.

The [Commission's final guidelines, C(2026) 7702 final of 5 November 2026](https://digital-strategy.ec.europa.eu/en/policies/guidelines-ai-transparency-obligations), sections4.2.1–4.2.3, discuss marking together with available detection, common alterations and adversarial robustness. The narrow controlled-environment cases are not blanket exemptions for publicly exported entertainment content. The [voluntary Code](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content) is a distinct compliance route with further measures; this SDK does not claim full adherence or universal detector routing.

**Measured limitation:** on one matched-payload720p24 street clip, replacing only the scheduled frames with adjacent unmarked frames removed Economy 5s at 6/240 frames and Economy 2s at 15/240. Duration/PTS were retained; metadata was removed by re-encoding. Applying the same 6-frame replacement to Resilient retained its ID. This is a small adversarial stress result, not a universal robustness ranking or a legal conclusion. It prevents treating the ordinary-transform24/24 recovery result as proof of statutory durability.

## Deployment responsibilities

1. Determine role, territory, operation type, release date and actual exceptions. The executable planner currently supports EU/California only.
2. Use truthful **public organization/model** fields and random per-asset IDs. Do not insert end-user names, account IDs, prompts or contact data into provenance. Review the public-source allowlist rather than automatically exposing uploaded strings.
3. Operate the verifier, feedback and persistent registry as required. A sample Compose file is not an availability or permanence commitment. Add the verifier link in the product's interface when using a third-party verification route.
4. Keep signing keys out of the verifier. Establish appropriate production certificate/TSA trust and key management. The SDK's strict production timestamp gate is an implementation policy, not a claim that every reviewed law mandates an external TSA request per file.
5. Validate the final product delivery chain and relevant removal/tampering threats. Record failures and incomplete searches. A report URL or benchmark percentage does not turn a declaration into a passing legal assessment.
6. Handle synthetic audio, additional disclosures, licensing obligations and other law outside this visual-content workflow.

For federal context, the [COPIED Act S1396 page](https://www.congress.gov/bill/119th-congress/senate-bill/1396) reviewed here shows an introduced bill, not an enacted universal marking mandate. This is not an assertion that no other federal or state duty applies. Asia and other markets have not been qualified by this release.

## Public wording

Use: **“Open-source tools for implementing image/video labeling, provenance and verification controls, with a documented EU/California requirements map.”**

Do not use: “install this SDK and your product is compliant everywhere,” “Economy 5s is the legal minimum,” “24/24 proves legal compliance,” “bulletproof watermark,” or “a missing mark proves human origin.”

## Public verifier output and upstream inputs

The reference verifier withholds unreviewed provider/system strings and private
metadata. A California operator must configure reviewed `--public-sources` and
issuer trust, test displayed system provenance, and declare
`deployment.verifier_public_sources_reviewed`. The planner records a declaration,
not proof of deployed behavior. Keep privacy filtering in place for arbitrary uploads.

A valid existing C2PA input currently requires `action=altered`; the resulting
assertion/visible label describes AI-altered/composite media. Merely adding a
mark to an already AI-created upstream asset is not yet a distinct relay mode.
That workflow needs semantic review; an `opened` + `created` action template
should not be adopted without validating the C2PA action/source-type semantics.

The existing California removal-resistance assessment remains open. Choosing
Economy or Resilient does not itself close it. See [supported scope](../operations/support.md)
and [measured reliability protocol](../../benchmarks/reliability/README.md).

Current public guides: [EU](eu-ai-act.md), [California](california.md),
[source excerpts](source-excerpts.md), [Code map](eu-code-map.md), and
[requirement/evidence matrix](requirements-matrix.md). The PDF edition date and
website publication/update dates are distinguished in the source review record.
