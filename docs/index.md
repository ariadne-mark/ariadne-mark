# Ariadne Mark documentation

SDK **0.7.2a1** · documentation review **2026-11-10**.

Start here if you run a generative image/video product and want to add marking,
signed provenance and verification at export. Use the qualified Linux CPU kit,
choose a mode for your delivery workflow and retain evidence of your implementation.

## Install and integrate

- [First export](start-here.md): installation, supported scope and expected results.
- [Python integration](implementation/integration.md): persistent workers, records and retries.
- [CLI and API reference](reference/api-cli.md): commands, result fields and exit codes.
- [Final renditions](implementation/final-renditions.md): crop/resize before marking.
- [Video modes](implementation/video-profiles.md): Economy5s, Economy2s and Resilient.
- [Supported formats](operations/support.md): dimensions, codecs, audio and known limits.

## Verify and operate

- [Complete deployment kit](operations/deployment-kit.md): SDK, verifier and registry.
- [Production onboarding](operations/production-onboarding.md): identities, trust, TLS and launch checks.
- [Verifier operations](operations/verifier.md), [signed reports](operations/signed-reports.md)
  and [manifest recovery](operations/c2pa-recovery.md).
- [Licences and redistribution](operations/licensing.md).
- [Data handling](operations/privacy.md), [CPU operation](operations/cpu-deployment.md)
  and [native-runtime diagnostics](operations/c2pa-runtime.md).

## Understand applicable requirements

- [EU Article 50 guide](compliance/eu-ai-act.md).
- [California provider guide](compliance/california.md).
- [Requirements matrix](compliance/requirements-matrix.md): norm, mechanism, evidence and remaining action.
- [Official excerpts and source status](compliance/source-excerpts.md).
- [EU voluntary Code mapping](compliance/eu-code-map.md).
- [Operator evidence template](compliance/operator-evidence-template.md).

## Inspect the evidence

- [Latest qualification results](validation/0.7.2a1-results.md).
- [Testing protocols](benchmarks/protocols.md) and [versioned evidence index](benchmarks/evidence-index.md).
- [Result terminology](reference/glossary.md).

The qualified SDK commit is `8c6fda81b27c5c6c0c9539bbbc3daef7e285b1fa`. Documentation can be updated separately;
a new docs commit does not imply that a rebuilt wheel has been qualified. The
existing wheel/source hashes remain in the [qualification record](validation/0.7.2a1-results.md).
Historical validation pages describe their original versions, datasets and machines.
