# Ariadne Mark

**Open-source watermarking, provenance and verification for AI-generated images and video.**

A local Python SDK and CLI that adds a recoverable ID (TrustMark for images and Economy/Resilient video), signs C2PA provenance, and checks the final exported file. Includes a self-hosted verifier and an optional SQLite recovery registry. No account, API key or hosted service is required.

**Developer-alpha candidate · 0.7.3a2 (not yet published).** JPEG/PNG images and SDR H.264 MP4 video are implemented. This is technical tooling for content-labeling workflows, not a certificate of legal compliance. See [supported formats and limits](docs/operations/support.md) and [requirements coverage](compliance/COVERAGE.md).

[Documentation hub](docs/index.md) · [EU guide](docs/compliance/eu-ai-act.md) ·
[California guide](docs/compliance/california.md) · [Test protocols and evidence](docs/benchmarks/protocols.md)

## Candidate and previous published release

This checkout contains the schema-2 candidate, **0.7.3a2**. Its installation and
verification-scope changes are described in [migration and known issues](docs/operations/release-0.7.3a0.md).
For the latest routing and result semantics see [R4 changes](docs/operations/release-0.7.3a1.md) and [0.7.3a2 adoption changes](docs/operations/release-0.7.3a2.md).
Use the wheel built from this checkout for candidate review. Do not overwrite
the older published artifact. The release link below is the previous 0.7.2a1
baseline, not this candidate.

### Previous published baseline

[Release 0.7.2a1](https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.2a1)
contains the wheel/source, SHA-256 hashes, runtime inventory and real sample
exports with signed verification reports. This is a GitHub release; no PyPI
publication is claimed. Qualified runtime source: `8c6fda8`; documentation can evolve separately.

For a complete image + three-video-mode walkthrough on Linux x86-64 with Docker:

```sh
curl -fL https://github.com/ariadne-mark/ariadne-mark/releases/download/v0.7.2a1/FIRST_EXPORT.sh -o FIRST_EXPORT.sh
# Read the script before running it. It creates a new ariadne-first-run directory.
bash FIRST_EXPORT.sh
```

[Production identity and timestamps](docs/operations/production-onboarding.md) ·
[Node.js / Next.js / mobile backend](docs/guides/nodejs-nextjs.md) ·
[Commercial use](docs/operations/licensing.md) · [Troubleshooting](docs/operations/troubleshooting.md)

## Quick start with Docker

```sh
# From this reviewed 0.7.3a2 source checkout; candidate is not published yet.
# --iidfile records the immutable image ID; no shared tag is created or moved.
docker build --platform linux/amd64 --iidfile ariadne-image.id .
IMAGE=$(cat ariadne-image.id)
```

Plan disk space before building: on the qualification host the final image is
about 3.2 GB and the build stage about 3.5 GB, plus BuildKit cache, so allow
roughly 9–10 GB free while building (more if layers are not already cached).
The wheel path below needs about 2.2 GB (venv 1.5 GB, models ~0.3 GB, Node
~0.2 GB) and is the fallback for hosts that cannot hold the Docker build.

The build downloads CPU dependencies and verifies pinned model files. Processing can then run without a network connection:

```sh
# Create a local DEVELOPMENT identity. Production uses your own credentials.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/data" "$IMAGE" init-dev .ariadne/dev

# Put input.png in this directory. Supply its actual generator and creation time.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/data" "$IMAGE" mark input.png output.png \
  --publisher "Example Studio" --system "Example Generator" --system-version "1.0" \
  --created-at "2026-11-03T10:00:00Z" --identity .ariadne/dev --allow-dev \
  --registry .ariadne/registry.sqlite3

docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/data" "$IMAGE" verify output.png \
  --registry .ariadne/registry.sqlite3
```

Video uses TrustMark Q on CPU. The default `economy_5s` marks 125 ms windows every 5 seconds; `economy_2s` uses 2 seconds. Each selected frame receives a fresh signal. `resilient` processes every frame. All three presets are in the same SDK/wheel and need the same video runtime. Select with `SDK(video_profile="economy_2s")`, a per-export `sdk.mark(..., video_profile="resilient")`, `--video-profile`, or `sdk.video_profile` in a product JSON configuration.

