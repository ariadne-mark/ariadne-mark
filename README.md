# Ariadne Mark

**Open-source watermarking, provenance and verification for AI-generated images and video.**

A local Python SDK and CLI that adds a recoverable ID (TrustMark for images and Fast/Resilient video), signs C2PA provenance, and checks the final exported file. Includes a self-hosted verifier and an optional SQLite recovery registry. No account, API key or hosted service is required.

**Developer preview · 0.5.1a0.** JPEG/PNG images and SDR H.264 MP4 video are implemented. This is technical tooling for content-labeling workflows, not a certificate of legal compliance. See [supported formats and limits](docs/operations/support.md) and [requirements coverage](compliance/COVERAGE.md).

## Quick start with Docker

```sh
git clone https://github.com/ariadne-mark/ariadne-mark.git
cd ariadne-mark
docker build -t ariadne-mark:local .
```

The build downloads CPU dependencies and verifies pinned model files. Processing can then run without a network connection:

```sh
# Create a local DEVELOPMENT identity. Production uses your own credentials.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/data" ariadne-mark:local init-dev .ariadne/dev

# Put input.png in this directory. Supply its actual generator and creation time.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/data" ariadne-mark:local mark input.png output.png \
  --publisher "Example Studio" --system "Example Generator" --system-version "1.0" \
  --created-at "2026-11-03T10:00:00Z" --identity .ariadne/dev --allow-dev \
  --registry .ariadne/registry.sqlite3

docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/data" ariadne-mark:local verify output.png \
  --registry .ariadne/registry.sqlite3
```

Video uses TrustMark Q on CPU. `--video-profile fast` reuses a signal with adaptive refresh (at most 24 frames); `--video-profile resilient` calculates a signal for each frame. Both mark every frame and verify 5 samples, expanding to 20 when no ID is found. Existing VideoSeal and older TrustMark IDs remain readable in the full media installation.

```sh
ariadne mark input.mp4 output.mp4 --video-profile resilient \
  --publisher "Example Studio" --system "Example Generator" --system-version "1.0" \
  --created-at "2026-11-04T10:00:00Z" --identity .ariadne/dev --allow-dev \
  --audio-kind original --registry .ariadne/registry.sqlite3
```

[Video installation, profiles and limits](docs/implementation/video-profiles.md).

For video use `input.mp4 output.mp4` and set `--audio-kind original`, `synthetic`, or `unknown` when appropriate. Add `--visible` for a visible disclosure, or `--action altered` for AI-altered material. Existing output files are never overwritten.

The output includes a `.receipt.json` file containing its SHA-256, processing time and verification results. A development signature is valid but **not publicly trusted**. `--trust-anchors .ariadne/dev/trust.pem` is only for explicitly trusting your own test root.

## Python installation and API

The tested media bundle is Linux x86-64 / Python 3.12 / CPU. The dependency-free record core is also tested on Python 3.11–3.14. Native video use requires FFmpeg/ffprobe, Node.js 20+ and npm on PATH; the Docker image includes them. The Node/ONNX worker is persistent and receives binary frames; audio/timestamps remain in the Python exporter.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install '.[media]'
ariadne models fetch
```

`models fetch` provisions image, new video and legacy VideoSeal engines. Use `--engine trustmark` for images, `--engine video` for Fast/Resilient, or `--engine videoseal` for legacy compatibility. `ARIADNE_VIDEOSEAL_MODEL` can point to a shared, checksum-verified model file.

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

Open **http://localhost:8080**. It accepts uploads without registration, exposes a binary-upload API at `POST /verify?format=png` (also `jpg`, `jpeg`, `mp4`), and deletes temporary media after each request. The default Compose service binds only to localhost. Public service mode requires configured roots (`--production --trust-anchors roots.pem`). Uploads are bounded separately from inference; the default 512 MiB ceiling matches export. See [deployment](docs/operations/verifier.md) to attach a recovery registry, trust roots or feedback link and publish it behind a reverse proxy.

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

## Tests and evidence

```sh
python -m unittest discover -s tests -t . -v
python scripts/check_requirements.py
# Full real-engine suite in the built image, with networking disabled:
docker run --rm --network none --cpus 2 --memory 6g \
  -e ARIADNE_MEDIA_TESTS=1 -w /app --entrypoint python \
  ariadne-mark:local -m unittest discover -s tests -t . -v
```

The ordinary core suite skips media tests unless explicitly enabled. CI requires both the Python matrix and real-engine Docker suite. [Reproducible benchmark](benchmarks/durability/README.md) · [Release evidence](docs/validation/0.5.1a0.md) · [Requirement records](compliance/requirements.json) · [Regulatory mapping](docs/compliance/release-mapping.md).

## Contribute

Use [Discussions](https://github.com/ariadne-mark/ariadne-mark/discussions) for integration questions, [Issues](https://github.com/ariadne-mark/ariadne-mark/issues) for bugs and sourced regulatory corrections, and [private security reports](https://github.com/ariadne-mark/ariadne-mark/security/advisories/new) for vulnerabilities. See [CONTRIBUTING](CONTRIBUTING.md). If useful, give the project a star.

## License

Original code is [Apache-2.0](LICENSE). TrustMark and VideoSeal code/models are MIT; C2PA is MIT/Apache-2.0. Other dependencies, including FFmpeg and codec libraries, retain their own licenses. [Third-party inventory](THIRD_PARTY.md).
