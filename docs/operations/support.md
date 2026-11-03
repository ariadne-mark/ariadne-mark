# Supported scope — 0.3.0a0

| Area | Supported | Boundary |
| --- | --- | --- |
| Images | Single-frame 8-bit RGB/RGBA PNG; JPEG; normalized EXIF orientation | Each dimension 256–4096 pixels. No animated PNG, HDR, CMYK, WebP export or arbitrary color-profile conversion |
| Video | SDR MP4, H.264 output; one video stream; optional AAC audio | Even dimensions, each 256–1920 pixels; max 5 min / 18000 frames. Other audio codecs, subtitles, multiple tracks, interlacing, anamorphic pixels and HDR are rejected |
| Timing | Frame presentation timestamps retained, including tested VFR; display rotation normalized | Verification samples up to 5 positions, not every frame |
| Audio | AAC packets retained; original/synthetic/unknown provenance recorded | No standalone audio processing or independent audio watermark. Extraction/transcoding of synthetic audio is not covered |
| Watermark | Images: TrustMark Q/BCH-5. Video: VideoSeal 1.0 with BCH-20/CRC; five-frame aggregate. Both carry 48 random ID bits | Recoverable ID, not authentication. Cropping/removal/copying may defeat it |
| Provenance | Signed C2PA record: publisher, generator/version, time, UUID, created/altered; parent ingredient when applicable | Caller supplies accurate facts. External certificate issuance and public trust enrollment are operator responsibilities |
| Recovery | Local SQLite token-to-record lookup | No central resolver, cross-provider routing or guaranteed permanent hosting |
| Disclosure | Optional baked-in AI-generated/AI-altered label | Caller determines applicability and provides accessible in-app disclosure |
| Runtime | Tested Linux x86-64, Python 3.12, 2 CPU / 8 GiB host | GPU unnecessary. Native/macOS/Windows media bundles have not been validated |

The 61-bit watermark payload is not the 128-bit public asset UUID. The signed
record and optional registry map the two. Registry inserts enforce uniqueness;
a collision or registry failure aborts the export. Public IDs are not user IDs.

Processing strips ordinary image metadata rather than copying possible private
EXIF fields into the export. It preserves prior C2PA history as an ingredient;
it does not make an old issuer trusted. The SDK cannot detect personal data
placed by a caller inside publisher/system strings. Keep those fields limited
to public organizational and model information.

All inference is local after model provisioning. C2PA remote-manifest and OCSP
fetching are disabled. Revocation freshness is therefore not checked offline.
Only a caller-configured timestamp authority enables a signing-time network
request. Output receipts document technical actions, not a legal verdict.

Default VideoSeal can fail read-back on saturated synthetic color bars after H.264 compression. Such exports are rejected; no file or receipt is published. This content-dependent boundary is covered by a regression test. Do not infer universal durability from the supported dimensions.
