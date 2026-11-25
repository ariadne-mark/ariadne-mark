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

Use test trust files provided for the assessment and convert to their PEM
certificate bundles if necessary. Lists for manifest issuers and TSAs remain
separate. Keep the original inputs and document the conversion. Wall-clock
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
