# Ariadne Mark

**Open-source compliance toolkit for AI-generated images and video.**

Watermarking, C2PA provenance, and verification — built to help developers implement applicable content-labeling requirements, with an initial focus on the EU AI Act and California.

> **Pre-alpha: SDK core only.** Installable from source: provenance records and verification result contracts. No watermarking, C2PA signing, media processing, or production verifier is included yet. No package has been published to PyPI.

## What we are building

- CPU-first invisible watermarking for images and video.
- Signed provenance with publisher, system, creation/editing, and asset information.
- A self-hostable verifier with clear verification and error states.
- Versioned requirement profiles linked to implementation, tests, and developer guidance.

Standalone music/audio watermarking is outside the initial scope. Synthetic audio within video needs an explicit supported workflow before full video coverage can be claimed.

## Requirements you can trace

Every requirement has an ID, an acceptance criterion, implementation and test locations, documentation, and a separate verification status.

| Entry point | Purpose |
| --- | --- |
| [Coverage checklist](compliance/COVERAGE.md) | Track all 15 initial requirements |
| [Requirement records](compliance/requirements.json) | Machine-readable source of truth |
| [Official-source registry](compliance/sources/index.json) | Legislative sources and release-review status |
| [Contributing](CONTRIBUTING.md) | How to propose code, tests, and regulatory corrections |
| [Security](SECURITY.md) | Private vulnerability reporting |

Initial detailed planning documents are in Russian; the public documentation will expand alongside implementation. [Russian project overview](docs/README.ru.md).

## Repository layout

```text
src/ariadne_mark/   Watermarking, provenance, signing, video, registry,
                   verification, disclosure, and pipeline modules
apps/verifier/     Public verification UI and API
compliance/        Requirements, sources, profiles, and coverage
benchmarks/        Reproducible robustness and quality evaluation
tests/             Tests corresponding to the requirements
docs/              Integration, compliance, and operations guidance
```

The `provenance` and `verification` modules contain the first data contracts. Other module directories remain planning placeholders. These contracts describe images and video; they do not yet process either format.

## Install and try the core

Requires Python 3.11 or newer. There are no runtime dependencies, account requirements, API keys, model downloads, or network calls in the core. Installation needs Python build tooling; an already-built wheel can be installed offline.

```sh
git clone https://github.com/ariadne-mark/ariadne-mark.git
cd ariadne-mark
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python examples/provenance_record.py
python -m unittest discover -s tests -t . -v
python3 scripts/check_requirements.py
```

The example creates an **unsigned record**, with a random asset ID and the supplied generator name/version. It does not change any media file. The unit tests validate data and result semantics; `check_requirements.py` checks traceability metadata and paths. Neither establishes legal compliance.

See [provenance records](docs/implementation/provenance.md), [verification results](docs/implementation/verification-results.md), and the [implementation sequence](docs/implementation/sequence.md).

## Participate

- Use [Discussions](https://github.com/ariadne-mark/ariadne-mark/discussions) for questions and integration needs.
- Use [Issues](https://github.com/ariadne-mark/ariadne-mark/issues) for reproducible problems, feature requests, and sourced regulatory corrections.
- Link implementation changes to a requirement ID and include evidence before marking it verified.
- If this project is useful to you, give it a star.

## License

Original project code and documentation are licensed under [Apache-2.0](LICENSE). Third-party code, model weights, standards, and legislative documents retain their own applicable terms; the project license does not relicense them.