Economy export checks require an independently decoded matching ID in every occupied watermark window; Resilient retains its five-sample read-back gate. For a new operator that has never issued VideoSeal marks, set `SDK(verification_scope="current")` or CLI `--verification-scope current`; new kits write this scope explicitly. Existing SDK/CLI defaults remain `all` for compatibility. A negative applies only to declared schemes; a signed out-of-scope technique remains `not_checked`. Independent verification does not need the export profile: it scans for IDs and can recover weak signals from cached logits without a second CNN pass. Search budgets and incomplete/conflicting results are explicit. A recovered ID does not establish whole-video coverage or legal compliance. Legacy Fast and older TrustMark IDs remain readable; VideoSeal requires its explicit optional model setup; `fast` is an explicit compatibility encoder, no longer the default.

```sh
ariadne mark input.mp4 output.mp4 --video-profile resilient \
  --publisher "Example Studio" --system "Example Generator" --system-version "1.0" \
  --created-at "2026-11-04T10:00:00Z" --identity .ariadne/dev --allow-dev \
  --audio-kind original --registry .ariadne/registry.sqlite3
```

[Video modes and installation](docs/implementation/video-profiles.md) · [Run the verifier](docs/operations/verifier-quickstart.md) · [Requirements and known limits](docs/compliance/launch-mapping.md).

For video use `input.mp4 output.mp4` and set `--audio-kind original`, `synthetic`, or `unknown` when appropriate. Add `--visible` for a visible disclosure, or `--action altered` for AI-altered material. Existing output files are never overwritten.

The output includes a `.receipt.json` file containing its SHA-256, processing time and verification results. A development signature is valid but **not a production identity**; its headline remains marked development even if its test root is explicitly trusted. `--trust-anchors .ariadne/dev/trust.pem` is only for explicitly trusting your own test root.

## Python installation and API

The tested media bundle is Linux x86-64 / Python 3.12 / CPU. The dependency-free record core is also tested on Python 3.11–3.14. Native video use requires FFmpeg/ffprobe and Node.js (tested 24); npm is needed only during explicit model/runtime setup. The Docker recipe provisions them and omits npm from the final runtime. The Node/ONNX worker is persistent and receives binary frames; audio/timestamps remain in the Python exporter.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
# Use the downloaded wheel, or use: python -m pip install --no-deps .
python -m pip install --no-deps /path/to/ariadne_mark-0.7.3a2-py3-none-any.whl
# Explicit setup installs the pinned C2PA pair and CPU dependencies, then models.
# FFmpeg/ffprobe and Node.js/npm must already be installed.
ariadne setup media --fetch-models
ariadne runtime check
```

The wheel contains media/video hash locks and an explicit installer; a source checkout is not needed.
`ariadne setup video --fetch-models` installs the lighter video-only runtime without
Torch, NumPy or Python TrustMark; image/legacy decoders are omitted. Extras alone
do not provision or qualify C2PA/models. The qualified wrapper is built explicitly
from pinned source rather than resolved from an unavailable PyPI version.

The explicit C2PA bootstrap builds the official tagged Python wrapper with the
SHA-256-pinned upstream native library 0.91.11. It is qualified on Linux x86-64;
use the Docker recipe for the supported media environment.

`models fetch` defaults to the current image and video engines (`--engine media`). Legacy VideoSeal is not on the normal setup/build path. Use `models fetch --engine all` to request all engines explicitly; a requested engine download failure remains an error. Use `--engine trustmark` for images, `--engine video` for Economy/Resilient, or `--engine videoseal` for legacy compatibility. `ARIADNE_VIDEOSEAL_MODEL` can point to a shared, checksum-verified model file.

`models fetch` is an explicit setup step. Later requests fail clearly if models are missing or have incorrect checksums. They do not silently download models.

```python
from datetime import datetime, timezone
from pathlib import Path
from ariadne_mark.pipeline import SDK
from ariadne_mark.provenance import Action, GenerativeSystem, MediaKind, ProvenanceRecord
from ariadne_mark.registry import Registry
from ariadne_mark.signing import SigningIdentity
from ariadne_mark.watermark import Watermarker

