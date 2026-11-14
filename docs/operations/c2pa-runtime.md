# C2PA runtime preflight — 0.7.3a4

```sh
ariadne runtime check
```

Exit code 0 and `status: qualified` require Linux x86-64 / Python 3.12, c2pa-python 0.38.3,
native 0.91.11 and the SHA-256 in the packaged `c2pa-bootstrap.json`. Exit code 2 returns
a machine-readable reason: missing dependency, unsupported platform, wrong Python
wrapper/native version, changed/uninspectable binary or a hash mismatch.
The diagnostic contains versions/hashes, not loader paths or uploaded media.

The upstream loader searches cwd and library paths and supports
`C2PA_LIBRARY_NAME`. Preflight checks the actual ctypes handle's absolute path
and the version returned by `c2pa.sdk_version()`. On qualified Linux it also
checks the mapped function's device/inode through `/proc/self/maps`, so replacing
the pathname after `dlopen` cannot qualify the wrong mapped file. It does not assume that the
library in the package directory is the one loaded. A copied qualified binary
can pass; a different build with the same version needs separate qualification.
Hashes are cached per process/handle/file-stat identity; changed files and new
processes are rechecked. It is not an extra binary hash per video frame.

## Startup and failure behavior

- Core `SDK()` construction is lazy, even when another application installed an
  unqualified C2PA. Supplying a signing identity checks an installed runtime.
  Every media export/verification, C2PA context and supplied HTTP service
  requires preflight before media is inspected or output is published.
- Signing and every C2PA context enforce preflight. A mismatch cannot proceed
  to signing/publication. No runtime request downloads or repairs packages.
- The supplied HTTP verifier checks its default child before binding a socket.
  The probe child is reaped; normal requests retain their resident worker.
- Low-level `inspect_c2pa` returns `not_checked`, reason
  `c2pa_runtime_unqualified`, and an operator diagnostic. It does not report
  `not_found` or an invalid/forged signature due to an unsupported runtime.
  Independently available watermark evidence remains separate.
- Core record/profile planning and independent signed-report verification do not
  require loading the native media runtime. Custom verifier implementations are
  responsible for their own preflight contract.

## Recovery

Use the qualified Linux Docker recipe or, in the supported Python 3.12 virtualenv:

```sh
python -m ariadne_mark.bootstrap_c2pa
ariadne runtime check
```

The bootstrap is an explicit installation step; it verifies its pinned sources
and force-reinstalls the wrapper/native pair. Restart Python and verifier
processes afterward: replacing a disk file does not replace a mapped library.
Inspect operator-controlled library overrides and cwd shadow copies if the
loaded version still differs. Do not bypass validation to hide a mismatch.

The check happens after importing/loading the library. It is compatibility and
provisioning-drift detection, not a sandbox, remote attestation or protection
against hostile native initializers or a host administrator altering code/pins.
Known OS/native vulnerability and combined-binary distribution qualifications
remain separate. This check does not certify product/legal compliance.
