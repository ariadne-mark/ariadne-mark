# C2PA assessment harness

Use a separate Linux x86-64 assessment container with the qualified Ariadne
0.7.3b2 Python 3.12 runtime. Assessment input paths and clock controls are
operator-only. The hosted HTTP service does not load this helper.

Build the qualification clock with a trusted C toolchain on an isolated Linux
build environment, then record its SHA-256 beside the source revision:

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared -Wl,-z,relro,-z,now \
  -o /work/assessment-clock.so scripts/c2pa_assessment_clock.c
sha256sum /work/assessment-clock.so
```

Render one assessment report on the exact asset with the two test anchor
bundles:

```sh
python scripts/c2pa_assess.py fixture.png \
  --trust-list test-manifest.pem --tsa-trust-list test-tsa.pem \
  --validation-time 2026-11-19T09:06:00.123Z \
  --clock-library /work/assessment-clock.so \
  --clock-sha256 '<recorded-sha256>' > fixture.crjson
```

The assessor takes PEM X.509 trust anchors, with distinct lists for manifest
issuers and TSAs. Preserve the original tests and test-list files. If an
assessor supplies another trust-list representation, confirm the treatment of
trust status and service scopes before extracting certificates. Wall-clock
control applies only to the child process. The SDK runtime performs normal
cryptographic validation with the supplied trust configuration. A report is
accepted only if its native crJSON reports the requested validation time. Use a
network-disabled container with read-only fixture inputs, a non-root account,
and no signing credentials. The command does not provide signing or a server.

Version 0.7.3b2 returns a native-generated report; label the resulting artifact
with the software that actually emitted it. The regular verifier's
`validation_state` and `validation_status_codes` are separate from the SDK's
own summary status and from the assessment crJSON itself. The status groups
expose bounded code identifiers and leave detailed input-controlled strings in
the local report. `/health` exposes a paired trust snapshot only after it has
matched both configured list hashes.

## CLI contract and replay

Get the independent harness version using `c2pa_assess.py --version`. On
exit 0, stdout holds the native crJSON. A native validation failure can be in
a successfully emitted report. Read its status groups to establish the
signature, binding and trust outcomes.

| Exit code | Output |
| --- | --- |
| 2 | Assessment infrastructure could not complete validation. |
| 3 | JSON diagnostic with `manifest_not_found`. |
| 4 | JSON diagnostic with `malformed_asset_or_manifest` for typed native failures. |
| 5 | JSON diagnostic with `no_manifest_assessment` if the native result has no manifest entries. |
| 6 | JSON diagnostic with `native_validation_failed` for an unclassified native reader error. The cause is unspecified. |

For 2–6, stdout is empty and the diagnostic is on stderr. Such a diagnostic
is outside the crJSON schema. Network access stays disabled during validation.

`c2pa_assess_replay.py` consumes a `CASE-MATRIX.json` containing the complete
test inputs, report and diagnostic hashes, expected exit code and exact
validation time for each case. Use the same runtime and assessor source as
recorded in the matrix. It verifies input hashes and compares full parsed
native reports and diagnostics. Set the clock hash to that of the copy you
built for the isolated container.

The `specVersion` emitted by the validator in its result block describes the
native report. The version declared by the content signer in
`claim_generator_info` is part of the content manifest. Keep both as emitted.
