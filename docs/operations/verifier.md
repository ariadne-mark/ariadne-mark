# Deploying the verifier

The standalone Compose service binds to localhost. It has no signing key and
runs without root, capabilities or a writable root filesystem. Use a public
TLS edge before exposing it. [Reference nginx config](../../apps/verifier/nginx.conf)
provides request buffering and per-client connection/rate limits; it is not a
TLS certificate/deployment manager.

```sh
ariadne serve --host 127.0.0.1 --port 8080 --production \
  --trust-anchors provider-and-optional-tsa-roots.pem \
  --registry .ariadne/registry.sqlite3 \
  --feedback-url https://github.com/ariadne-mark/ariadne-mark/issues
```

`--production` requires configured roots. Operator roots are added to the
built-in C2PA trust store, preserving its TSA roots. A trusted certificate chain
does not independently verify the truth of a publisher's free-text claim.
Untrusted signed data is labelled **Signature valid; issuer unverified**.
Use `ariadne verify FILE --strict` to fail unless the credential and issuer
trust validate. Test-root trust is not public C2PA trust-list enrollment.

The CLI opens a verification registry with SQLite `mode=ro`, with no schema
creation or writes. Mount its **directory read-only**; signing workers retain
write access. The reference writer uses rollback journaling. Do not use SQLite
`immutable=1` for a live database. A separately managed WAL database needs
readable WAL/SHM sidecars or a reader snapshot/replica. The verifier never needs
signing keys or unrelated host directories.

API: raw binary `POST /verify?format=png` (also jpg/jpeg/mp4), no account,
multipart or remote URL fetch required. Default maximum is **512 MiB**, matching
the signed export ceiling. Deployments choosing a smaller maximum must narrow
their accepted/exported content scope accordingly. Allocate a temporary spool
for up to four uploads; the Compose reference uses a 2 GiB tmpfs.

Uploads have four bounded slots and a 120-second total body deadline. They do
not acquire the single inference slot until the complete body is spooled. There
are at most 16 request handlers. A slow uploader therefore cannot hold the
model slot. Busy slots/inference return 429; upload timeouts 408; oversize 413;
unsupported extension 415; an operational verification failure 422/not_checked.
This is bounded resource handling, not an availability SLA against many clients.

Temporary files are deleted on success, failure and timeout. Access logging is
disabled by default. Review edge-server logs, retention, data isolation and the
privacy notice for your actual deployment. Verification reports do not establish
human origin, factual truth, or authenticated source attribution from an ID alone.

## Header deadline and development roots (0.5.3)

A total 10-second deadline covers request line and headers, independent of the
body upload deadline. Byte-by-byte sends cannot reset it indefinitely. This
only bounds resource occupation; public deployments still require the supplied
edge-proxy controls. Development roots and invalid/non-CA roots are rejected
in production. Development assertions always receive a development headline.
CORS is not enabled by default; cross-origin browser clients need a controlled
proxy or their own explicitly reviewed CORS layer.
