# Supported scope — 0.7.1a1 candidate

| Area | Supported | Boundary |
| --- | --- | --- |
| Images | Single-frame 8-bit RGB/RGBA PNG; JPEG; normalized EXIF orientation | Each dimension 256–4096 pixels. No animated PNG, HDR, CMYK, WebP export or arbitrary color-profile conversion |
| Video | SDR MP4 with H.264/HEVC input, H.264 output; one video stream; optional AAC audio | Even dimensions, each 256–1920 pixels; max 5 min / 18000 frames. Other audio codecs, subtitles, multiple tracks, interlacing, anamorphic pixels and HDR are rejected |
| Timing | Frame presentation timestamps retained, including tested VFR; display rotation normalized | Economy selects 125 ms windows every 5 s (default) or 2 s; the first observed frame in each occupied period is included even after a VFR gap. No whole-video coverage inference |
| Audio | AAC packets retained; original/synthetic/unknown provenance recorded | No standalone audio processing or independent audio watermark. Extraction/transcoding of synthetic audio is not covered |
| Watermark | Images: TrustMark Q/BCH-5. Video: Economy 5s/2s or per-frame Resilient, with blind search and cached-logit aggregation; legacy formats retained. Both carry 48 random ID bits | Search limited to 2000 frames / 120 s / 512 aggregate hypotheses by default. Budget exhaustion is not a negative. Exploratory aggregate FPR is not population-calibrated. Recoverable ID, not authentication |
| Provenance | Signed C2PA record: publisher, generator/version, time, UUID, created/altered; parent ingredient when applicable | Caller supplies accurate facts. External certificate issuance and public trust enrollment are operator responsibilities |
| Recovery | Local SQLite records and exact signed manifests; read-only soft-binding API subset for explicitly published entries | Provisional algorithms, no global discovery/central resolver or guaranteed hosting |
| Disclosure | Optional baked-in AI-generated/AI-altered label | Caller determines applicability and provides accessible in-app disclosure |
| Profiles | Offline EU/California product requirement planning; versioned source catalog and export receipts | Partial legal mapping; no deployment verification or legal determination. Profiled synthetic-audio exports unsupported |
| Runtime | Tested Linux x86-64, Python 3.12, 2 CPU / 8 GiB host | GPU unnecessary. The C2PA media guard requires the pinned Linux x86-64/Python3.12 pair; other media platforms are unqualified |

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

The retained legacy VideoSeal encoder can fail read-back on saturated synthetic color bars after H.264 compression. Such exports are rejected; no file or receipt is published. This content-dependent boundary is covered by a regression test. Do not infer universal durability from the supported dimensions.

## Publication boundaries

Signed outputs must be at most 512 MiB, matching the default upload verifier.
ICC-tagged images require explicit color conversion before SDK processing;
the SDK does not silently drop a tagged color space. The built-in visible
label remains an English reference component, not a complete localization or
accessibility solution. Credentialed inputs must use `action=altered` to retain
their parent history; re-watermarking is not represented as creation from nothing.

The media file is the publication commit marker. Its registry row (if used)
and a complete, fsynced receipt are written before that file appears. A process
crash earlier may leave an unpublished registry row/receipt and private temp
directory; these do not establish a completed export. The single-worker product
example reconciles its own unpublished job state on retry. Generic applications
must manage orphan cleanup and retry/idempotency outside `SDK.mark`. No atomic
transaction spanning SQLite and two arbitrary filesystem paths or universal
power-loss guarantee is claimed.

## Decoder and service boundaries

MP4 preflight uses ffprobe; the actual PyAV video/audio codec contexts are
checked for H.264/HEVC and AAC before decoding, with file-only protocol access.
PyAV bundles its own FFmpeg libraries, separately inventoried from system FFmpeg. This narrows the accepted format surface; it does not establish safety
of all malformed media. Run untrusted uploads in the bounded isolated worker
described in the deployment guide. Standalone verification closes temporary
video workers; callers retain ownership of reusable workers they provide.
Production verifier startup rejects empty/key-bearing files, known development
roots, expired/not-yet-valid roots and non-CA certificates. Operator-selected
roots define a trust policy; parsing a CA does not authenticate an organization.

Unsigned image checks use the Python TrustMark image scheme and need no Node.
`algorithm_scope` records that scope: a negative does not rule out a different
payload in an extracted video frame. A verified signed algorithm still routes
to its required decoder; failure remains not_checked. A video-only installation
without legacy decoders cannot establish a negative across legacy formats.

Staging currently uses a mode-0700 temporary directory adjacent to the output.
Do not expose that parent recursively through a static web server: dot-path
filtering and explicit download routes are deployment requirements. Process-kill
orphans and receipt reconciliation still require application-level cleanup.

See [C2PA runtime preflight](c2pa-runtime.md) for mismatched installations and
[short/excerpt limits](../implementation/video-profiles.md#short-clips-excerpts-and-deliberate-removal)
for temporal coverage. Historical validation records retain their original versions.
