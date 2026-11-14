# Historical 0.7.3a0 migration record: migration, setup and known issues

This is a local developer-alpha candidate, not a published release or legal certification.
The previous public package is 0.7.2a1. Do not label the new schema-2 wheel as that version.
Qualification results are delivered with the exact candidate SHA outside this document.

## Installation and legacy models

`ariadne setup media --fetch-models` and default `ariadne models fetch` provision
TrustMark images and current Q video. The committed Dockerfile takes the same path.
They do not download legacy VideoSeal from Meta. Explicit `models fetch --engine
videoseal` or `--engine all` still fails on an unavailable requested download;
TLS verification is never disabled. `ARIADNE_VIDEOSEAL_MODEL` accepts only the
existing hash-pinned model. Legacy operator compatibility is optional setup.
No model weights are included in the wheel and no combined GPL binary image is distributed.

## Operator detection scope

Existing SDK and CLI defaults remain `all`. New kits explicitly set
`verification_scope: "current"` in `config/kit.json`. An old kit with no field
keeps `all`; edit it only after checking what that operator has issued.

```python
from ariadne_mark.pipeline import SDK
with SDK(verification_scope="current") as verifier:
    report = verifier.verify("export.mp4")
```

```sh
ariadne verify export.mp4 --verification-scope current
ariadne serve --verification-scope current
```

`current` covers the supported image/video TrustMark-Q payloads, excluding
VideoSeal. Python Q may contribute additional sampled video reads of the
compatible payload; if absent in a video-only install it is an unavailable
auxiliary decoder. The primary Q decoder is still required. `not_found` is
limited to declared techniques and performed search; it is never a global AI detector.
A signed out-of-scope technique returns `not_checked`, not `not_found`. Required
decoder failures and exhausted search budgets remain incomplete.

## Report schema 2 and recovery

Consumers must handle `multiple_ids`, unconfirmed observations, bounded positions
and `evidence_scope`. `signed_id_observed` reports whether the signed watermark
ID was observed; absence is not proof of tampering. `token_mismatch` retains its
single-token conflict meaning. UI shows positions for a single ID too. First/last
read positions do not establish coverage of the interval between them.

A finite directional compatibility table allows Python Q/BCH-5 video observations
to locate the video-Q manifest schema. The original algorithm identifier and token
are still checked inside the recovered signed store; the signature is validated.
This is not an alias of VideoSeal, a merge of observations, or authentication of
an edited/spliced copy. Recovery with multiple IDs requires an explicit selector.

## Mode selection

Economy5s remains the direct SDK default. Economy2s and Resilient remain available.
A product/compliance profile missing `sdk.video_profile` no longer silently inserts
Economy5s: it reports `video_profile_required` and blocks profiled video export.
The template proposes Economy5s as an editable value; review it for the product.
Optional `sdk.video_profile_reason` records the operator's cost/delivery/evidence
rationale in the profile result. It does not establish statutory sufficiency.

## Known limits

- Economy sparse windows can be absent from screenshots, short excerpts and
  deliberately replaced frames. Early stopping can miss a later ID.
- Crop/letterbox transformations and the public TrustMark remover remain weaknesses;
  Resilient is not attack-proof. No preset is certified legally sufficient.
- Long negative scans may hit the bounded budget and return `not_checked`.
- Media qualification is Linux x86-64/Python 3.12; core support is separate.
- Production issuer trust, timestamps, public hosting and product obligations
  remain operator setup. Development keys are not production credentials.
- Native `bmffHash.additionalExclusionsPresent` reflects the qualified C2PA
  library's default BMFF exclusion rules. A valid hash covers the specified ranges;
  it does not promise that every container box is authenticated. No custom
  exclusions were introduced in this release.

## Evidence boundaries

Source identity of `SDK.mark` is a static fact, not proof that its downstream
verification decisions are unchanged. Behavioural gate regressions and actual
export/read-back tests are required. The old R2 "interleaved" fixture dropped its
one-frame segments and is not evidence of interleaved conflict detection. R3
replaces it with a frame-counted, pixel-labelled fixture and records outcomes.
The previous A/B selector result from a diagnostic adapter must not be presented
as evidence of the shipped verifier; R3 checks the shipped path separately.