sdk = SDK(
    Watermarker(threads=2),
    SigningIdentity.from_directory(Path(".ariadne/dev"), allow_dev=True),
    Registry(Path(".ariadne/registry.sqlite3")),
)
record = ProvenanceRecord.create(
    publisher="Example Studio", system=GenerativeSystem("Example Generator", "1.0"),
    media_kind=MediaKind.IMAGE, action=Action.CREATED,
    created_at=datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc),
)
receipt = sdk.mark(Path("input.png"), Path("output.png"), record)
result = sdk.verify(Path("output.png"))
```

Load the SDK once and reuse it across a queue of jobs. It serializes model inference; do not load a model per frame or request.

## Product requirements profiles

```sh
ariadne profile init > product.json
# Fill the product facts and deployment fields, then:
ariadne profile check product.json > requirements-report.json
ariadne mark input.png marked.png --profile product.json \
  --created-at "2026-11-03T10:00:00Z" --identity .ariadne/dev --allow-dev
```

The offline EU/California planner reports missing configuration, deployment
actions and review items. No models are needed for `profile check`; exit 3 means
open actions/review, exit 2 means invalid input. The media export records the
assessment and configuration hash in its receipt. Declarations are never
reported as verified legal compliance. [Profile guide](docs/compliance/applicability.md).

## Self-hosted verifier

```sh
docker compose up --build
```

Open **http://localhost:8080**. It accepts uploads without registration, exposes a binary-upload API at `POST /verify?format=png` (also `jpg`, `jpeg`, `mp4`), and deletes temporary media after each request. The default Compose service binds only to localhost. Public service mode requires valid, non-development CA roots and deployment behind a buffering/rate-limiting reverse proxy. It requires configured roots (`--production --trust-anchors roots.pem`). Uploads are bounded separately from inference; the default 512 MiB ceiling matches export. See [deployment](docs/operations/verifier.md) to attach a recovery registry, trust roots or feedback link and publish it behind a reverse proxy.

## Try a complete product integration

The [stock export lab](examples/stock_product/README.md) replaces a generator
with stock images/video and exercises a persistent queue, SDK worker,
downloads and a separate verifier. It includes a browser UI and an HTTP
acceptance script that deliberately interrupts and restarts services.
[Server validation](examples/stock_product/VALIDATION.md).

## What verification means

- **Valid signed claim:** signature and content binding validate. An untrusted issuer gets an unverified headline; use `verify --strict` when trusted credentials are required.
- **Recovered watermark:** a supported ID was extracted. Registry lookup returns the record associated with that ID; a transformed copy has no authenticated content binding from the ID alone.
- **Not found:** a supported check ran and found no mark. This does not establish human origin.
- **Not checked / invalid / expired credential:** operational failure, invalid evidence and unresolved signing time are distinguished. None is a successful negative detection.

Watermarks can be removed or copied. The tool does not detect every AI image, verify factual truth, or call other providers' closed detectors. Video watermark verification reports sample coverage and aggregate-only recovery; C2PA verifies the signed asset binding. No whole-video watermark percentage is inferred from the samples.

## SDK + verifier + registry deployment kit

`ariadne kit init DIRECTORY` prepares an operator-owned deployment. Add
`--development` to explicitly generate local test credentials. The kit includes
batch export with resident SDK workers, a read-only registry verifier, separate
report keys and a pinned nginx TLS edge. No signing key is mounted in the
verifier. Economy5s, Economy2s and Resilient are unchanged.

See the [end-to-end kit guide](docs/operations/deployment-kit.md). Production
credentials, public TLS/DNS and actual product-scope assessment remain operator
steps; kit readiness is not a legal compliance determination.

## Tests and evidence

```sh
python -m unittest discover -s tests -t . -v
python scripts/check_requirements.py
# Full real-engine suite in the built image, with networking disabled:
docker run --rm --network none --cpus 2 --memory 6g \
  -e ARIADNE_MEDIA_TESTS=1 -w /app --entrypoint python \
  "$IMAGE" -m unittest discover -s tests -t . -v
