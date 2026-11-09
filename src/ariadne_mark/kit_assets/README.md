# Ariadne deployment kit

This directory is an operator-owned deployment, not a public release asset.
Keep `private/`, input/output media, registry and feedback state out of Git.
All three video profiles are retained; Economy5s is the default. The kit does
not determine legal sufficiency or provide a production issuer identity.

## Export and run

Build the versioned SDK image from the accompanying source archive. The kit
uses that local image (`pull_policy: never`). Provision the pinned edge image
explicitly before an offline deployment:

```sh
docker compose pull edge
cp batch.example.json batch.json
# Put final renditions under inputs/. Edit batch.json: supply real filenames
# and actual generation times with timezone. Null timestamps are refused.
docker compose run --rm exporter
docker compose up -d
docker compose ps
```

No exporter HTTP API is exposed. One batch reuses its SDK/workers across jobs.
For a long-lived product worker, reuse the Python SDK directly. A failed batch
does not roll back earlier successful files: per-file receipts/registry entries
identify committed exports. New destinations are required for retries.

HTTP and HTTPS bind to localhost by default (8800 / 8443). Development TLS is
self-signed for localhost/kit.test, not public trust. Pin `private/tls/cert.pem`
with `curl --cacert`; do not disable TLS validation. A different HTTPS port
also requires updating both verifier_url fields in config/kit.json and
config/product.json. Run `ariadne kit render DIRECTORY` after configuration
changes to regenerate the edge body limit and production HTTP redirect.

## Files and isolation

- exporter: provider signing key read-only; registry/outputs writable;
- verifier: registry read-only, separate report signing key, feedback writable;
- edge: TLS key only, no provider/report keys, no request access logging;
- config/public-sources.json: reviewed public organization/model fields only;
- config/product.json: explicit scope and operator review declarations;
- outputs/: signed media plus SDK receipts, not served as a public directory;
- config/report.pub: independently pin this key before trusting a signed report.

Exporter and verifier use only an internal network. The edge also joins a
standard bridge for host port publishing; only the edge publishes ports.
Signing with an external production TSA needs operator-configured outbound
access for the exporter only; the default offline network intentionally blocks
it. Never give the verifier the provider key or unrestricted egress.

## Production preparation

Production init does not create fake signing/TLS credentials. Supply:

- private/provider/certificate.pem, private.key, identity.json with
  `{"development": false}`; private key mode 0600;
- config/issuer-roots.pem and config/tsa-roots.pem, public CA certificates;
- kit.json timestamp_url (qualified SDK production signing currently requires
  a trusted timestamp; this implementation policy is not a universal law);
- private/tls/cert.pem and key.pem for your HTTPS hostname;
- the same actual public verifier URL in kit.json and product.json.

Keep the generated separate report key. Review public-sources, provenance
history before enabling full manifest publication, product scope, feedback,
retention, backups and the actual upload/download delivery transformations.
Run `ariadne kit check DIRECTORY --runtime` inside the SDK environment.
`local_configuration_checked` is not certificate enrollment, public endpoint
reachability, C2PA conformance or a compliance determination.

Expose the edge only after configuring real TLS/DNS and reviewing the deployment.
For production signing, explicitly use
`docker compose -f compose.yaml -f production-egress.yaml run --rm exporter`.
This adds exporter egress, leaving the verifier internal. Enforce the intended
TSA destination at the host egress proxy/firewall. The SDK does not configure
cloud firewalls, certificate issuance or DNS.

Software is Apache-2.0, including its AS-IS terms. Third-party components retain
their licenses. The nginx image is an independently fetched deployment tool,
not a binary redistributed inside the SDK wheel/source.
