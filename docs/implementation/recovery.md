# Recovery registry

REQ-006. Optional local SQLite maps the 61-bit watermark token to the full provenance record and original exported-file SHA-256. Queries are parameterized; token/UUID uniqueness is enforced. No uploaded files or end-user IDs are stored.

After metadata loss the verifier may recover a token and return its stored source record. This is a recoverable association, not a cryptographic binding of the transformed file: watermarks can be copied. Unknown IDs remain unknown; they are not inferred to be AI or human content from a particular issuer.

Persist and back up the database if your product depends on recovery. The SDK does not promise permanent internet hosting, a global registry or interoperability with other providers' tokens. See [deployment](../operations/verifier.md) and [metadata-loss tests](../../tests/integration/test_media.py).
