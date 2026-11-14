# Ariadne Mark documentation

SDK **0.7.3a3 candidate** · documentation updated **2026-11-14**.

Versioned benchmark and legal-source review dates below remain historical evidence;
they are not a new qualification or legal approval of this candidate.

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

- [Previous published baseline qualification](validation/0.7.2a1-results.md).
- [Testing protocols](benchmarks/protocols.md) and [versioned evidence index](benchmarks/evidence-index.md).
- [Result terminology](reference/glossary.md).

The qualified SDK commit is `8c6fda81b27c5c6c0c9539bbbc3daef7e285b1fa`. Documentation can be updated separately;
a new docs commit does not imply that a rebuilt wheel has been qualified. The
existing wheel/source hashes remain in the [qualification record](validation/0.7.2a1-results.md).
Historical validation pages describe their original versions, datasets and machines.

## Practical adoption guides

- [Startups: role, market and publication checklist](guides/startups.md)
- [Node.js, Next.js and mobile backends](guides/nodejs-nextjs.md)
- [Cost of labeling](guides/cost.md)
- [Visible labels versus watermarks](guides/labels.md)
- [Components, kits and managed alternatives](guides/alternatives.md)
- [Troubleshooting](operations/troubleshooting.md)
- [Downloadable SDK sample exports](benchmarks/samples.md)

- [0.7.3a3 adoption fixes: install, image identity, memory, TSA boundary](operations/release-0.7.3a3.md).
- [0.7.3a1 candidate fixes and remaining qualification](operations/release-0.7.3a1.md).
