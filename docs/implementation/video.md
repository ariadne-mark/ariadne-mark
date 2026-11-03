# Video export

REQ-005. PyAV decodes frames and preserves presentation timestamps while TrustMark marks every frame. H.264 export uses CPU, CRF 18 and two encoding threads. Video uses a 1.5× watermark-residual strength to reserve a margin for codec losses; images retain the default strength. Display rotation is normalized into pixels. FFmpeg remuxes AAC packets without re-encoding them. C2PA signs the final MP4, then native binding validation and watermark samples must succeed before publication.

Tests exercise short, vertical, VFR and rotated videos, matching frame timestamps and exact compressed AAC packets. See [support limits](../operations/support.md) and [evidence](../validation/0.2.0a0.md).

`--audio-kind` records original/synthetic/unknown audio provenance. Audio is covered by the signed MP4 binding but is not independently watermarked; extracted/transcoded synthetic audio is not a supported marking workflow. A five-frame verification sample is not a claim that every transformed frame carries a recoverable mark.
