# Prepare your production deployment

SDK **0.7.3b2 security candidate** · documentation updated **2026-11-18**.

Versioned benchmark and legal-source review dates below remain historical evidence;
they are not a new qualification or legal approval of this candidate.

Use the qualified kit as a reference deployment and assign an owner for each
step below. A development init is a local evaluation, not a production setup.

## Production at a glance

| You need | What to prepare | Where to start |
| --- | --- | --- |
| A supported worker | Linux x86-64 / Python 3.12, runtime and models; size CPU, memory and queue for your own files | [Measured worker resources](../benchmarks/0.7.3a4-performance-2026-11-15.md) |
| Your signing identity | A compatible ES256 certificate/key, issuer roots and an owner for enrollment and renewal | [Credentials and trust](#credentials-and-trust) |
| Timestamp capacity | A reachable HTTPS TSA, its trust roots, actual quota and any required authentication | [Authenticated TSA setup](authenticated-timestamping.md) |
| A checkable export | Public verifier when required, persistent registry and reviewed public fields | [Verifier deployment](verifier-quickstart.md) |
| Delivery evidence | Verify files downloaded through your own app/CDN after expected transformations | [Final renditions](../implementation/final-renditions.md) |
| An operating budget | CPU/hosting, storage, certificate, timestamp requests and operational time | [Workload and cost worksheet](../guides/cost.md) |

Start with one representative image and video. Keep their exact downloaded
bytes, receipt and verification result. Then repeat through your real delivery
path. The remainder of this page provides the settings and acceptance checks.

The monthly cost is workload-specific: **compute + hosting/storage + certificate
amortization + timestamp service/overage + operations**. Fill the cost worksheet
with your own throughput and supplier terms; an unknown TSA quote is an input
to obtain, not a zero-cost assumption. No all-in service price is supplied.

## Dev to production: the critical path

| Step | Owner | External access | Result | Acceptance |
| --- | --- | --- | --- | --- |
| 1. Prove your own export | App engineer | Public release downloads during provisioning | Own image and silent video, receipt and independent read-back | Follow the [single integration route](../implementation/own-files.md); no unmarked fallback |
| 2. Map your product's duties | Founder/product lead, legal reviewer as needed | [EU](../compliance/eu-ai-act.md) / [California](../compliance/california.md) primary sources | Written role, markets, placement date, modalities and disclosure plan | Resolve applicable matrix rows and remaining operator actions; no assumption that installing code certifies the app |
| 3. Choose public trust and signing arrangements | Product operator | C2PA conformance/enrollment and CA, when choosing that public-trust route | Eligible product/operator, compatible signer chain/key and renewal terms | Confirm the CA's actual issuance/key interface works with local ES256 PEM loading; no HSM/cloud-signing adapter is supplied |
| 4. Provision credentials and timestamp capacity | Operator/security owner | Real CA identity and HTTPS TSA; bearer token if required | Protected provider key, issuer roots, independent TSA roots and configured URL/token | `kit check --runtime` succeeds; actual production export validates timestamp and signer chain; fixture TSA is insufficient |
| 5. Publish verifier and recovery | Service operator | Domain, DNS/TLS, hosting | Public HTTPS upload UI/API, reviewed public fields, report key and persistent registry | Check from outside the host; compare downloaded bytes/ID, verify signed report using pinned key, exercise feedback and cleanup |
| 6. Validate actual delivery and failures | App engineer + operator | Own app/CDN and chosen services | Evidence for final renditions, expected transforms, negative/incomplete results and outages | Export failures do not publish; capacity/back pressure, restore and renewal rehearsed; record known limits |
| 7. Enable and maintain | Product owner | Monitoring and vendor accounts | Budget, runbook and evidence archive | Assign incident, key rotation, feedback and law/version review owners |

**Available now:** source/wheel, development identities, three unchanged modes,
local integration, verifier/registry, signed reports and offline test evidence.
**External remaining step:** a real eligible operator/product must obtain its own
signing and timestamp credentials. Ariadne's development test certificate cannot
complete that step. No live CA/TSA interoperability trace for your identity is
claimed. When credentials are available, retain a sanitized export, independent
validator output, exact versions, trust-list date and failure/retry evidence.

A valid signature verifies the manifest and file binding. A locally trusted root
is your verifier configuration; public C2PA trust adds separate ecosystem enrollment
and product conformance. Neither is a declaration that all statutory duties are
met. The SDK's per-export trusted timestamp gate is engineering policy. Applicable
law, the voluntary Code and this implementation are mapped separately in the
[requirements matrix](../compliance/requirements-matrix.md).

Primary onboarding references rechecked **15 November 2026**:
[CAI conformance guide](https://opensource.contentauthenticity.org/docs/conformance/conformance-impl-guide/)
and [SSL.com issuance process](https://www.ssl.com/products/content-authenticity/content-credentials/c2pa/).
Confirm key protection and CA terms for your selected product/assurance level;
support for a local key format does not establish that your deployment satisfies
a conformance security requirement. Do not send private keys in an issue/report.

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
[0.7.3a4 qualification](../validation/0.7.3a4-results.md) used development credentials;
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

## Authenticated TSA compatibility

SSL.com is the selected pilot route. Its official provenance SDK uses bearer
credentials and a short-lived loopback forwarder for the same c2pa-python
family. This candidate implements that approach with verified HTTPS, bounded
messages, a deadline and no redirects; see [authenticated timestamping](authenticated-timestamping.md).
The pinned C2PA pair is unchanged. A future native HTTP-resolver migration
requires its own compatibility qualification and is not a release prerequisite.

Use `timestamp_credential_file` for an owner-only token file, never a token in
the URL. A kit must also have actual provider credentials and independent TSA
roots. The available offline fixture results do not establish live service
availability or production public trust. Real enrollment and authenticated
SSL.com exports remain pending operator credentials.

An unauthenticated HTTPS TSA can still use the original direct-URL path. The
previous DigiCert connection failure was a single-host observation, not a
finding that its service is generally unavailable. Do not downgrade production
HTTPS or reuse a development signer to make an example pass.
