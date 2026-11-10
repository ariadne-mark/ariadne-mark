# Troubleshooting an image or video export

Start with `ariadne runtime check` and the exact SDK version. Keep the command,
exit code, structured result and a public/synthetic reproduction; remove keys,
user media, messages and local paths before opening an Issue.

| Symptom | Check and next action |
| --- | --- |
| Native C2PA mismatch | Use the qualified Linux x86-64/Python 3.12 setup. Run `ariadne setup media --fetch-models` in a fresh venv; restart workers. Do not install an older available C2PA version to suppress the check. |
| Missing model / checksum failure | Run explicit setup with network access. Check free disk and proxy access to pinned upstream files. Processing deliberately does not fetch missing files. |
| Node, npm, FFmpeg or ffprobe missing | Install system prerequisites, or use the matching Docker recipe. npm is needed during setup, not normal video processing. |
| Output already exists | Choose a new destination. Inspect the previous receipt before retrying; never treat an unmarked original as successful output. |
| Development / untrusted issuer | Expected with `init-dev`. Follow production onboarding for your own credentials. Adding a test root locally does not create public C2PA trust. |
| Production timestamp failed | Check the configured HTTPS TSA, egress, quota and TSA roots. Keep failed candidates private; never bypass failure by publishing the original. |
| Video metadata lost on social upload | Verify the downloaded rendition. Recoverable ID and C2PA metadata are separate layers. Mark each final crop/rendition before publishing. |
| Watermark not found | Check supported format, dimensions, transforms and scan completeness. No recovered mark is not evidence of human origin. |
| `not_checked` / budget exhausted | This is incomplete inspection, not a negative. Increase the documented verifier budget for trusted offline investigation or retain the incomplete result. |
| Conflicting IDs / unverified content match | Do not turn a recovered ID into a clean whole-file origin claim. Preserve the structured result and investigate the source/renditions. |
| Slow video | Reuse a worker/SDK, queue jobs, compare Economy5s/2s with Resilient on your clips. Every video frame still needs decode/encode. |
| Out of memory | Limit concurrent jobs before adding processes. The image runtime includes Torch; video-only setup omits it. A 6 GiB test limit is not measured RSS. |
| Clean image cannot get a complete negative | Check installed engines and result completeness. Video-only installs omit image/legacy decoders. |

See [supported media](support.md), [runtime qualification](c2pa-runtime.md),
[video profiles](../implementation/video-profiles.md), [production setup](production-onboarding.md)
and [private security reports](../../SECURITY.md). Include the asset SHA-256 and
receipt when available; do not post provider signing keys or the registry database.
