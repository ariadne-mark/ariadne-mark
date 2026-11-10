# Visible AI labels, watermarks and Content Credentials

These layers answer different questions. A practical export pipeline can use
all three; none makes the content itself true or lawful.

| Layer | What a recipient gets | Important boundary |
| --- | --- | --- |
| Visible disclosure | A readable indication that AI created or altered the media | Placement, wording and accessibility depend on your use and applicable duties |
| Invisible watermark | A machine-readable recoverable identifier in supported pixels/frames | Recovery is bounded by content, transforms, scan budget and deliberate removal |
| Signed C2PA manifest | A signed statement bound to the published asset, with declared source/actions | Signature validity, asset binding and trust in the signer are distinct checks |
| Recovery registry | A route from a supported recovered ID to a stored signed manifest | A copied ID alone does not prove the new asset matches the original |
| Signed verifier report | A checkable record of a verifier's observations about exact bytes | Pin the report public key and asset hash; the report is not a legal certificate |

The [CAI durable-credentials documentation](https://opensource.contentauthenticity.org/docs/durable-cr/)
describes combining provenance manifests with watermarks or fingerprints to
recover information lost when metadata is removed. Ariadne's current kit uses
its supported watermark/registry route. It does not search every vendor's marks.

Publish the final export and a reachable verifier; add appropriate visible
disclosure in the app/content where required. Preserve the structured result
when verification is incomplete or a recovered claim is untrusted.

[Disclosure component](../implementation/disclosure.md) · [Verification results](../implementation/verification-results.md) ·
[EU requirements](../compliance/eu-ai-act.md) · [California requirements](../compliance/california.md)
