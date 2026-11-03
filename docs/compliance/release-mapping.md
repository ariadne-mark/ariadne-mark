# Technical coverage, not a jurisdictional certification

Review date: 2026-11-03. This release implements measures and records evidence;
it does not decide a product's legal role, territorial scope or exceptions.
The executable planner in 0.4.0a0 maps declared product facts to technical
settings and remaining actions. It never returns `compliant=true`.
See the [profile guide](applicability.md).

## EU

Article 50(2) addresses machine-readable, detectable marking of synthetic
outputs, with feasibility, reliability and interoperability considerations.
Article 50(4) addresses relevant deployer disclosure; paragraph 5 addresses
presentation and accessibility. The SDK supplies watermarking, C2PA and an
optional visible label. The application must determine applicability, provide
appropriate user-facing information and assess the evidence for its actual
content pipeline. Synthetic audio, adversarial durability and application
accessibility are not fully covered by this implementation.

Source: [European Commission Article 50 text](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50).
The page identifies the consolidated version on which it is based. Check the
operative legal text and transitional rules before deploying a legal profile.

Provider marking starts on 2 August 2026; Commission guidance gives systems
first placed on the market before that date until 2 December 2026 for that
marking obligation. This does not defer deployer disclosure. See the
[official timing FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act).
Full adherence to the separate voluntary Code of Practice is not evaluated.

## California

The chaptered SB 1000 text updates the covered-provider definition, latent
fields and free disclosure verification workflow. The SDK supplies the core
publisher/system/version/time/ID/created-or-altered fields, a free self-hosted
upload/API verifier and optional recovery storage. A provider still needs to
publish and maintain the tool, connect feedback, manage privacy, assess
applicability and durability, and address licensing and other operational
obligations. No stale million-user exemption is encoded in this SDK. The mapped amendment
also removes the previous mandatory offer of a visible disclosure. Upload or
URL submission can meet the submission-mode provision; our verifier uses upload.

[Official bill page](https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260SB1000)
was inaccessible (403) during this review. The [chaptered text mirror](https://legiscan.com/CA/text/SB1000/2025)
was reviewed; reconcile it with the official consolidated code before approving
a production legal profile. A working watermark does not by itself establish
the required resistance to removal or full statutory coverage.

## Developer release checklist

1. Confirm role, territory, content types, dates and exceptions for your service.
2. Populate truthful public metadata; never place end-user IDs in public claims.
3. Validate your real image/video transformations using the benchmark harness.
4. Configure an appropriate production identity and verifier trust policy.
5. Publish the verifier, feedback channel and any required in-app disclosures.
6. Address synthetic audio separately; this release preserves but does not
   independently watermark its track.
7. Record remaining obligations and your release evidence. China, Korea and
   India are not advertised as supported legal profiles in this release.
