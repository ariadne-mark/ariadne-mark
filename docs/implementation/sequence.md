# Implementation status

The image-only stage was internal: the first media preview includes both images
and MP4 video.

Completed for 0.2.0a0: installable core, CPU TrustMark adapter, C2PA signing and
read-back, timestamp-preserving video path, AAC retention, local registry,
optional visible label, self-hosted UI/API, real-engine tests, Docker recipe and
measured smoke benchmark. See [release evidence](../validation/0.2.0a0.md).

Added in 0.3.0a0: CPU VideoSeal video adapter, BCH-protected IDs, multi-frame
verification, legacy-video dispatch and explicit model provisioning. See
[VideoSeal release evidence](../validation/0.3.0a0.md).

Added in 0.4.0a0: versioned offline EU/California requirement planning, strict
product configuration, and profile-bound image/video export receipts.
See the [profile guide](../compliance/applicability.md).

Remaining before broad production/compliance claims:

1. Representative product datasets, broader transformations and adversarial tests.
2. Production credential/trust/revocation operations and public verifier hosting.
3. Real load/queue/crash recovery qualification and deployment privacy review.
4. Independent review of the partial executable legal mapping, official California
   source reconciliation and full Code of Practice assessment.
5. Independent synthetic-audio marking where the product workflow requires it.
6. External interoperability testing and, where useful, standard soft-binding routing.
7. Landing page and adoption materials that accurately reflect verified scope.

These are not silently marked complete because a small smoke suite passes.
