# Signing identity and trust

`ariadne init-dev DIRECTORY` generates a fresh 30-day development CA and ES256
leaf certificate. Only the leaf private key is retained (mode 0600); no shared
private keys ship with the project. Using it requires `--allow-dev`. Its
signature can be mathematically valid while its issuer remains untrusted.

For your own signing identity, supply a directory containing:

- `certificate.pem`: PEM leaf certificate followed by its certificate chain.
- `private.key`: matching PEM ES256 private key, readable only by the signer.
- `identity.json`: `{"development": false}` for your production-managed identity.

The C2PA SDK validates certificate/signature requirements. Setting the JSON
flag does not enroll a certificate in any public trust list. Obtain a suitable
credential and configure independent verifier trust through your chosen trust
framework. Keep credentials outside Git, container images and public verifier
mounts. HSM/KMS callbacks are not implemented by this release.

Rotate keys by deploying a new signing identity. Retain the relevant public
certificate chain and receipts for prior exports. Existing content retains its
original signature; replacement of local keys cannot revoke distributed files.
An operational revocation process, monitoring and timestamp policy are still
required for a production service.

Offline verification disables OCSP and remote manifest fetching. Its report
says `not_checked_offline` for revocation. To request a signing timestamp, pass
an explicit `--timestamp-url`; failure must fail the export. No default TSA or
external identity service is contacted.

## Timestamp and expiry policy (0.5.1)

Non-development signing requires an explicit TSA URL and the final read-back
must report a validated, trusted timestamp. Supply required issuer/TSA roots
using `SDK(trust_anchors=...)` or the CLI. C2PA's native validator checks the
signer's validity at the trusted timestamp. The adapter never ignores expiry
because `timeStamp.validated` alone appears: that code does not establish TSA trust.
Without an acceptable timestamp, a now-expired signer returns
`expired_credential`, not a label alleging media tampering. Revocation freshness
still is not checked offline.

An offline regression creates an RFC3161 TSA, signs with a 10-second signer,
waits for expiry and checks both stamped and unstamped files. See
`tests/integration/test_timestamp_expiry.py` and release evidence.

Primary references: [C2PA Python context settings](https://github.com/contentauth/c2pa-python/blob/main/docs/context-settings.md),
[C2PA implementation guidance — time-stamp authorities](https://spec.c2pa.org/specifications/specifications/2.3/guidance/Guidance.html).

0.7 / native 0.91.11 separates manifest and TSA trust. `--trust-anchors`
adds only manifest roots. For a private TSA, explicitly supply
`--tsa-trust-anchors`; built-in public TSA roots remain in use. No signer root
is implicitly trusted as a TSA. The same setting reaches isolated verifier
workers, export read-back and recovered-manifest validation.
