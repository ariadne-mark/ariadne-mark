# Third-party components — 0.2.0a0

The wheel contains Ariadne Mark's code and a model checksum manifest, not model
weights or third-party source copies. Pip/Docker installation obtains upstream
packages. The Docker build downloads TrustMark weights explicitly and verifies
their SHA-256 hashes; runtime processing can be offline.

| Component | Tested pin | Origin | License / notes |
| --- | --- | --- | --- |
| TrustMark | 0.9.2, Q/BCH-5 | https://github.com/adobe/trustmark | MIT; upstream README states it covers code and downloaded models |
| C2PA Python | 0.38.1 | https://github.com/contentauth/c2pa-python | MIT OR Apache-2.0; bundles native C2PA |
| PyTorch CPU | 2.14.1+cpu | https://pytorch.org/ | BSD-style; use the official CPU wheel index |
| torchvision CPU | 0.29.1+cpu | https://github.com/pytorch/vision | BSD-3-Clause |
| Pillow | 13.0.0 | https://python-pillow.org/ | MIT-CMU |
| PyAV | 16.0.1 | https://github.com/PyAV-Org/PyAV | BSD-3-Clause; bundled FFmpeg libraries have separate terms |
| cryptography | 50.0.2 | https://github.com/pyca/cryptography | Apache-2.0 OR BSD-3-Clause |
| FFmpeg / libx264 | Debian package in Python 3.12 slim-trixie | https://ffmpeg.org/ | LGPL/GPL components depending on build; libx264 is GPL. Do not describe a combined container as Apache-only |

Model hashes live in [models.json](src/ariadne_mark/watermark/models.json).
Downloads come from the location embedded in the pinned official TrustMark
package. No custom models, model-removal weights or detection network are
bundled. Preserve upstream notices when redistributing packages or images, and
review the license obligations of the exact transitive/binary build. The
project license does not relicense dependencies, standards or legislative text.

Reference designs and audits informed the architecture; this implementation
wraps the upstream libraries directly and does not copy a competitor's server
or reuse a cloud credential. Runtime dependency inventory is captured with the
release validation artifacts.
