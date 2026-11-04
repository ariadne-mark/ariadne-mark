# Verification result contract

Related: **REQ-008**. This module defines a per-method result;
it does **not** run watermark detection or cryptographic verification.

| Status | Meaning within the named method's scope |
| --- | --- |
| `not_checked` | Check could not run; a reason is required |
| `not_found` | Check ran successfully and found no supported claim |
| `invalid` | Check found invalid evidence; a reason is required |
| `recovered_claim` | A record was recovered, but its signature is absent or unchecked |
| `verified_claim` | Adapter reports a valid content-bound signature for the record |

`signature` separately records `not_checked`, `absent`, `invalid`, or `valid`.
`issuer_trust` separately records `not_checked`, `untrusted`, or `trusted`.
A valid signature never automatically makes the issuer trusted. An unsigned
record cannot receive either verified-claim status or trusted-issuer status.

Unsupported formats, missing models, timeouts and decode failures must be
reported as `not_checked` with a reason, never `not_found`. A negative result
from one method is not a global AI detector result or proof of human origin.
Confidence scores from different detectors are not treated as interchangeable.

## Adapter responsibility

`VerificationResult` checks consistency, not truth. A caller can construct a
valid-looking result, so do not trust arbitrary JSON as verification evidence.
There is deliberately no deserializer that authenticates external results.
Actual adapters must verify content binding, signatures and a documented issuer
trust policy before setting these states. Failure messages must not contain
keys, upload contents or private identifiers.

Executable tests: [test_results.py](../../tests/verification/test_results.py).
The media adapters now exercise these distinctions on actual signed,
transformed, unmarked and corrupted files; see [release evidence](../validation/0.2.0a0.md).

## Media API additions in 0.5.1

- `expired_credential`: the native validator cannot establish a valid signing
  time for an expired credential. This is distinct from detected tampering.
- Untrusted, mathematically valid signatures retain their raw signed claims in
  JSON, but the headline is `Signature valid; issuer unverified`.
- `recovery.content_binding`: `exact_registered_file` only when SHA-256 matches
  the registry's original; otherwise `not_verified`. A matching public ID alone
  is not authenticated source attribution. Even perceptual similarity would not
  make a copy-resistant signature.
- Video `watermark.sample_coverage` reports matched/sample counts per engine,
  partial/aggregate-only evidence and `whole_video_coverage: not_established`.
  It does not invent a whole-file confidence percentage from sampled frames.
  No new acceptance percentage is imposed; conflicts and absent read-back IDs
  still fail export as before.

A valid C2PA binding covers its signed asset; that is separate from the extent
to which watermark IDs can be recovered across a video's timeline.
