# Deploying the verifier

`docker compose up --build` starts the verifier at localhost:8080. The image has
no signing keys; verification needs none. The service runs as an unprivileged
user, with a read-only filesystem, a temporary upload filesystem, two CPUs,
6 GiB memory, no Linux capabilities and a process limit.

For an existing registry, mount its **directory read-write** to the container
and add `--registry /data/registry.sqlite3`. SQLite needs a writable parent for
journals. Restrict this directory to the operator. The registry contains public
claims and technical receipts, not uploaded media. Back it up if recovery is
part of your service. Without it, C2PA and watermark detection still work, but
stripped metadata cannot be resolved to publisher details.

Example native service:

```sh
ariadne serve --host 127.0.0.1 --port 8080 \
  --registry .ariadne/registry.sqlite3 \
  --feedback-url https://github.com/ariadne-mark/ariadne-mark/issues
```

API example:

```sh
curl --data-binary @output.png -H 'Content-Type: application/octet-stream' \
  'http://localhost:8080/verify?format=png'
```

The API takes a raw body, not multipart or a remotely fetched URL. Default
maximum upload size is 32 MiB. One request is processed at a time; concurrent
verification requests return 429. Unsupported formats return 415, invalid
sizes 413 and processing failures 422 with `not_checked`. A successfully
processed file can still have an `invalid` credential in its 200 response.
Temporary uploads are deleted on success and failure. Default request logging
is disabled; filenames are not retained.

Before public internet use, put a maintained TLS reverse proxy in front of the
service, enforce connection/rate limits, review resource sizing, connect an
operational feedback channel, and publish a privacy notice. The small built-in
HTTP server is an integration reference, not a hardened public edge server.
Do not mount signing keys or unrelated host directories into the verifier.

Trust roots are an explicit operator choice: `--trust-anchors roots.pem`.
The development root only identifies your test environment and must not be
represented as public CAI/C2PA trust enrollment.
