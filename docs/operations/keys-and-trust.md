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
