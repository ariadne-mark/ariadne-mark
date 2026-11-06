# Third-party components — 0.6.0a0

The wheel contains Ariadne Mark's code and a model checksum manifest, not model
weights. It also contains the attributed Apache-2.0 vocabulary described below.
Pip/Docker installation obtains upstream
packages. The Docker build downloads TrustMark and VideoSeal weights explicitly and verifies
their SHA-256 hashes; runtime processing can be offline.

| Component | Tested pin | Origin | License / notes |
| --- | --- | --- | --- |
| TrustMark | 0.9.2, Q/BCH-5 | https://github.com/adobe/trustmark | MIT; upstream README states it covers code and downloaded models |
| VideoSeal | official 1.0 TorchScript y_256b_img.jit | https://github.com/facebookresearch/videoseal | MIT; model hash and official Meta download URL in src/ariadne_mark/videoseal/__init__.py |
| C2PA Python | 0.38.3 / native 0.91.7 | https://github.com/contentauth/c2pa-python | MIT OR Apache-2.0; bundles native C2PA |
| PyTorch CPU | 2.14.1+cpu | https://pytorch.org/ | BSD-style; use the official CPU wheel index |
| torchvision CPU | 0.29.1+cpu | https://github.com/pytorch/vision | BSD-3-Clause |
| Pillow | 13.0.0 | https://python-pillow.org/ | MIT-CMU |
| PyAV | 16.0.1 | https://github.com/PyAV-Org/PyAV | BSD-3-Clause; bundled FFmpeg libraries have separate terms |
| cryptography | 50.0.2 | https://github.com/pyca/cryptography | Apache-2.0 OR BSD-3-Clause |
| FFmpeg / libx264 | Debian package in Python 3.12 slim-trixie | https://ffmpeg.org/ | LGPL/GPL components depending on build; libx264 is GPL. Do not describe a combined container as Apache-only |

TrustMark model hashes live in [models.json](src/ariadne_mark/watermark/models.json).
Downloads come from the location embedded in the pinned official TrustMark
package. VideoSeal is provisioned from Meta; the wheel does not include its weights.
The BCH codec is reused from the pinned TrustMark package; no bchlib dependency
or copied competitor implementation is introduced. Preserve upstream notices when redistributing packages or images, and
review the license obligations of the exact transitive/binary build. The
project license does not relicense dependencies, standards or legislative text.

Reference designs and audits informed the architecture; this implementation
wraps the upstream libraries directly and does not copy a competitor's server
or reuse a cloud credential. Runtime dependency inventory is captured with the
release validation artifacts.

## Economy/Resilient and legacy Fast video runtime

- `@variax-ai/video-watermark` 0.3.2: MIT, copyright 2026 Variax. Upstream commit 2fa85425546e. The original license is packaged in `ariadne_mark/videoq/VARIAX-LICENSE.txt`. A one-line aliasing fix copies the cached scene signature; upstream/patched SHA-256 are pinned.
- `onnxruntime-node` 1.23.2: MIT; CPU installation, CUDA download disabled. npm integrity lockfile packaged in the wheel.
- Official Adobe TrustMark Q ONNX models: same MIT upstream as TrustMark; hashes pinned in the adapter.
- Node.js and npm retain their own licenses and are external dependencies; the Docker recipe copies Node from a pinned official image and uses npm only in its build stage. No Node executable or model weights are embedded in the Python wheel.

## Distribution boundary

The Ariadne wheel/source contain original adapters, upstream attribution,
lockfiles and hash manifests. They do not bundle FFmpeg, PyAV, Torch, Node or
model weights. The C2PA bootstrap obtains unmodified official upstream sources
and native release bytes; origin and SHA-256 are recorded in the locally built
wheel. C2PA Python 0.38.3 is not currently available from PyPI.

The Docker recipe is provided as source. A combined prebuilt Docker binary is
a separate distribution: the tested Debian FFmpeg reports GPLv2-or-later and
PyAV's bundled codec libraries have their own terms. Before distributing such
an image, supply applicable notices and corresponding source/build information
for its exact GPL components. No combined Docker binary is included in the
first public alpha assets. MIT upstream licenses for TrustMark/VideoSeal cover
code and the official downloaded models; verify alternative weights separately.

`adm-zip` is overridden to 0.6.1. Provisioning records the packaged lockfile
SHA and rejects an older vulnerable runtime cache. Model/runtime requests never
perform automatic dependency installation. See the release security evidence
for scanner coverage and remaining native advisories.

## PyAV and redistributed environments

PyAV wheels carry separate FFmpeg/codec binaries, including GPL-bearing x264
and x265 builds; the SDK's encoder uses PyAV's libx264 in-process. Inventory
those binaries independently of Debian's CLI FFmpeg. Applicable obligations
apply to redistribution of a bundled venv as well as a container. Ariadne's
wheel does not contain those binaries; it includes this third-party notice.
The exact bootstrap/media package graph is hash-locked for Linux x86-64 and
Python 3.12. Apt package repositories remain an external mutable build input;
these locks are not a claim that the entire OS image is bit-reproducible.

## Trufo public C2PA vocabulary (Apache-2.0)

`src/ariadne_mark/c2pa_types/source_types.py` derives from
`trufo-ai/trufo-py/src/trufo/c2pa/source_types.py`, commit
`24dd6478e2b5ce753e34abb2c557707c12dd8d40`.
Copyright 2025-2026 Trufo, Inc. All rights reserved. SPDX: Apache-2.0.
Its copyright/SPDX headers and a modification notice remain in the file;
`LICENSE` contains the applicable Apache-2.0 text. The upstream repository has
no root NOTICE at this revision; `trufo-local/NOTICE` describes a separate
container that we do not copy or distribute.

The enum is used by signing and passive C2PA declaration inspection. No Trufo
API client, service credentials, proprietary provenance/PawPrint engine,
model weights or container are included. This reuse introduces no dependency
on Trufo's API or commercial Library License and grants no Trufo trademark.
