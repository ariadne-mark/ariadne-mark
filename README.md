# Ariadne Mark

**Open-source compliance toolkit for AI-generated images and video.**

Watermarking, C2PA provenance, and verification — built to help developers implement applicable content-labeling requirements, with an initial focus on the EU AI Act and California.

> **Pre-alpha: repository scaffold.** No installable SDK or production verifier has been released. Planned capabilities below are not claims of implemented features or legal certification.

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

The module directories currently contain planning placeholders, not working implementations.

## Check this scaffold

Requires Python 3.9 or newer; no third-party Python dependencies.

```sh
git clone https://github.com/ariadne-mark/ariadne-mark.git
cd ariadne-mark
python3 scripts/check_requirements.py
```

This checks traceability metadata and local paths. It does **not** run watermarking or establish legal compliance.

## Participate

- Use [Discussions](https://github.com/ariadne-mark/ariadne-mark/discussions) for questions and integration needs.
- Use [Issues](https://github.com/ariadne-mark/ariadne-mark/issues) for reproducible problems, feature requests, and sourced regulatory corrections.
- Link implementation changes to a requirement ID and include evidence before marking it verified.
- If this project is useful to you, give it a star.

## License

Original project code and documentation are licensed under [Apache-2.0](LICENSE). Third-party code, model weights, standards, and legislative documents retain their own applicable terms; the project license does not relicense them.
