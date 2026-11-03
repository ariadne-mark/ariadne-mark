# Full SDK stock-video regression

Run after provisioning both models:

```sh
python benchmarks/video/run.py /path/to/corpus /path/to/new-output-directory
```

[Source inventory and preparation commands](corpus.json) identify the three stock clips used for release validation. Download them under the stated source licenses and normalize locally; the repository does not redistribute those files.

The corpus contains `manifest.json` with `items`: each video item has `name`, `kind: "video"`, a relative `input` path and the file SHA-256 in `sha256`. The benchmark checks hashes and makes no downloads. Keep source URLs and license information in the corpus manifest.

It runs three reproducible IDs per clip, full export/sign/read-back, independent verification, negative originals, and four transformations on the first export: CRF 28, CRF 35, half-size/CRF 28, 10% center crop/CRF 28. Model loading is reported separately. Warm-up effects are not removed from the first measured export. `peak_python_rss_mib` is Linux Python RSS, not total container/FFmpeg peak memory. Metadata-free verification checks both supported engines and is slower than signed VideoSeal dispatch.

Only publish `report.json` and separately reviewed media. The output directory contains a development signing private key. Test claims do not mean the stock originals are AI-generated. This small corpus does not qualify legal compliance or a general false-positive rate.