```

The ordinary core suite skips media tests unless explicitly enabled. Release qualification runs the Python matrix and real-engine Docker suite in a maintainer-dispatched EC2 job for an exact commit. Automatic PR/push checks are notices and do not run SDK tests. [Reproducible benchmark](benchmarks/durability/README.md) · [0.7.2a1 qualification](docs/validation/0.7.2a1.md) · [Prior video qualification](docs/validation/0.7.1a0.md) · [Requirement records](compliance/requirements.json) · [Regulatory mapping](docs/compliance/release-mapping.md).

[Public alpha checklist](docs/operations/public-alpha-checklist.md).

## Contribute

Use [Discussions](https://github.com/ariadne-mark/ariadne-mark/discussions) for integration questions, [Issues](https://github.com/ariadne-mark/ariadne-mark/issues) for bugs and sourced regulatory corrections, and [private security reports](https://github.com/ariadne-mark/ariadne-mark/security/advisories/new) for vulnerabilities. See [CONTRIBUTING](CONTRIBUTING.md). If useful, give the project a star.

## License

Original code is [Apache-2.0](LICENSE). TrustMark and VideoSeal code/models are MIT; C2PA is MIT/Apache-2.0. Other dependencies, including FFmpeg and codec libraries, retain their own licenses. [Third-party inventory](THIRD_PARTY.md).


### Signed reports and C2PA recovery (0.7 alpha)

The self-hosted verifier can issue portable Ed25519/JWS reports bound to the
submitted file. The registry can retain exact signed C2PA manifest stores and
serve explicitly published entries through read-only soft-binding endpoints.
[Signed reports](docs/operations/signed-reports.md) ·
[Recovery, publication and registration limits](docs/operations/c2pa-recovery.md).
Economy 5s (default), Economy 2s and Resilient marking policies are unchanged.
Color conversions use explicit SDR matrix/range and accurate rounding; fractional
FPS recovery has a bounded phase bank. Canonical BCH5 guards validate decoded
codewords in both runtimes. See the [video guide](docs/implementation/video-profiles.md)
and [spatial recovery limits](docs/research/spatial-recovery-2026-11-06.md).
Native C2PA 0.91.11 is pinned for correct CBOR byte-string assertions; rerun
bootstrap when upgrading an existing 0.6 environment. Algorithm-list enrollment,
production trust and mode-specific durability assessment remain separate work.

### C2PA media preflight (0.7.2a1)

`ariadne runtime check` reports the loaded native version and SHA-256 alongside
Python-package pins. The qualified media pair is c2pa-python0.38.3/native0.91.11
on Linux x86-64/Python3.12. Core construction without a signing identity is lazy. Installed mismatches stop media operations; the
supplied verifier preflights before binding HTTP. Low-level inspection reports
`not_checked`/`c2pa_runtime_unqualified`, never absence or a forged signature.
Record/profile-only core operations remain dependency-free. See the
[runtime guide](docs/operations/c2pa-runtime.md) for diagnosis and recovery.

## Boundaries to assess before integrating

- Media is qualified on Linux x86-64 / Python 3.12; core planning supports Python 3.11–3.14. Use Linux amd64 Docker on other hosts; emulation performance is unqualified.
- Post-export portrait crops/aspect changes, letterboxes, severe compression and arbitrary excerpts are not guaranteed to retain ID. Mark final renditions and test the actual delivery path.
- Economy is a cost/coverage setting. Its temporal windows can be removed; public TrustMark removal can also defeat images and Resilient video. No preset is certified as a statutory minimum or attack-proof.
- Detector FPR is not population-calibrated. Two repeated reads are concordant observations, not independent statistical trials. See the [reliability protocol](benchmarks/reliability/README.md).
- Standalone/synthetic audio marking is outside scope; retaining an AAC track does not mark it.
- `verified_at` in signed verifier reports is the verifier's clock, not a TSA timestamp.
- Inputs already carrying valid C2PA require `action=altered` today and are declared AI-altered/composite. A pure marking relay for already-generated upstream media is not implemented; this can be semantically unsuitable for that workflow.
- Public provider/system fields are withheld by default. Configure reviewed `--public-sources` and issuer trust, then test the public output. The CA planner keeps this operator action open until declared reviewed.

The [requirements map](docs/compliance/launch-mapping.md) distinguishes binding law,
voluntary guidance, technical measures and operator duties. Economy's adequacy for
an actual EU/California product remains an assessment question, particularly the
California removal-resistance criterion. This SDK does not supply a compliance certificate.

### Developer-alpha boundaries

One deployment kit serves one publisher/system/version pair; use separate kits
for other model versions. Generation timestamps more than five minutes ahead
of the export clock are rejected. Production `kit check` validates the local
issuer chain/EKU against configured roots, but does not establish production
readiness, certificate enrollment, endpoint availability or legal compliance.
Kit recovery acceptance covers metadata removal without re-encoding (PNG
re-save and MP4 remux); recompression/crop recovery is not guaranteed. The
six-second acceptance fixture distinguishes Economy5s and Economy2s cadence.
See [0.7.2a1 qualification](docs/validation/0.7.2a1.md) and
[deployment scope](docs/operations/deployment-kit.md).
