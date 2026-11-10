# Python CLI and verification reference

SDK **0.7.2a1** · documentation review **2026-11-10**.

This reference describes the shipped command surface. Run `ariadne --help`
and a command's `--help` in the provisioned environment for all options.

## Main commands

| Command | Purpose | Important inputs |
| --- | --- | --- |
| `setup media` / `setup video` | Explicit pinned installation | `--fetch-models`, optional bootstrap cache/wheelhouse |
| `runtime check` | Inspect native/wrapper pair and hash | No implicit repair |
| `models fetch` / `models check` | Provision/inspect selected engines | `--engine all`, `trustmark`, `video`, or `videoseal` |
| `init-dev DIRECTORY` | Generate local evaluation identity | Explicit development use only |
| `profile init` / `profile sources` / `profile check CONFIG` | Template, source catalog, requirement planning | `--as-of YYYY-MM-DD` changes evaluation date, not source knowledge |
| `kit init DIRECTORY` | Create a new deployment | `--publisher`, `--system`, `--system-version`; development is opt-in |
| `kit check DIRECTORY --runtime` | Local configuration/runtime checks | No live endpoint or legal verdict |
| `kit render DIRECTORY` | Regenerate deployment config | Run after endpoint/limit changes |
| `kit export DIRECTORY BATCH` | Batch export with resident workers | Relative paths, actual timestamps, per-job video profile |
| `kit serve DIRECTORY` | Run the configured verifier | Isolated inference, separate report key |
| `mark SOURCE DESTINATION` | Mark, sign and read back | Identity, source facts/time; optional profile, registry, disclosure |
| `verify SOURCE` | Check supported evidence | Optional roots/registry and `--strict` |
| `recover SOURCE DESTINATION` | Recover a detached manifest | Registry; output file must be new |
| `report keygen DIRECTORY` / `report verify RECEIPT` | Separate Ed25519 report keys and offline verification | Pinned `--public-key`; optional `--asset`, `--verifier-id` |
| `feedback-summary DATABASE` | Read anonymous aggregate counts | Existing feedback database |

`--trust-anchors` configures manifest issuer roots; `--tsa-trust-anchors`
configures private TSA roots separately. A report key, provider key and TLS key
have different functions. See [trust operations](../operations/keys-and-trust.md).

## Python objects

`SDK` accepts a marking adapter, signing identity, optional registry, issuer/TSA
roots and a `video_profile`. Reuse one instance per worker process, after fork;
close it on shutdown. `SDK.mark(source, destination, record, ...)` is synchronous.
A per-export profile override must agree with any supplied product configuration.
`SDK.verify(path)` checks evidence; `SDK.recover_manifest(source, destination)`
validates and saves the registered manifest without modifying the submitted file.
See the runnable [integration pattern](../implementation/integration.md).

`ProvenanceRecord` contains publisher, system name/version, image/video kind,
created/altered action, timezone-aware generation time and a random UUIDv4.
It is a publisher claim, not proof of the factual truth of those fields. Export
and signing reject creation times over five minutes in the future; parsing
external records remains possible. The allowance is an SDK clock-skew policy.

## Result interpretation

| Evidence | Meaning |
| --- | --- |
| `c2pa.status=verified_claim` | Signature and supported asset binding validated; inspect issuer trust and development status separately |
| `watermark.status=recovered_claim` | Supported ID recovered; not a factual-truth or whole-video certificate |
| `not_found` | Scoped check completed without a supported mark |
| `not_checked` | Check incomplete/unavailable; not a successful negative |
| `single_observation` | A video ID was observed once without sufficient corroboration |
| `invalid` / `token_mismatch` | Invalid or conflicting evidence |
| `expired_credential` | Acceptable signing time could not be established for an expired credential |
| Registry `content_binding=not_verified` | ID association exists; edited copy is not authenticated by that association |

An incomplete negative headline is `Check incomplete`. Existing positive or
invalid evidence is retained. Inspect structured fields, not only the label.
Video sample coverage is not the percentage of the whole video carrying a mark.

## Exit codes and HTTP

Most successful commands return 0; argument, operational and verification failures
return 2. `profile check` uses 3 for open actions/review. An ordinary `verify`
can return 0 for a completed `not_found`; parse the result. `--strict` requires
a valid, non-development credential and trusted issuer, otherwise 2.

The verifier accepts raw binary `POST /verify?format=png|jpg|jpeg|mp4`, not
multipart. It exposes UI, `/health`, `/openapi.json`, report public-key endpoints,
`/records/{token}` and feedback. A signed response is verified with a separately
pinned report public key and, when needed, the submitted asset digest. See
[signed reports](../operations/signed-reports.md) and [recovery endpoints](../operations/c2pa-recovery.md).
Full-manifest routes are disabled unless explicitly enabled; only approved
records are published. HTTP 429 indicates capacity/rate limits, not a negative
media result. TLS edge and application upload ceilings can differ.
