# Ariadne Mark

**Free, open-source labeling and verification for AI-generated images and video.**

Add an invisible watermark and signed [C2PA](https://c2pa.org/) Content Credentials to media at export. Verify the resulting file independently. If metadata is missing, the verifier can use a recovered watermark ID to look up a record that was stored in a connected registry. Ariadne Mark runs on your infrastructure as a Python SDK and CLI, with a self-hosted verifier and an optional recovery registry.

[**Try the image demo**](https://ariadnemark.xyz/try/) · [**Verify a signed video**](https://ariadnemark.xyz/verify/?sample=full-video) · [**Quickstart**](docs/start-here.md) · [**Download v0.7.3b2**](https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.3b2)

**Supported media:** JPEG, PNG and SDR H.264 MP4. **Tested runtime:** Linux x86-64, Python 3.12, CPU. Local evaluation requires no account, API key or hosted service. Original code is [Apache-2.0](LICENSE).

## What you get

- **Export:** embed a recoverable watermark ID and signed provenance for the final file. Add visible disclosure when your workflow needs it. The SDK reads the result back before writing it to the requested output path and writes a JSON receipt with the file hash and check results.
- **Verify:** use the browser UI, HTTP API or CLI to inspect credentials and search for a supported watermark. With a registry, a recovered ID can retrieve its provenance record. Watermark recovery alone cannot authenticate the content of a transformed copy.
- **Plan for deployment:** map the features to the [EU AI Act](docs/compliance/eu-ai-act.md) and [California AI Transparency Act](docs/compliance/california.md). The guides identify which actions and assessments remain with the operator. SDK output does not establish legal compliance.

Want to see the difference between a signed claim and a recovered watermark? Try the [signed PNG](https://ariadnemark.xyz/verify/?sample=full-image) and the [signed MP4](https://ariadnemark.xyz/verify/?sample=full-video). We built Ariadne for our own generative-media workflows and shared it so other teams could reuse the export and verification work. If you try it, [tell us what you were trying to label and where you got stuck](https://github.com/ariadne-mark/ariadne-mark/discussions).

## Get your first verified export

Use Docker for a complete sample run. The wheel fits an existing Python worker.

| If you want to… | Use | What you need |
| --- | --- | --- |
| Run the complete example on your machine | [Docker walkthrough](#quick-start-with-docker) | Linux x86-64, Docker Engine, `curl`, `tar`, `sha256sum`, at least **10 GiB free** |
| Integrate with an existing Python backend | [Release wheel](#python-wheel) | Linux x86-64, Python 3.12, FFmpeg/ffprobe, Node.js/npm, about **2.2 GB** for the installed runtime |
| Test a real export without installing | [Hosted verifier with a signed MP4](https://ariadnemark.xyz/verify/?sample=full-video) | A browser |

Both installation routes use files from the [GitHub release](https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.3b2), which includes checksums, runtime inventory, examples and signed verification reports. There is no PyPI distribution or prebuilt combined Docker image. Initial setup downloads dependencies and models.

### Quick start with Docker

```sh
curl -fL https://github.com/ariadne-mark/ariadne-mark/releases/download/v0.7.3b2/FIRST_EXPORT.sh -o FIRST_EXPORT.sh
# Inspect FIRST_EXPORT.sh before running it.
bash FIRST_EXPORT.sh
```

The script checks the release downloads, builds the container from source, and runs one PNG export plus an MP4 export in each video mode. In `ariadne-first-run`, look for `first.png`, the three `first-*.mp4` files, their `.receipt.json` sidecars and separate verification JSON files. Check for a valid C2PA signature with a development identity and a recovered watermark ID matching the receipt. See [verification results](docs/implementation/verification-results.md) for the field meanings.

For the next export, follow the [current Quickstart](docs/start-here.md) or the [production onboarding guide](docs/operations/production-onboarding.md). The [own-files walkthrough](docs/implementation/own-files.md) shows the worker pattern and is documented for v0.7.3b1.

### Python wheel

Download the wheel from the release and verify its checksum. Run the following from the directory with the wheel, with the system prerequisites already installed:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --no-deps ./ariadne_mark-0.7.3b2-py3-none-any.whl
ariadne setup media --fetch-models
ariadne runtime check
```

`ariadne setup media` installs the pinned Python media dependencies and C2PA runtime. A passing `runtime check` confirms setup. For a verified export, follow the [Quickstart export and check steps](docs/start-here.md) with a supported file. See [the wheel guide](docs/operations/wheel-install.md) for alternatives, including video-only setup. Load one SDK instance per worker and reuse it across jobs.

## Choose a video mode

| Mode | Watermark cadence |
| --- | --- |
| **Economy5s** (default, `economy_5s`) | Marks a 125 ms window every 5 seconds |
| **Economy2s** (`economy_2s`) | Marks a 125 ms window every 2 seconds |
| **Resilient** (`resilient`) | Processes every frame |

All three use the same CPU video runtime. Select a profile with `--video-profile` or the SDK’s `video_profile` option. Mark each final rendition and test the actual delivery path. Cropping, letterboxing, heavy compression and short edits can remove signals, particularly with sparse marking. See [video modes and read-back checks](docs/implementation/video-profiles.md), [CPU measurements](docs/benchmarks/0.7.3a4-performance-2026-11-15.md) and [delivery transform results](docs/benchmarks/0.7.3a4-delivery-2026-11-18.md). The linked measurements cover v0.7.3a4. Use them as reference and measure CPU time and memory on your own media before planning capacity for v0.7.3b2.

## Deploy and verify

- [Self-hosted verifier quickstart](docs/operations/verifier-quickstart.md) · runs a UI and API that distinguish valid claims, watermark recovery and incomplete checks.
- [Exporter + verifier + registry deployment kit](docs/operations/deployment-kit.md) · includes batch export, a read-only recovery service and a TLS edge. Plan for your own TLS/DNS and signing credentials in production.
- [Stock export lab](examples/stock_product/README.md) · illustrates a queued worker and a separate verifier. See also the [Node.js and Next.js backend guide](docs/guides/nodejs-nextjs.md) and [ComfyUI export nodes](https://github.com/ariadne-mark/ComfyUI-Ariadne-Mark).
- [Signed verification reports](docs/operations/signed-reports.md) · [C2PA recovery and registry publication](docs/operations/c2pa-recovery.md) · [C2PA runtime troubleshooting](docs/operations/c2pa-runtime.md).

A successful C2PA check validates the claim signature and its binding to the submitted file. The verifier reports issuer trust separately. A missing watermark does not establish human origin. Development signatures are for testing. Standalone audio and text marking, universal AI detection, and relaying already-signed upstream files unchanged are outside the supported workflow. See [supported formats and limits](docs/operations/support.md) and [verification semantics](docs/implementation/verifier.md).

## Evidence and requirements

For a pilot, exercise the signed final rendition, then check watermark recovery separately after metadata removal and the transformations your delivery pipeline actually performs. Measure throughput and check that the production verifier trusts your issuer.

- **Run your own checks:** [test protocols](docs/benchmarks/protocols.md), [reproducible durability benchmark](benchmarks/durability/README.md) and [sample artifacts](docs/benchmarks/samples.md).
- **Inspect external verification:** [C2PA interoperability evidence](https://ariadnemark.xyz/evidence/c2pa/).
- **Assess your workflow:** [requirements coverage](compliance/COVERAGE.md), [operator checklist and evidence template](docs/compliance/operator-evidence-template.md), and [offline product profile guide](docs/compliance/applicability.md).

[Documentation hub](docs/index.md) · [Troubleshooting](docs/operations/troubleshooting.md) · [Release qualification](docs/operations/releases.md) · [Release history](CHANGELOG.md)

## Feedback and contributions

[Start a discussion](https://github.com/ariadne-mark/ariadne-mark/discussions) with your media format, deployment environment and what happened. Use [Issues](https://github.com/ariadne-mark/ariadne-mark/issues) for reproducible bugs and sourced regulatory corrections, and [private security reports](https://github.com/ariadne-mark/ariadne-mark/security/advisories/new) for vulnerabilities. See [the contribution guide](CONTRIBUTING.md).

## License

Original code is [Apache-2.0](LICENSE). Dependencies and models retain their own licenses. See the [third-party inventory](THIRD_PARTY.md) and [commercial use guide](docs/operations/licensing.md).
