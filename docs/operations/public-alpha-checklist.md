# Public alpha checklist — 0.7.1 candidate

Release target: local CPU SDK for JPEG/PNG and supported SDR MP4, with
Economy5s/2s and Resilient video, signed provenance, self-hosted verification and partial
EU/California requirements planning. Assets: Ariadne wheel + source + Docker
recipe. A maintained hosted service and a prebuilt combined image are separate.

| Order | Priority | Item | Acceptance condition |
| --- | --- | --- | --- |
| 1 | P0 | Dependencies and licensing | Patched C2PA/native runtime and npm zip dependency; exact pins, notices, audit coverage and remaining native findings recorded. Combined-image redistribution separately qualified. |
| 2 | P0 | Public API failures and resource ownership | Temporary decoders closed, reusable workers retained, startup roots validated, unsupported codecs rejected; real-engine regressions pass. |
| 3 | P0 | Legal mapping and public claims | Current primary-source review recorded; executable profiles retain partial measures and operator duties; no universal compliance claim. |
| 4 | P0 | Exact release revision and CI | Python matrix, CPU media and requirement checks pass for the final commit; same built wheel tested and hashed. |
| 5 | P1 | Clean developer installation | Fresh supported environment installs the delivered wheel, explicitly provisions dependencies/models, exports and verifies both image/video without source-tree imports. |
| 6 | P1 | Public release package | Version/tag, wheel/source hashes, release notes, supported scope, benchmark context, examples and feedback/security links published together. |

The order reflects release blockers, not the importance of future programs.
Existing performance/robustness evidence is retained. A new broad benchmark
campaign is justified when algorithm/profile settings change, not for every
documentation or packaging revision.

A self-hosted verifier exists in the SDK. A provider must still deploy its
endpoint, configure trust/privacy/feedback, and assess its own duties. Public
hosting of an Ariadne-operated verifier is not a prerequisite for this local
alpha.

See [current qualification protocol](../validation/0.7.1a2.md),
[prior video qualification](../validation/0.7.1a0.md) and
[qualification rules](releases.md) for publication gates.

0.7.1 follow-up adds explicit color handling, bounded fractional-FPS recovery
and canonical BCH5 guards. Severe portrait crops and letterbox recovery are
separate qualification items; a cropdetect feasibility result is not a public
verifier capability. A clean CI run for the final commit, published source
licenses/notices, operator credentials and accurate public claims remain gates.

0.7.1a1 checks the actual loaded native C2PA pair at media/verifier startup and
adds current-version short/excerpt and public-remover evidence. These checks do
not close spatial recovery, anti-removal, population calibration, production
trust enrollment or the public release/publishing gates above.

0.7.1a2 closes the reviewed full-range bypass and wheel-provisioning code gaps;
actual release qualification is the exact-SHA EC2 workflow artifact, not this
checklist's presence. [Server CI](server-ci.md) uses a temporary one-job runner
for a trusted maintainer dispatch. SDK tests are not run on GitHub-hosted or
Mac environments. Automatic PR notices do not satisfy the runtime gate.
