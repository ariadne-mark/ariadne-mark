# Signing and validation

REQ-004. The official `c2pa-python==0.38.1` signs the final media file with ES256. Verification requires a valid signature and a matching image/BMFF asset binding; untrusted issuer status is separate from invalid evidence. Unknown substantive native validation failures are not ignored.

The manifest contains standard C2PA actions/digital source types plus an Ariadne assertion with publisher, model/version, timestamp, public UUID, action and watermark token. Parent credentials are imported before publishing derived material. A custom token assertion is not an implementation of the C2PA soft-binding repository protocol.

See [key operations](../operations/keys-and-trust.md), [result semantics](verification-results.md) and [test evidence](../validation/0.2.0a0.md). No production trust enrollment or legal certification is implied.
