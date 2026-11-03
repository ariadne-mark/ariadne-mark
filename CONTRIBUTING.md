# Contributing to Ariadne Mark

The repository is currently a developer-preview media SDK. Implementation, integration examples, reproducible benchmarks, and corrections to the requirements mapping are welcome.

## Before a change

For substantial design changes, open an issue or discussion first. For a concrete correction, a pull request is welcome directly. Follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Requirement-driven changes

1. Link the change to a `REQ-ID` in `compliance/requirements.json`.
2. For regulatory changes, provide the official source, exact provision, version, effective date, applicability, and exceptions. Distinguish binding law, voluntary guidance, and engineering choices.
3. Implement the acceptance criterion and add appropriate executable checks. A unit test does not replace an end-to-end scenario.
4. Update relevant documentation and the coverage checklist in the same change.
5. Install the package with `python -m pip install .`, then run `python -m unittest discover -s tests -t . -v` and `python3 scripts/check_requirements.py`. CI tests the built wheel on Python 3.11–3.14; all versions and the real-engine CPU Docker job must pass the required traceability check.

Implementation states: `planned`, `in_progress`, `implemented`.
Verification states: `not_run`, `failed`, `passed`.

A `passed` result needs implementation plus evidence identifying the commit/version, environment, command, result, and scope. Upstream audit results are useful references, not proof of this project's implementation. A checked requirement does not certify every obligation of a deployed product.

## Pull requests

Explain the user-visible problem, resulting behavior, and validation. Keep changes focused. Do not add credentials, personal uploads, production data, model weights, or large generated artifacts. Record the licenses and provenance of third-party material before inclusion.

No CLA or DCO signing requirement is currently imposed. Contributions are submitted under the repository's Apache-2.0 license unless a separately identified third-party license applies.

## Security

Report exploitable issues privately using [Security Advisories](https://github.com/ariadne-mark/ariadne-mark/security/advisories/new), not a public issue. See [SECURITY.md](SECURITY.md).
