# Implement EU Article 50 marking for visual media

SDK **0.7.3a3 candidate** · baseline legal-source review **2026-11-10**.

The source review date and dated evidence below remain historical; this header
is not a new legal clearance or candidate qualification.

This guide covers image/video marking and detection for a provider using
Ariadne at final export. Identify your role and output modalities first.
A visual-media kit does not cover all obligations of an AI business.

## Binding requirements and timing

[Article 50(2)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50) requires machine-readable marking and detectability of
synthetic outputs. The combined solution must address effectiveness,
interoperability, robustness and reliability within technical feasibility,
content limitations, implementation costs and the acknowledged state of the art.
No 2 s/5 s cadence or fixed recovery percentage is prescribed.

Article 50 generally applies from 2 August 2026. For provider systems placed
on the market before that date, [Article 111(4)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-111) sets 2 December 2026
for Article 50(2). This transition is not a blanket delay of deployer duties.
Record the actual first-placement date and any factual exception assessment.
Standard editing is not an automatic exemption for an entire generative app.

For applicable deepfake deployments, Article 50(4)–(5) requires suitable,
understandable disclosure. Creative/satirical contexts affect its form, not
an automatic absence of disclosure. Invisible marking alone does not supply
all user-facing disclosure. Direct AI interaction can also trigger 50(1).

## Map the solution to the obligation

Ariadne combines signed C2PA AI-origin assertions with a recoverable visual
watermark ID. It supplies detection software, a self-hosted UI/API, separate
signed reports and optional persistent ID/manifest recovery. The [matrix](requirements-matrix.md)
links each measure to code, tests, evidence and an operator action.

The [Commission Guidelines](https://digital-strategy.ec.europa.eu/en/library/guidelines-transparency-obligations-providers-and-deployers-ai-systems), edition C(2026) 7702 final of 5 November
2026, explain that marking and available detection are complementary. They
address common alterations and plausible adversarial behavior, while allowing
proportionate choices. The narrow closed-environment examples do not automatically
apply to freely exported entertainment images/videos. See the [source excerpts](source-excerpts.md).

## Choose and document a route

The [Code of Practice](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content) is an adequate voluntary framework recognised
by the Commission/AI Board, distinct from the binding statute. Providers using
other measures need an adequacy justification. Ariadne's components map to
several Code measures; full adherence is not established. Use the
[Code mapping](eu-code-map.md) to assign remaining actions and route-specific dates.
Neither a local CI pass nor selecting Economy is an automatic legal approval.

## Integration and retained evidence

1. Prepare the final supported rendition, then mark/sign it. Publish the returned
   file; prevent unmarked fallbacks. Record every output path using the SDK.
2. Configure actual publisher/system/version/time and production signing/trust.
   The SDK's trusted-TSA export gate is an implementation policy; the Code's
   timestamp provision does not by itself prescribe that exact architecture.
3. Make the corresponding detection route usable by its intended audience.
   Publish its supported schemes, entry points, interpretation and limitations.
4. Select a mode using evidence for your duration, content and delivery transforms.
   Economy5s has known short-excerpt limits; Resilient is not attack-proof.
5. Retain configuration, release hashes, receipts, delivery tests, remaining
   limitations and a process for feedback/corrective updates. Use the
   [operator evidence template](operator-evidence-template.md).

Synthetic audio, independent text marking, broader provenance relay and full
cross-provider discovery remain outside the qualified visual workflow. The
[latest engineering results](../validation/0.7.2a1-results.md) and
[protocols](../benchmarks/protocols.md) specify exactly what was tested.
