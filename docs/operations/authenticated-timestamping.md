# Configure an authenticated timestamp authority

SDK **0.7.3a4 candidate** · updated **2026-11-14**.

The pinned C2PA pair remains c2pa-python 0.38.3 / native 0.91.11. Its signer
accepts a TSA URL but cannot attach an authorization header. Ariadne can now
use an optional, short-lived loopback relay to add a bearer credential and
forward the unchanged RFC 3161 request over verified HTTPS. Timestamp tokens
are still checked by native C2PA; the relay does not issue or approve them.

This topology follows the approach described in the official
[SSL.com provenance SDK](https://github.com/SSLcom/SSL-Provenance-SDK), whose
timestamp adapter uses bearer authorization with the same Python SDK family.
The service remains configurable; no SSL.com account or credential is included.

## Kit configuration

Obtain your actual token through the TSA operator. Save it in an owner-only
regular file `private/tsa/bearer.token` inside the kit, with permissions `0600`.
Do not put it in JSON, a URL, source control or command-line arguments. The file
contains the token alone, optionally followed by one newline, without `Bearer`.

Set these non-secret fields in `config/kit.json`:

```json
{
  "timestamp_url": "https://ts-c2pa.ssl.com/ecc",
  "timestamp_credential_file": "private/tsa/bearer.token",
  "timestamp_timeout": 10
}
```

These fields extend the existing configuration; do not replace the whole file.
The endpoint and token permissions must be confirmed with the service before
production use. `kit check DIRECTORY --runtime` checks local settings and file
format; it makes no live TSA request. The exporter mounts `private/tsa` read-only.
The verifier and TLS edge receive no TSA credential mount.

The default Compose network blocks exporter Internet access. Use the generated
production-egress override and your operator's destination restrictions when
enabling an external TSA. The local relay does not create an egress exemption.

Without `timestamp_credential_file`, the original direct-URL route is preserved.
Old kits without these fields still load. `timestamp_timeout` controls the
authenticated relay only; it does not change native's direct-request timeout.

## Python and CLI

`SigningIdentity` and `SigningIdentity.from_directory` accept
`timestamp_credential_file`, `timestamp_timeout` and `timestamp_ca_bundle`.
The optional CA bundle is for the upstream HTTPS server certificate; it is
different from `tsa_trust_anchors`, which validates the timestamp token signer.
The kit uses system HTTPS roots; a private HTTPS CA bundle is currently a
Python/CLI option, not a kit JSON field.

The `mark` command offers `--timestamp-url`, `--timestamp-credential-file`,
`--timestamp-timeout` and `--timestamp-ca-bundle`. Keep the token in its file;
the CLI argument is the path. Authenticated timeouts must be greater than zero
and at most 25 seconds, allowing time for native's 30-second request boundary.
Kit timeouts are whole seconds. Development fixtures may use HTTP loopback;
production upstream endpoints always require HTTPS.

## Failure and trust boundaries

- The relay binds only to `127.0.0.1` on an ephemeral port with an unpredictable
  request path, and is shut down after the signing operation. This is not
  isolation from other processes on the same host. An unprivileged local
  process can connect to the port; a random path is not host isolation.
- At most four local clients have handler threads. Excess connections are
  closed immediately. A two-second absolute deadline covers the request line,
  headers and complete body together, regardless of byte-by-byte activity.
  Valid complete requests then use the configured upstream deadline. Shutdown
  closes active local connections and interrupts established upstream sockets.
  This bounds one slow client; it does not promise availability under sustained
  hostile local connection flooding. Isolate the exporter process/host as needed.
- Requests are bounded to 64 KiB and replies to 1 MiB. Redirects, automatic
  retries and environment proxy routing are disabled. Upstream TLS is verified.
- The deadline interrupts slow response headers/bodies after connection;
  operating-system DNS resolution can have its own latency. Native also has a
  separate request timeout. This is not a service-level latency guarantee.
- Authentication failures, invalid tokens, TLS failures and timeouts fail the
  export. A file created by a failed low-level signing call is removed; SDK
  publication does not write output, a success receipt or a registry row.
- Public error messages, relay status records and object representations never
  include the token. Expected local disconnects do not print tracebacks.
  Protect host diagnostics and the private file separately.
- Credential files must be regular, not symlinks/FIFOs, and have no group/world
  permission bits. The SDK does not require the file UID to equal the process
  UID: root-owned/container-mounted secrets may legitimately differ. The host
  deployment must enforce who can read or replace the secret.
- A valid HTTPS connection does not establish timestamp-signer trust. Supply
  and independently verify the appropriate `config/tsa-roots.pem` and issuer
  roots. Keep provider, report, TSA-credential and TLS credentials separate.

Offline test PKI exercises successful authorization, rejected credentials,
mismatched RFC 3161 message imprints, timeout, untrusted HTTPS and untrusted
timestamp roots. These tests do not qualify the live SSL.com service. Actual
production enrollment, credentials, quotas and an externally verified export
remain operator actions. The selected service's published endpoint and access
conditions are described in [SSL.com's TSA documentation](https://www.ssl.com/products/content-authenticity/timestamping/).

See [production onboarding](production-onboarding.md) and
[the deployment kit](deployment-kit.md).
