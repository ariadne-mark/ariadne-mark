# Python CLI and verification reference

SDK **0.7.3a2 candidate** · documentation updated **2026-11-14**.

Versioned benchmark and legal-source review dates below remain historical evidence;
they are not a new qualification or legal approval of this candidate.

This reference describes this candidate command surface. Run `ariadne --help`
and a command's `--help` in the provisioned environment for all options.

## Main commands

| Command | Purpose | Important inputs |
| --- | --- | --- |
| `setup media` / `setup video` | Explicit pinned installation | `--fetch-models`, optional bootstrap cache/wheelhouse |
| `runtime check` | Inspect native/wrapper pair and hash | No implicit repair |
| `models fetch` / `models check` | Provision/inspect selected engines | `--engine auto` (default), `media`, `all`, `trustmark`, `video`, or `videoseal` |
| `init-dev DIRECTORY` | Generate local evaluation identity | Explicit development use only |
| `profile init` / `profile sources` / `profile check CONFIG` | Template, source catalog, requirement planning | `--as-of YYYY-MM-DD` changes evaluation date, not source knowledge |
| `kit init DIRECTORY` | Create a new deployment | `--publisher`, `--system`, `--system-version`; development is opt-in |
| `kit check DIRECTORY --runtime` | Local configuration/runtime checks | No live endpoint or legal verdict |
| `kit render DIRECTORY` | Regenerate deployment config | Run after endpoint/limit changes |
| `kit export DIRECTORY BATCH` | Batch export with resident workers | Relative paths, actual timestamps, per-job video profile |
| `kit serve DIRECTORY` | Run the configured verifier | Isolated inference, separate report key |
| `mark SOURCE DESTINATION` | Mark, sign and read back | Identity, source facts/time; optional profile, registry, disclosure |
| `verify SOURCE` | Check supported evidence | Optional roots/registry, `--verification-scope all|current`, and `--strict` |
| `recover SOURCE DESTINATION` | Recover a detached manifest | Registry, `--verification-scope all|current`; output file must be new |
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
When several IDs are found it refuses an automatic choice; pass `token=` (CLI
`recover --id`) to select one confirmed ID after detection. The selector is never
given to the detector.
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
| `multiple_ids` | Several distinct watermark IDs were read. Each is listed in `watermark.ids` with its scheme, basis (`confirmed`/`observed`) and observed positions. No ID is chosen for the file, and several IDs do not by themselves invalidate a C2PA signature |
| `c2pa.status=invalid` | Invalid credential; `c2pa.reason` gives the cause. Watermark evidence is reported separately |
| `token_mismatch` | One recovered ID differs from the signed claim: conflicting claims, not by itself an invalid signature |
| `expired_credential` | Acceptable signing time could not be established for an expired credential |
| Registry `content_binding=not_verified` | ID association exists; edited copy is not authenticated by that association |

An incomplete negative headline is `Check incomplete`. Existing positive or
invalid evidence is retained. Inspect structured fields, not only the label.
Video sample coverage is not the percentage of the whole video carrying a mark.
`watermark.evidence_scope` lists each pass (scheme, selection, unique frames,
time range, stop reason) and `whole_file_examined`; an ID applies only to the
positions where it was read. With several IDs, `recovery.status=per_id` gives one
registry result per confirmed ID, bound to the schemes that read it.

Report `schema_version` 2 (unreleased, after 0.7.2a1): the former watermark
`invalid` with reason `multiple_tokens`/`conflicting_ids` is now
`multiple_ids` with `watermark.ids`. Single-ID results keep their fields.

## Exit codes and HTTP

Most successful commands return 0; argument, operational and verification failures
return 2. `profile check` uses 3 for open actions/review. An ordinary `verify`
can return 0 for a completed `not_found`; parse the result. `verify` returns 0
only for watermark `recovered_claim`/`not_found` without a C2PA failure or ID
mismatch; `multiple_ids`, `single_observation` and incomplete checks return 2. `--strict` requires
a valid, non-development credential and trusted issuer, otherwise 2.

The verifier accepts raw binary `POST /verify?format=png|jpg|jpeg|mp4`, not
multipart. It exposes UI, `/health`, `/openapi.json`, report public-key endpoints,
`/records/{token}` and feedback. A signed response is verified with a separately
pinned report public key and, when needed, the submitted asset digest. See
[signed reports](../operations/signed-reports.md) and [recovery endpoints](../operations/c2pa-recovery.md).
Full-manifest routes are disabled unless explicitly enabled; only approved
records are published. HTTP 429 indicates capacity/rate limits, not a negative
media result. TLS edge and application upload ceilings can differ.

## Detection scope and model selection

`verify`, `recover` and `serve` accept `--verification-scope all|current`; the
Python SDK also accepts a nonempty finite list of known schemes. Existing SDK/CLI
defaults remain `all`; new kits explicitly configure `current`. `current` promises
Python-Q image checks and video-Q MP4 checks. Python-Q video reads are supplemental
when available: a negative video-Q result is not a check of the older Python-Q
MP4 scheme. A signed Python-Q MP4 also requires that historical decoder; provision
the media runtime. `all` retains legacy VideoSeal and Python-Q video obligations.
`configured_schemes` records the operator configuration; `declared_schemes` is the
file-specific obligation. `completed_schemes` lists completed declared checks only
(always a subset of `declared_schemes`); a supplemental reader that also finished,
such as Python-Q on a current-scope MP4, is in `supplemental_completed_schemes`.
A positive early stop is not a completed negative; the ID is in `watermark.ids`.
For a declared legacy Python-Q MP4 the documented procedure is five uniformly
requested positions. Missing required decoders or expired budgets never become a
completed negative.

Untrusted/development C2PA claims cannot restrict the independent operator scan.
A trusted non-development issuer can only skip *other* legacy schemes: the
operator's primary scheme (video-Q for MP4, Python-Q for images) is always
scanned, because a public CA trust store also trusts third-party signers. If the
trusted claim names a technique outside the operator scope, the primary result
is kept, `signed_scheme_unchecked` names the claimed technique and a negative
becomes `not_checked` (`signed_scheme_out_of_operator_scope`). The reported
`signed_routing` makes the routing visible. `signed_id_observed` is true on an
actual matching read, false after performed nonmatching observations, and null
when observation was not established. A partial scan can still have a true value.

Bare `models fetch/check` uses `auto`: current media if Python TrustMark is
installed, otherwise video-only, with selection/skips printed. Explicit `media`
requires both current runtimes; explicit `all` retains its legacy requirements.
No request handling downloads models.

`POST /matches/byContent` rejects an explicit algorithm outside this file's
operator scope with HTTP422 `algorithm_outside_operator_scope` / `not_checked`.
An in-scope requested technique without completed negative or matching positive
evidence returns HTTP503 `incomplete_content_search`, never an empty successful
search. These outcomes are separate from a completed HTTP200 empty match list.
