# Video export

REQ-005. VideoSeal 1.0 is the default video engine in 0.3.0a0. Images retain TrustMark Q/BCH-5. The official Meta TorchScript model is loaded on CPU only after SHA-256 verification. Provision it during setup; inference never downloads weights.

PyAV processes four frames at a time. The pinned model uses temporal repetition with step size four; this is not four independent model calls. The last incomplete batch is processed too. Original presentation timestamps survive VFR export and display rotation is normalized into pixels. H.264 uses CRF 18 and two encoding threads; FFmpeg remuxes original AAC packets. C2PA signs the resulting MP4. Failed final verification publishes neither media nor receipt.

## Payload and verification

The 256-bit payload (`ariadne-vs1`) is 16-bit ASCII AM + the existing 64-bit stored token + CRC-32 of those ten bytes + 140 BCH parity bits + four zero padding bits. The token contains the same 48 random ID bits as images. BCH uses t=20, primitive polynomial 285, through TrustMark's MIT-licensed implementation. After correction, the decoder checks prefix, CRC and distance from the re-encoded codeword (at most 20 differing bits). This is error correction, not cryptographic authentication.

The verifier samples up to five positions. It decodes each frame and the mean of the 256 detector logits. Both paths require exact CRC-valid ID recovery; an aggregate cannot hide a conflicting recovered frame ID. `corrected_bits` measures Hamming distance, not a calibrated confidence probability. No claim is made about all frames or arbitrary transformations.

Valid Ariadne C2PA metadata selects the declared supported engine. Without it, verification checks VideoSeal and legacy TrustMark, reporting partial coverage or operational failure when an engine is unavailable. Legacy TrustMark exports remain readable, including after metadata removal. To explicitly produce a legacy video from Python, pass `video_marker=marker` to `SDK`, where `marker` is the existing TrustMark instance.

`--audio-kind` records original/synthetic/unknown audio provenance. Audio is covered by the signed MP4 binding but is not independently watermarked. Extracted or transcoded synthetic audio is outside this workflow.

[Supported scope](../operations/support.md) · [Validation](../validation/0.3.0a0.md)
