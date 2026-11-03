# Reproducible CPU smoke benchmark

After installing the media extra and provisioning models:

```sh
python benchmarks/durability/run.py /tmp/ariadne-benchmark-new
```

The destination must not exist. The script generates four deterministic image
fixtures and two short videos, creates a development identity, runs the complete
SDK, and writes `report.json` plus original/exported/transformed media.
Development private keys stay in the output directory; do not publish that
whole directory. Share only the report and selected media/receipts.

The matrix includes JPEG quality 75/50, half-size resize, 10%/25% center crop,
negative controls, H.264 CRF 28 recompression, processing time, image PSNR and
peak process RSS. All outputs must pass original watermark and C2PA read-back.
Transformation failures are recorded, not hidden. Video checks sample frames;
no claim is made about all frames after third-party transformation.

This small synthetic dataset is smoke evidence, not a calibrated FPR/FNR or an
adversarial evaluation. It does not establish statutory durability. Extend it
with representative content and transformations from the adopting product.
See [release evidence](../../docs/validation/0.2.0a0.md).
