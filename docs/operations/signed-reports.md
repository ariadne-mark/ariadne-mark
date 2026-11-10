# Signed verifier reports

Install the `reports` extra (also included in `video`/`media`). Generate a
separate verifier key; do not use a content-signing identity:

```sh
ariadne report keygen .private/verifier-report
ariadne serve --report-key .private/verifier-report/report.key \
  --verifier-id https://verify.example.org
```

The existing `/verify` response retains its public result fields and adds
`signed_report`, containing an RFC 7515 compact JWS with Ed25519/EdDSA (RFC 8037).
The UI downloads that envelope. Its payload contains the exact uploaded file's
SHA-256, byte size and declared media type, the UTC verification time, verifier
identifier, SDK version, key fingerprint and **public, redacted** result.
The time is the verifier's clock, not a trusted timestamp authority attestation.
The signature authenticates a report; it is not an assertion of legal compliance,
factual truth, whole-video coverage or model accuracy. Incomplete outcomes stay
incomplete inside signed reports. Error requests do not receive success receipts.

Retrieve the public key at `/report-key.pem` or JWK set at `/report-key`. Exchange
and pin this key through a trusted channel; downloading a key from an arbitrary
server is not independent authentication of that server. The signing key stays
in the HTTP parent and is never passed to the media-inference child. Production
startup requires a configured report signer; development can explicitly operate
without one and `/health` reports `signed_reports: false`.

```sh
ariadne report verify downloaded.json --public-key verifier-report.pub \
  --asset original-submitted.mp4 --verifier-id https://verify.example.org
```

The command validates the pinned key fingerprint, algorithm, signature, payload
schema and (when supplied) asset digest/size and expected verifier ID. It performs
no network fetches and does not need watermark models. Only the decoded signed
payload is authoritative; outer API fields are a display convenience.

For local media verification, `ariadne verify FILE --report-key KEY
--verifier-id ID --report-output NEW.json` writes a portable public receipt.
A failed strict/media check can still produce a signed negative/incomplete result;
the process exit status remains the media verdict. Existing output files are never
overwritten. JSON serialization is deterministic for this implementation; JWS
validation uses the exact encoded bytes and makes no RFC 8785 claim.

Rotate report keys separately from content keys. Keep old public keys available
for receipts already issued and distribute new fingerprints independently.
Application uploads are removed before responding; receipts are not retained by
the service. Operator proxy logs, backups and TLS remain deployment duties.
