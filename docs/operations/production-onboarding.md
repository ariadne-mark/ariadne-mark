# Prepare your production deployment

SDK **0.7.3a2 candidate** · documentation updated **2026-11-14**.

Versioned benchmark and legal-source review dates below remain historical evidence;
they are not a new qualification or legal approval of this candidate.

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

## A concrete certificate route

Reviewed 11 November 2026. Start by identifying your actual operator and product.
The [CAI implementer guide](https://opensource.contentauthenticity.org/docs/conformance/conformance-impl-guide/)
describes product conformance followed by CA certificate issuance. Generator
and validator are separate roles; backend is a supported implementation class.
The process asks for registered organization details and authorized agreements.
Ariadne has not enrolled your product, obtained conformance or issued its credentials.

[SSL.com's C2PA offer](https://www.ssl.com/products/content-authenticity/content-credentials/c2pa/)
currently lists a no-cost one-year Level 1 certificate plus 2,500 timestamps/year,
subject to eligibility and a valid conformance record. Above-quota pricing needs
a quote. Confirm ES256/P-256 key handling, certificate chain/EKU, HTTPS TSA
endpoint, root distribution, quotas and renewal directly before choosing it.
We have not obtained or interoperability-tested a real certificate from that CA.

The public [C2PA issuer and TSA trust lists](https://opensource.contentauthenticity.org/docs/conformance/trust-lists/)
serve different purposes. A locally accepted root or generic RFC3161 response
alone does not prove public C2PA enrollment or the final product's conformance.

### Before paying for or announcing production

1. Complete the operator/product identity and conformance decisions.
2. Confirm the CA can provide the key/signing interface this SDK supports.
   The current identity loader requires local PEM ES256 keys; hardware-backed
   signing is not automatically supplied by this adapter.
3. Obtain the actual chain and separate TSA roots; validate their provenance.
4. Run a real export with the configured HTTPS TSA and qualified runtime.
5. Inspect the exact downloaded output in an independent C2PA validator,
   distinguishing signature, asset match, timestamp and issuer trust.
6. Repeat through your real CDN, with renewal/failure/restore tests and a budget.

These steps depend on your operator identity and vendor arrangements. They
cannot be completed by changing a development identity flag. The SDK/sample
qualification is available now; production public trust remains an explicit
operator onboarding step. See [cost planning](../guides/cost.md).

## Provider compatibility checked during launch preparation

| Candidate route | What is established | What is not established |
| --- | --- | --- |
| SSL.com C2PA certificate/TSA | Published eligibility, quota and HTTPS TSA endpoint | No enrollment/key; API-key authentication is not directly exposed by this SDK adapter |
| Generic DigiCert RFC3161 endpoint | Official documentation publishes an HTTP endpoint | The kit requires HTTPS; a single EC2 HTTPS probe failed to connect. No C2PA-TSA compatibility is claimed |
| Operator-owned compatible HTTPS TSA route | SDK accepts an HTTPS URL and separately configured TSA roots | The actual service, authentication and end-to-end production export need qualification |

[SSL.com's timestamp documentation](https://www.ssl.com/products/content-authenticity/timestamping/)
specifies `https://ts-c2pa.ssl.com` with an API key. Current kit configuration
accepts a plain HTTPS URL, rejecting URL credentials/query secrets; the C2PA
signer adapter supplies no configurable TSA authorization header. Do not put a
secret into a public URL or imply that this vendor works out of the box.
Confirm a supported authenticated signing interface or separately qualify a
restricted operator-owned egress adapter before selecting that route. This
documentation does not provide or qualify such an adapter.

### Why authentication is not available in this release

This was checked against the official C2PA sources at the pinned tags, not
inferred from the Python wrapper alone:

- In native c2pa-rs 0.91.11 (the qualified pair with c2pa-python 0.38.3) the
  RFC 3161 request is sent by `Signer::send_timestamp_request`, which creates a
  fresh default `Context` (`sdk/src/signer.rs`, `crypto/time_stamp/provider.rs`).
  Headers come only from `timestamp_request_headers()`, which none of the
  signers creatable through the C API (`c2pa_signer_from_info`,
  `c2pa_signer_create`, settings `local`/`remote`) implement. Its default HTTP
  client uses bundled public web roots. There is therefore no supported way to
  add an `Authorization` header, an API key or a private TLS root for the TSA
  connection, and the SDK does not invent an HTTP proxy workaround.
- c2pa-rs 0.92.0 (released 11 November 2026) passes the builder's `Context`
  into `send_timestamp_request`. The C API already exposes a context HTTP
  resolver (`c2pa_http_resolver_create`, `c2pa_context_builder_set_http_resolver`),
  so on that version an application-supplied resolver would carry the TSA
  request and could add credentials, a private trust store and timeouts.
  Adopting it means a new qualified wrapper/native pair, which is a separate
  qualification task; it is not part of this candidate.

What the SDK enforces today: the TSA URL must be HTTPS without credentials,
query or fragment (`SigningIdentity`, kit configuration), so a secret can never
travel in a URL, receipt or log. A failed timestamp request (unreachable,
refused, TLS failure, error response or an invalid token rejected by the native
validator) fails the export with `C2PA signing with a timestamp authority
failed; no output published`. The endpoint is not echoed; no media, receipt or
registry row is written. Usable routes now are TSAs that accept unauthenticated
RFC 3161 requests over HTTPS with a publicly trusted server certificate, with
their roots supplied separately as `tsa-roots.pem`. No such service has been
qualified by this project.

The DigiCert probe sent only a synthetic random-hash request; its failed HTTPS
connection is an observation from one host, not a finding that the vendor's
service is generally unavailable. Do not downgrade the kit's HTTPS policy to
make that example pass. A real CA/TSA export remains pending actual operator
identity, credentials and endpoint arrangements.
