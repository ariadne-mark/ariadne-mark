# Image marking

REQ-002. `SDK.mark` loads single-frame PNG/JPEG, normalizes EXIF orientation, optionally adds visible disclosure, embeds an Ariadne-format 61-bit TrustMark-Q token, signs the exported file and reads it back. Alpha is retained for PNG; existing outputs are never overwritten. Models are provisioned explicitly and verified against SHA-256 before loading.

See [quick start](../../README.md), [limits](../operations/support.md), and [evidence](../validation/0.2.0a0.md). Tests include PNG, JPEG, transparency, metadata stripping and failure without publication. The watermark carries a recovery token, not a user ID or cryptographic proof.
