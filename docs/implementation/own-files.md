# From the first export to your own image and silent video

Use this single route for **0.7.3a4**, Linux x86-64/Python 3.12, CPU. It covers
newly generated JPEG/PNG and final silent SDR MP4. Bring the file's real generation
time and public publisher/system/version. Audio generation and credentialed inputs
need a different workflow; see [formats](../operations/support.md) and
[upstream inputs](../compliance/operator-evidence-template.md#content-and-export-scope).

## 1. Provision once and prove the installation

Download [Release 0.7.3a4](https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.3a4),
read `START_HERE.txt`, then run its `FIRST_EXPORT.sh`. It checks artifact hashes
and demonstrates an image and all three video modes. Its Docker route **builds
from source**; there is no published ready-made Docker image to pull. Allow
about 10 GB free for the build. Alternatively use the [qualified wheel setup](../operations/wheel-install.md)
with FFmpeg/ffprobe and Node/npm installed. Do not install the unrelated PyPI `ariadne` package.

The remaining commands run inside that provisioned environment. If using Docker,
mount a private working directory, use the image ID from your completed build,
and enter its shell with `--entrypoint /bin/bash`. Match the container UID to the
workspace owner, allocate two CPUs/4 GiB for this evaluation and keep keys outside
source control. Processing needs provisioned models, not network downloads.

## 2. Describe your own jobs

Download [the worker](../examples/export_jobs.py) and [job manifest](../examples/jobs.example.json)
into the working directory. Put your files under `inputs/`; create private `staging/`.
Replace both placeholder generation times with **each file's actual generation
time, including timezone**. Neither batch start time nor file modification time
is a substitute. Set truthful public product names; never use account IDs,
prompts or emails. The JSON manifest is trusted operator input, not an upload API.

```sh
mkdir -p inputs staging .private registry
ariadne init-dev .private/dev
python export_jobs.py jobs.example.json --identity .private/dev \
  --registry registry/assets.sqlite3 --allow-dev > accepted.jsonl
```

The example validates the complete manifest before any export, accepts at most
100 jobs, constructs the SDK after the worker process starts, and processes serially
with `verification_scope="current"`. This scope covers this new issuer's current
TrustMark image/video schemes. Use `all` and provision legacy engines when your
verifier must also inspect older schemes; it costs additional resources and does
not expand what a current-only negative says about other formats.

Omit `video_profile` to keep **Economy5s**; select `economy_2s` or `resilient` per
video job. All presets share one Node worker in this SDK process. No cadence,
strength or SDK gate is changed by this example. `audio_kind="none"` requires a
silent video; do not use it to misdescribe an audio track.

A success line contains the job ID, receipt and a fresh local read-back. Confirm
signature, expected ID and source record. Development issuer trust remains
separate from a mathematically valid signature. The SDK also saves a sidecar
`.receipt.json` and registry entry. Keep those files private until you deliberately
publish the relevant public data. Only hand accepted staged output to your app's
publication step.

## 3. Run an independent verifier

Start a **separate process** without the provider private key. Give it a read-only
mount of the registry directory and approved public-source config. SQLite readers
need access to the database and its supporting files; mount the directory, not a
stale copied database. Review public names before writing `public-sources.json`:

```json
{"schema_version":1,"sources":[{"publisher":"Your public studio name","system":{"name":"Your generator","version":"1.0"}}]}
```

Generate the separate report key once, then start the verifier:

```sh
ariadne report keygen .private/verifier-report
ariadne serve --host 127.0.0.1 --port 8080 --threads 2 \
  --verification-scope current --registry registry/assets.sqlite3 \
  --public-sources public-sources.json \
  --report-key .private/verifier-report/report.key \
  --verifier-id http://127.0.0.1:8080
```

The loopback URL is for this local evaluation. Public deployment needs HTTPS,
real operator contact/privacy details and the [production path](../operations/production-onboarding.md).
Pin `.private/verifier-report/report.pub` through your own trusted channel.

In another terminal in the provisioned environment:

```sh
curl --fail-with-body --max-time 330 -H 'Content-Type: application/octet-stream' \
  --data-binary @staging/video-001.mp4 \
  'http://127.0.0.1:8080/verify?format=mp4' > verification.json
ariadne report verify verification.json \
  --public-key .private/verifier-report/report.pub \
  --asset staging/video-001.mp4 --verifier-id http://127.0.0.1:8080
```

Repeat with `staging/image-001.png` and `format=png`. Compare the returned ID with
that job's receipt. `GET /records/{token}` resolves the reviewed registry entry.
A registry match is operator evidence; it does not authenticate an edited copy.
HTTP200 means inspection completed, not necessarily that a mark was found. Read
`watermark.status`, `watermark.search`, `c2pa.signature` and issuer trust. A clean
negative can take much longer than a positive. [Result contract](verification-results.md).

## 4. Connect your queue and handle failures

The manifest loop is a small worker example, not a durable message broker. In
your app, retain the generation timestamp and idempotency key when accepting a
job. Admit only a bounded number of pending jobs, then return back pressure
(HTTP429/Retry-After where appropriate). Create a fresh staging path for every
attempt. Publish once, only after accepted receipt/read-back; reconcile retries
against your own job ledger. Never start one model process per web request or
fork a live SDK. Keep exporter and verifier capacities separate.

Nonzero worker exit stops this batch. Earlier accepted jobs may remain; inspect
their receipts before retrying. Existing outputs, duplicate IDs, naive/future
timestamps and input/output collisions fail before marking. Unsupported media
or a failed SDK gate stops export. If the extra local read-back fails after an
SDK export, preserve the candidate privately for investigation. **Never replace
failed output with the unmarked input.**

Back up registry/config and protect keys; rehearse restore before relying on
recovery. The SDK's gate is not a replacement for testing your actual CDN/download
bytes. Follow the [operator evidence template](../compliance/operator-evidence-template.md)
and [cost worksheet](../guides/cost.md) before enabling user traffic.

## Evidence for this example

Server acceptance exercises the published 0.7.3a4 runtime with JPEG, PNG, 720p/24fps
and portrait 1080p/29.97fps silent MP4, all three modes, individual source times,
independent HTTP/registry/JWS verification and rejected malformed jobs. The script
is [in the repository](https://github.com/ariadne-mark/ariadne-mark/blob/main/scripts/ci_client_journey.py). These deterministic
engineering fixtures check integration behavior, not real-world durability,
production public trust or a capacity SLA. The acceptance summary and logs are retained separately from the immutable
[release evidence](../validation/0.7.3a4-results.md).
