# Software licences attribution and redistribution

SDK **0.7.3a3 candidate** · documentation updated **2026-11-14**.

Versioned benchmark and legal-source review dates below remain historical evidence;
they are not a new qualification or legal approval of this candidate.

Ariadne's original code/documentation use [Apache-2.0](../../LICENSE).
Preserve the applicable licence, notices and required attribution/modification
information when redistributing. Trademark permission and a regulatory approval
are not supplied by that licence. The full terms, including warranty provisions,
control; free software does not make a provider's product duties disappear.

## Keep the distribution boundary explicit

| What you distribute | What to retain or assess |
| --- | --- |
| Ariadne wheel/source | Project licence, [third-party notice](../../THIRD_PARTY.md), original headers and attributed code modifications |
| Downloaded dependencies/models | Terms and notices for the exact pinned upstream files; another model/version may differ |
| Combined Docker image or bundled venv | Binary/component inventory, licences and applicable corresponding-source/build obligations; not Apache-only |
| Site documentation | Original documentation licence; short attributed legal excerpts and links retain source reuse terms |
| Hosted verifier | Your actual operator privacy, access, contact and support practices; not an invented hosted Ariadne SLA |

The qualified wheel/source include adapters, locks, checksums and attribution,
not Torch/Node/FFmpeg binaries or model weights. The Docker recipe provisions
those components explicitly. A prebuilt combined binary image is a separate
distribution channel and is not part of the candidate bundle.

## Component sources

The [inventory](../../THIRD_PARTY.md) identifies pinned versions and code/weight
origins. Primary references include [Adobe TrustMark licence](https://github.com/adobe/trustmark/blob/main/LICENSE),
[Meta VideoSeal licence](https://github.com/facebookresearch/videoseal/blob/main/LICENSE),
[Apache-2.0 terms](https://www.apache.org/licenses/LICENSE-2.0) and
[FFmpeg legal guidance](https://ffmpeg.org/legal.html). Upstream main pages are
navigation references; the exact redistributed revision and its terms govern.
The release inventory distinguishes system FFmpeg from PyAV's bundled codecs.
GPL-bearing x264/x265 components need separate redistribution assessment;
do not infer binary obligations solely from the top-level Python package licence.

A small Apache-2.0 C2PA vocabulary is attributed to its pinned Trufo source;
this does not include Trufo's proprietary engine, service credentials or trademark
rights. Public legislation, standards and third-party PDFs are not re-licensed
under Ariadne's Apache licence. Full official PDFs stay in maintainer source
review evidence; the website content uses short excerpts and source links.

## Reporting and deployment notices

Follow [private security reporting](../../SECURITY.md) for exploitable issues;
ordinary documentation/product feedback belongs in repository Issues. Avoid
attaching private keys or real user media. The self-hosted application privacy
page describes application defaults; operators must supply their own actual
hosting/contact/retention information as applicable. No response-time SLA or
public trust endorsement is created by publishing this documentation.

## Can a commercial app use this?

Yes: the original Apache-2.0 SDK does not require your app to be open source,
charge per export or prohibit commercial use. Keep the licence/notices when
redistributing the SDK. This permission does not replace the terms of the
dependencies, downloaded weights or bundled codecs in your actual distribution.

| Component in the qualified setup | Licence boundary to inspect |
| --- | --- |
| Ariadne original code | Apache-2.0; preserve attributed third-party portions |
| Adobe TrustMark code and supplied models | Upstream MIT terms; retain notice |
| Meta VideoSeal legacy code/model | Exact pinned upstream terms in THIRD_PARTY.md |
| C2PA wrapper/native | MIT or Apache-2.0 according to upstream component |
| Node/ONNX runtime | Their included notices and third-party terms |
| FFmpeg, libx264 and PyAV bundled codecs | Component/build-specific terms, including GPL-bearing codecs |

Running your own service and shipping a combined binary/container to customers
are different distribution scenarios. Do not label an entire generated image
Apache-only. A prebuilt combined image remains outside this release until its
corresponding-source and native-dependency distribution review is complete.
The exact [runtime inventory](../validation/results/0.7.2a1-artifacts.json) and
THIRD_PARTY.md are the starting point for that review.
