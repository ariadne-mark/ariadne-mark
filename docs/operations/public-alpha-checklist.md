# Public alpha checklist — 0.5.2 candidate

Release target: local CPU SDK for JPEG/PNG and supported SDR MP4, with
Fast/Resilient video, signed provenance, self-hosted verification and partial
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

See [release evidence](../validation/0.5.2a0.md) for current results and
[qualification rules](releases.md) for publication gates.
