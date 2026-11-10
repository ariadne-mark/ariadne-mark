# Stock export product emulator

A running product, rather than an SDK unit test: stock selection → persistent
queue → real SDK export → download → verification through a separate service.
It replaces only the generative model with nine existing stock fixtures.
Watermarking, C2PA signing, read-back, receipts and registry recovery are real.

The UI and signed publisher/system fields identify engineering fixtures.
The stock originals are not represented as genuinely AI-generated content.
This private lab uses a development signing identity and an intentionally
incomplete hypothetical product profile; it makes no legal-compliance claim.

## Services

- **web**: stock catalog, export API, persistent job status, downloads and
  verification proxy. Host loopback port 8020.
- **worker**: one queue consumer, reuses SDK/model instances, applies the profile
  and optional visible disclosure, publishes only complete exports.
- **verifier**: independent SDK HTTP process, upload UI/API and the same persistent
  recovery registry. Host loopback port 8021. It cannot read the signing key.

State lives outside containers: jobs SQLite, registry SQLite, staging/results
and the development identity. A request key deduplicates identical requests;
reuse with different settings returns 409. A worker restart requeues interrupted
jobs and checks any completed staged output before committing it. Failed and
partial results are not available through the download API.

This is a single-host, single-worker POSIX/SQLite integration. It does not
implement S3, distributed queue leases, power-loss durability, authentication,
billing, arbitrary uploads or a production load SLA. Do not expose the private
lab to the public internet. Containers communicate on an internal Docker network.

## Run

Build the SDK image from the repository root, then provision the fixtures listed
in `catalog.json` under an input directory. The catalog includes source pages,
authors, license links and exact hashes for the normalized fixtures used by the
lab. Stock media and private signing keys are not included in this repository.
Existing benchmark fixtures are 1280px PNGs and five-second 720p silent MP4s.
Create `invalid.png` containing exactly `not an image` for the failure test.

```sh
docker build -t ariadne-mark:local .
cd examples/stock_product
export PRODUCT_DATA=/absolute/path/to/product-data
export PRODUCT_INPUTS=/absolute/path/to/stock-inputs
export SDK_IMAGE=ariadne-mark:local
mkdir -p "$PRODUCT_DATA/registry"
# The SDK container uses UID 10001; grant that user ownership of PRODUCT_DATA.
sudo chown -R 10001:10001 "$PRODUCT_DATA"
docker run --rm --network none -v "$PRODUCT_DATA:/data" \
  "$SDK_IMAGE" init-dev /data/identity
docker compose -p ariadne-stock up -d --build
```

Open `http://localhost:8020`; standalone verification is at port 8021. For a
remote host, forward both loopback ports with SSH. Keep `.env`, identity,
SQLite and media data outside version control.

## Exercise the product

```sh
python3 acceptance.py --compose-dir "$PWD" --report /tmp/stock-product-report.json
```

The acceptance script uses HTTP to enqueue six images and three videos,
verify every export, check downloads and profile receipts, reject conflicting
request keys and corrupt input, exercise visible disclosure, kill the worker
during video processing, then restart the web/verifier services. It is intended
for the isolated lab: it deliberately interrupts its worker and services.

`results/server-acceptance.json` records the actual run. Timings are observations
on this small fixture set, not performance or durability guarantees.

Stop the product with `docker compose -p ariadne-stock down`. Persistent data
remains available for the next start. Stop the EC2 instance separately when it
is no longer needed.

## 0.5.1 profile and audit follow-up

Jobs accept `video_profile: "economy_5s" | "economy_2s" | "resilient"` (default Economy 5s). Explicit legacy `fast` jobs remain supported. Historical database rows retain their original Fast setting; new requests record the new default explicitly. The request key
includes this setting in its conflict check. One persistent SDK exists per
profile. The HTTP acceptance run additionally exports all three video fixtures
with Resilient and checks its per-frame inference count.

The verifier mounts only the public root certificate and a read-only registry
directory. It uses production trust configuration but this remains a private
development-certificate lab, not public trust enrollment. Interrupted jobs have
three maximum attempts (configurable via PRODUCT_MAX_ATTEMPTS, 1–10) with bounded
backoff. A poison job fails and its partial staging is removed. A surviving
worker owns the exclusive flock before it reconciles unpublished job artifacts.
