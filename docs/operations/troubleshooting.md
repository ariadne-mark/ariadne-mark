# Troubleshooting an image or video export

Start with `ariadne runtime check` and the exact SDK version. Keep the command,
exit code, structured result and a public/synthetic reproduction; remove keys,
user media, messages and local paths before opening an Issue.

| Symptom | Check and next action |
| --- | --- |
| Native C2PA mismatch | Use the qualified Linux x86-64/Python 3.12 setup. Run `ariadne setup media --fetch-models` in a fresh venv; restart workers. Do not install an older available C2PA version to suppress the check. |
| Missing model / checksum failure | Run explicit setup with network access. Check free disk and proxy access to pinned upstream files. Processing deliberately does not fetch missing files. |
| Node, npm, FFmpeg or ffprobe missing | Install system prerequisites, or use the matching Docker recipe. npm is needed during setup, not normal video processing. |
| `Final read-back failed` | The signed candidate failed its own export read-back and was rejected: no output, success receipt or registry entry was written. See [Final read-back failed](#final-read-back-failed) below. |
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

## Final read-back failed

Before publishing anything, `ariadne mark` (`SDK.mark`) reads back the signed
candidate it just produced. The error reports the C2PA status, the watermark
status and `matching frames=<matched>/<checked>`, and ends with
`no output published`. The CLI prints it to stderr as
`{"error": "VerificationFailed", "message": "Final read-back failed: ..."}` and
exits with code 2.

- **The export was not accepted.** The temporary candidate is discarded. This
  path writes no output file, no success receipt and no registry entry, so there
  is no receipt to inspect. In a kit batch, earlier committed jobs keep their
  own receipts; the failed job has none.
- **What the gate requires.** C2PA must be a verified claim carrying the same ID
  and record, the watermark must be a recovered claim with that same ID, and no
  checked frame may return a different ID.
- **Economy vs Resilient (video).** `economy_5s` and `economy_2s` check the
  known scheduled windows: every occupied window needs at least one decoded
  matching ID, and individual unreadable frames are tolerated. `resilient` (and
  legacy `fast`) decodes five uniform samples, and every sample must return the
  same ID. `matching frames` counts these read-back observations only; it is not
  whole-file coverage. See
  [export read-back](../implementation/video-profiles.md#export-read-back-and-blind-verification).

For an Issue, keep the exact SDK version, the command and settings (product
profile, `--video-profile`, `--visible`, `--audio-kind`), the
`ariadne runtime check` result, the full stderr JSON with the exit code, the
SHA-256 of the input asset, and a reproducible input you are allowed to share.
Remove keys, secrets, private user media/data and local paths first.

Do not publish the unmarked source in place of the rejected output, and do not
disable or patch around the gate. Another video profile is not guaranteed to
pass; a retry that passes is a new export with its own read-back and receipt.
