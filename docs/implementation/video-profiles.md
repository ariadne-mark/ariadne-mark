# CPU video profiles — 0.5 developer preview

The CLI `--video-profile fast|resilient` and Python `SDK(video_profile="fast")`
select the encoder. Both mark every frame and use the same TrustMark Q models
and new `ariadne-vq1` payload format. Older `ariadne-v1` and VideoSeal
`ariadne-vs1` are routed to their respective legacy decoders.

| Profile | Computation | Detection |
|---|---|---|
| fast (default) | Refresh when scene distance exceeds 0.10, at most 24 frames | 5 uniform timeline samples, then 20 if absent |
| resilient | New signal for every frame, strength 1 | Same |

The detector receives no expected ID. Individual decoded IDs and aggregate
logits must agree; conflicting IDs are rejected. Both attempts are returned.
A valid C2PA engine identifier routes detection directly. Without it, the full
installation checks the new and legacy bit layouts. Missing engines mean
incomplete coverage, not evidence of a human-created file.

The profile ID is a signed publisher assertion, not proof that a particular
transformation will be survived. 90% is only a contextual benchmark warning;
there is no accuracy cutoff in the SDK and no claimed statutory percentage.

## Install

Use Docker for the complete CPU bundle, including old-format compatibility:

```sh
docker build --platform linux/amd64 -t ariadne-mark:0.5 .
docker run --rm --network none ariadne-mark:0.5 models check
```

For a new-video-only Python installation, install Node.js (tested 24) and npm plus
FFmpeg/ffprobe, then install `.[video]` (or the wheel with the video extra):

```sh
python -m pip install .
python -m ariadne_mark.bootstrap_c2pa
python -m pip install '.[video]'
ariadne models fetch --engine video
```

This avoids PyTorch for new-video encoding. The full `[media]` extra and all
model sets are needed for images and complete legacy compatibility. Install
CPU PyTorch wheels first as shown in README; the Dockerfile does this.

Provisioning is explicit and uses the packaged npm lockfile plus SHA-256 model
and source checks. Runtime requests never download code/models. The dependency
cache is `~/.cache/ariadne-mark/video-v1`, configurable by `ARIADNE_VIDEO_DATA`.
Docker preprovisions it under `/opt/ariadne-video`, readable by the runtime user.
Node24.22.2/Linux x86-64 is the tested 0.5.2 environment; other platforms require validation.

## Python

```python
from pathlib import Path
from ariadne_mark.pipeline import SDK
from ariadne_mark.signing import SigningIdentity
from ariadne_mark.registry import Registry

sdk = SDK(
    identity=SigningIdentity.from_directory(Path(".ariadne/dev"), allow_dev=True),
    registry=Registry(Path(".ariadne/registry.sqlite3")),
    video_profile="resilient",
)
# record: ProvenanceRecord with actual publisher/system/time and media_kind VIDEO
receipt = sdk.mark(Path("input.mp4"), Path("output.mp4"), record,
                   audio_kind="original")
result = sdk.verify(Path("output.mp4"))
sdk.close()
```

Each SDK owns a lazy persistent worker. Create one SDK per product worker and
reuse it. Shared-thread exports serialize access to the encoder and isolate
per-export caches; start separate SDKs in separate processes for parallel jobs.
After a worker failure, the export fails before publication; a later export
can create a fresh worker. Receipts contain model-call count, profile, total
processing seconds, signed-file SHA-256 and verification attempts.

## Supported export boundary

MP4 input/output, 8-bit SDR, one video track and optionally one AAC track,
square pixels, dimensions 256–1920 pixels per side, at most 5 minutes/18000 frames.
H.264 and HEVC decoding depend on FFmpeg/PyAV; output is H.264 CRF18/preset fast.
AAC bytes and timestamps are copied. Synthetic audio is not watermarked by
this visual SDK. VFR timing, portrait layout and 90-degree rotation are tested.

WebM/AV1/VP9 and 4K were research ingestion/load tests. This release's signed
export API remains MP4 within the boundary above. HDR, alpha, interlacing,
other audio codecs and anamorphic pixels require explicit conversion first.
A negative/incomplete watermark result never certifies human origin or truth.

## Evidence

Frozen selection references live in `benchmarks/video/profiles/`. Their settings
are used unchanged in this implementation, but runtime integration is a new
pipeline and its timings must be measured again. Selection used six known
720p24 scenes; matched transform recovery was 32/36 for Fast and 36/36 for
Resilient. Those figures are not independent validation or legal certification.
See `docs/validation/0.5.0a0.md` for installed-package results and timings.
