# Install and produce your first marked export

SDK **0.7.2a1** · documentation review **2026-11-10**.

Use this path for your own generated JPEG/PNG or final SDR MP4 rendition.
The supported media runtime is Linux x86-64/Python 3.12 on CPU. The record/profile
core also supports Python 3.11–3.14. Synthetic audio and text marking are outside
this visual kit; AAC may be preserved as original audio.

## Choose an installation

The [source README](../README.md#quick-start-with-docker) contains the Docker
build commands for the matching qualified source archive. The [wheel guide](operations/wheel-install.md)
provides an installation outside the source checkout:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --no-deps /path/to/ariadne_mark-0.7.2a1-py3-none-any.whl
ariadne setup media --fetch-models
ariadne runtime check
```

FFmpeg/ffprobe and Node.js/npm are prerequisites for that wheel path. Use
`ariadne setup video --fetch-models` for video-only processing; it excludes
Torch, NumPy, Python TrustMark and legacy decoders. Explicit setup may download
files; processing does not install missing dependencies. A production TSA request
is a separate, explicitly configured signing-time network operation.

## Evaluate the complete local kit

In the provisioned environment:

```sh
ariadne kit init deployments/demo --development --publisher "Example Studio"   --system "Example Generator" --system-version "1.0"
ariadne kit check deployments/demo --runtime
```

Put a supported final file under `deployments/demo/inputs/`. Copy the generated
`batch.example.json` to `batch.json`. Supply its real source/destination and
actual generation time with timezone; choose a new output name. For video,
choose `economy_5s`, `economy_2s` or `resilient`, and declare audio correctly.
The generated kit README has the Docker/Compose commands and pinned edge setup.
Alternatively, with this environment and kit on the host:

```sh
ariadne kit export deployments/demo deployments/demo/batch.json
```

A successful job produces the signed file, its `.receipt.json` and a registry
entry. Publish the returned file, retaining the receipt internally. The original
input is not a fallback publication if marking fails. A failed batch may have
committed earlier successful jobs; inspect per-file receipts before retrying.

## Check the result

```sh
ariadne verify deployments/demo/outputs/YOUR_OUTPUT.png   --registry deployments/demo/registry/assets.sqlite3
```

Development files intentionally show a development-signature headline. They do
not become production credentials by trusting their test root. For the complete
HTTPS UI/API run the generated Compose kit as described in the [deployment guide](operations/deployment-kit.md).
Pin its local TLS certificate; do not disable certificate verification.

## Move to production

Follow [production onboarding](operations/production-onboarding.md). One kit
represents one publisher/system/version pair. Prepare crop, size and overlays
before marking each rendition. Preserve the published bytes or qualify later
transformations. For a generator already returning C2PA credentials, first read
the [upstream-input boundary](compliance/operator-evidence-template.md#content-and-export-scope).
