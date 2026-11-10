# Prepare your production deployment

SDK **0.7.2a1** · documentation review **2026-11-10**.

Use the qualified kit as a reference deployment and assign an owner for each
step below. A development init is a local evaluation, not a production setup.

## Credentials and trust

Run `kit init` without `--development` using your actual HTTPS verifier origin.
It creates the directory structure and separate report key, but intentionally
creates no fake production issuer or public TLS credentials.

| File or setting | Operator supplies | Checked locally |
| --- | --- | --- |
| `private/provider/certificate.pem` | ES256 signer leaf and intermediate chain | Current validity, path to issuer roots and supported signer EKU |
| `private/provider/private.key` | Matching ES256 private key, mode 0600 | Key match; no group/world read access |
| `private/provider/identity.json` | Actual non-development identity declaration | Mode consistency; JSON flag does not create public trust |
| `config/issuer-roots.pem` | Appropriate public issuer CA roots | CA validity/constraints, provider path validation |
| `config/tsa-roots.pem` | Appropriate TSA roots, separate from signer trust | Root format/validity; export validates actual timestamp trust |
| `config/kit.json` `timestamp_url` | Reachable HTTPS TSA endpoint | Syntax; live availability tested by actual export |
| `private/tls/cert.pem`, `key.pem` | TLS identity for your public hostname | Pair can load; local check does not establish public hostname/reachability |
| `config/report.pub` | Independently distributed report public key | Matches the separate report signer |

Do not relabel an `init-dev` identity as production. Public C2PA trust-list
membership and conformity are separate from a chain rooted in an operator's
local configuration. The toolkit does not obtain a certificate or enroll a product.
Accepted local signer EKUs are emailProtection, documentSigning and
c2pa-kp-claimSigning, excluding timestamp/OCSP/any-purpose leaf use. Revocation
freshness is not checked offline. See [key lifecycle](keys-and-trust.md).

Production exports currently require a trusted TSA. This is the SDK's signing
policy, not a direct requirement to contact a TSA per file in Article 50(2).
The voluntary Code separately discusses secure signing/time-stamping; do not
confuse that with a mandate for this particular service topology.

## Product and publication

1. Set truthful public publisher/system/version in product and reviewed-source
   config. One kit serves one pair; use separate kits for additional versions.
2. Declare content, roles, markets and placement dates. Record remaining actions
   from `profile check`; a declaration is not verification of deployed behavior.
3. Prepare each final rendition before SDK export. Keep synthetic audio outside
   the visual profile. Resolve upstream C2PA semantics before re-marking inputs.
4. Apply required user-facing disclosures in the app when applicable, considering
   placement, wording and accessibility. `--visible` is a reference component.
5. Run `kit check DIRECTORY --runtime`, inspect structured errors and open actions.

`local_configuration_checked` covers local configuration only. It does not
establish public reachability, TLS hostname, TSA uptime, public enrollment,
accessibility, production capacity or legal sufficiency.

## Publish and prove the route

Use the generated production-egress override for the exporter only after
configuring the TSA destination policy. Keep verifier egress disabled and its
registry mount read-only. Publish the edge with real TLS/DNS; defaults bind to
localhost. `kit render` regenerates limits/redirects after configuration changes.

From a client outside the host, test the actual HTTPS UI/API with an image and
all selected video modes. Verify signed responses with the separately pinned
report key. Download the content through the real app/CDN and verify those bytes.
Check normal delivery transforms, negative/unsupported results, feedback and
upload cleanup. Confirm that export failures never publish the original as a
fallback. These operator checks are not automatically performed by `kit check`.

## Keep it operational

Back up registry/config and protect keys; rehearse restore in staging. Monitor
capacity, TLS expiry, failed exports and incomplete scans. The reference verifier
has one inference slot and no queue: load behavior needs an operator-specific
plan. Review proxy/host logs and publish actual operator privacy/contact details.
Review anonymous feedback and documented failures. Plan key/report-key rotation,
revocation and backward detection of earlier formats.

Record the results in the [operator evidence template](../compliance/operator-evidence-template.md).
[Release qualification](../validation/0.7.2a1-results.md) used development credentials;
no real production identity/TSA deployment or long-running public load test is claimed.
