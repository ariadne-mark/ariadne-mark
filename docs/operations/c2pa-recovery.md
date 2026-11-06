# C2PA manifest recovery — 0.7 alpha

The SDK signs a `c2pa.soft-binding` assertion and a `c2pa.watermarked.bound`
action. An 8-byte big-endian Ariadne token is the binding value. Image Q/BCH5,
video Q/variax-BCH5, and legacy VideoSeal/BCH20 have distinct algorithm IDs;
video frequency presets share the same video decoder/ID format.

**Registration remains open.** `org.ariadne-mark.*` identifiers are provisional
and absent from the C2PA Soft Binding Algorithm List. The implementation uses
C2PA 2.4 assertion/API shapes, but does not claim full C2PA conformance or automatic
cross-vendor discovery. Before interoperability enrollment, confirm the owned
namespace, stable public endpoint, contact and informational URL and submit an
algorithm-list request. No enrollment or external agreement is made by the SDK.

## Local storage and recovery

When a registry is configured, final native `application/c2pa` bytes and their
SHA-256 are committed in the same SQLite transaction as the provenance record.
The SDK reads those exact bytes against the final signed asset and requires the
soft binding and active manifest ID to match before publication. An identical
retry is accepted; a changed binding/record is refused. Old databases remain
readable and gain an additive `manifests` table when opened for writing.

```sh
ariadne mark input.png output.png --registry state/assets.sqlite \
  --publisher 'Example Inc.' --system 'Example Generator' --system-version 1 \
  --created-at 2026-11-06T10:00:00Z --identity production-identity \
  --timestamp-url https://your-trusted-tsa.example
ariadne recover downloaded.png recovered.c2pa --registry state/assets.sqlite \
  --trust-anchors trusted-roots.pem
```

Recovery performs blind watermark detection first, matches the observed engine,
then validates the original manifest's signature and all its active soft-binding
assertions. It writes a separate manifest file and never edits the downloaded
asset. A recovered original manifest can have a valid signature while its hard
binding mismatches an edited asset. Those states are kept separate, including in
the signed verification report. A copied ID is not authentication of an edited
copy. A corrupt stored blob is refused, rather than served as a successful match.

## Explicit publication

By default manifests stay private in the operator's registry. The full signed
manifest can include inherited history and personal/free-text data. Review that
history before explicitly using `ariadne mark ... --publish-manifest`. A signed
manifest cannot be redacted in place without invalidating its signature.

Enable public read-only endpoints separately:

```sh
ariadne serve --registry state/assets.sqlite --public-manifests \
  --report-key .private/verifier-report/report.key \
  --verifier-id https://verify.example.org
```

- `GET /services/supportedAlgorithms` lists provisional algorithms.
- `GET /matches/byBinding?alg=...&value=...` accepts standard base64 (URL-encode it).
- `POST /matches/byBinding` accepts JSON `alg` and `value`.
- `POST /matches/byContent` accepts raw media with `image/png`, `image/jpeg` or
  `video/mp4` Content-Type; optional `alg` narrows the association match.
- `GET /manifests/{manifestId}` returns the exact full `application/c2pa` store.

Queries return `matches` with `manifestId`, not invented probability scores.
`maxResults` is bounded to 1–100 (this repository has one immutable association
per token). Only explicitly published rows are visible. Unknown IDs return an
empty match list; incomplete content detection returns an error, not a successful
absence. Active-only fetch (`returnActiveManifest=true`), reference URL fetching,
repository receipts and public store/update/delete routes are not implemented.
Writes happen through the local SDK transaction; no anonymous ingestion endpoint
is exposed. This is a documented read-only subset, not the full repository API.

Keep the SQLite database on persistent storage and back it up. Existing `/records`
is retained for compact public provenance. Registry publication and verifier key
publication do not provide universal discovery or authenticate an operator.

## Native runtime qualification

Native C2PA 0.91.7 converts JSON byte arrays into CBOR arrays for soft bindings.
0.7 pins official 0.91.11, which contains upstream fix #2689 and emits the required
CBOR byte string. Source/runtime archive and library SHA-256 are pinned in
`c2pa-bootstrap.json`. No custom binary-patching workaround is retained.
Real-media tests check the binary CBOR value, detached-manifest read-back, signature
and file binding separately, metadata loss, all three video presets and signed
HTTP receipts. Development certificates in tests are not production enrollment.

Sources: [C2PA 2.4 §18.10](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html#_soft_binding),
[C2PA Soft Binding API](https://spec.c2pa.org/specifications/specifications/2.4/softbinding/Decoupled.html),
[official algorithm list](https://github.com/c2pa-org/softbinding-algorithm-list),
[official native release](https://github.com/contentauth/c2pa-rs/releases/tag/c2pa-v0.91.11).
