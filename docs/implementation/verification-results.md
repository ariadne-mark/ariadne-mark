# Verification result contract

Related: **REQ-008 (in progress)**. This module defines a per-method result;
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
REQ-008 remains in progress until real adapters demonstrate these semantics
on supported, unsupported and malformed media files.
