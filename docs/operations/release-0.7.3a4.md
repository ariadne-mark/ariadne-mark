# Ariadne Mark 0.7.3a4 developer alpha

This release addresses the low/info follow-ups from the independent 0.7.3a3
review. It is a developer alpha, not a legal certificate or production qualification.

- Q-01: bounded parallel loopback TSA handling, absolute two-second local
  header/body deadline, bounded overload and active-connection shutdown.
- Q-03: a trusted claim no longer narrows explicit all/custom historical scope.
  Missing historical decoders remain visible instead of yielding a false negative.
- Q-02/Q-04: document the shared export/verify worker lock and its queue wait,
  separate-process deployment, and the limits of local image/RECORD identity.
- Q-05: quiet expected disconnects; retain strict file permissions without a
  universal UID-equality rule that would reject valid container secrets.
- Q-06: cache policy is recorded by qualification; no earlier run is relabelled.
- C-01: [resolver discovery acceptance](resolver-discovery.md) distinguishes
  implemented own-registry recovery from unqualified third-party discovery.
- C-02: synthetic audio remains outside the visual SDK and blocked by profiles.

Economy5s remains the default; Economy2s and Resilient remain selectable. No
watermark cadence, strength, payload format or read-back threshold changes.
The previous [0.7.3a3 release note](release-0.7.3a3.md) remains historical.

Qualification is recorded for the exact candidate SHA and artifacts in CI.
Do not reuse an earlier version's timing or qualification as evidence for this one.

Published [v0.7.3a4](https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.3a4) uses the unchanged qualified artifacts from `49578688710a8bae2373aaf9d47ff9521f566d4c`.
[Exact qualification](../validation/0.7.3a4-results.md) records the checks and boundaries.
