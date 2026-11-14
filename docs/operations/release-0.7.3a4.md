# Ariadne Mark 0.7.3a4 candidate

This candidate addresses the low/info follow-ups from the independent 0.7.3a3
review. It is not a legal certificate or a published production release.

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
