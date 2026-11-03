# Release qualification

0.4.0a0 is a developer preview with a wheel, source code, reproducible Docker
recipe, real-engine tests and CPU evidence. It adds an offline EU/California
requirements planner and optional export configuration. Automatic legal
determinations, public certificate enrollment and PyPI publishing are not included.

The required CI gate depends on both the Python 3.11–3.14 core matrix and the
CPU Docker media suite. Media tests use actual TrustMark/VideoSeal/C2PA/FFmpeg with
networking disabled. Model SHA-256 hashes and tested package versions are
recorded. Legal-mapping requirements stay in progress until independently
reviewed against their operative sources and applicability.

For a subsequent release, rebuild, run the real-engine suite, benchmark the
changed pipeline, update support limits and source mappings, inspect dependency
licenses/security updates, and link evidence to the exact release commit.
