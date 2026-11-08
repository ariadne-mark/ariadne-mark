# Run the verifier

The same wheel supports image/video export, local verification and a self-hosted UI/API. There is no account, API key, payment gate or remote URL fetch requirement. Use an already provisioned media environment or build the Docker recipe. [Runtime setup](../implementation/video-profiles.md) · [Deployment limits](verifier.md).

Before starting a manually provisioned verifier, run `ariadne runtime check`.
The supplied service also checks the pinned wrapper, actual loaded native C2PA
version and SHA-256 before binding its HTTP socket. A runtime mismatch prevents
startup; it is not a verdict about an uploaded file. See
[C2PA runtime diagnostics](c2pa-runtime.md).

## Local integration preview

```sh
# From the source checkout; this builds the complete CPU bundle.
docker compose up --build
# Open http://127.0.0.1:8080
```

The default Compose service binds only to localhost. It mounts a reviewed-source example read-only and a writable volume for anonymous feedback counters. Replace the example organization/model names with your reviewed public values before real use. It does not contain a signing identity or a production registry.

For an installed wheel in a provisioned environment:

```sh
ariadne models check
ariadne serve --host 127.0.0.1 --port 8080 \
  --public-sources examples/public-sources.json \
  --feedback-db .ariadne/verifier-state/feedback.sqlite
```

The UI uploads JPEG, PNG and supported MP4 to this server; it removes temporary uploads before responding. It offers a compact human-readable result and a downloadable public JSON report.
Configure a separate report key to make that download an independently verifiable
Ed25519/JWS receipt: [signed reports](signed-reports.md).

## Verification API

```sh
curl --fail-with-body --max-time 330 \
  -H 'Content-Type: application/octet-stream' \
  --data-binary @output.mp4 \
  'http://127.0.0.1:8080/verify?format=mp4'
```

The response is HTTP200 for a completed inspection request, not necessarily a recovered mark. Read `c2pa.status`, `watermark.status`, `watermark.search` and `public_output`. Request errors use408/413/415/422/429/504; incomplete inspection is not an absence result. [OpenAPI](../../src/ariadne_mark/verifier_assets/openapi.json) is also served at `/openapi.json`.

| Result | Meaning |
|---|---|
| `verified_claim` | C2PA signature and file binding validated; issuer trust is a separate field |
| `recovered_claim` | Compatible watermark ID recovered; not cryptographic authentication of an edited copy |
| `single_observation` | One individual ID read without sufficient confirmation |
| `not_found` | No supported ID recovered within the completed inspection scope |
| `not_checked` | Missing engine, budget or another operational/incomplete check |
| `invalid` | Invalid credential or conflicting recovered evidence |

The CLI service runs verification in a persistent verification-only child with a 180-second whole-job deadline (configurable with `--verification-timeout`), including model startup. On timeout or crash it terminates the qualified POSIX process group, including Node, and starts a fresh worker for the next request. Cleanup has a separate bounded wait. HTTP 504 is `not_checked`; uploaded files are removed and the inference slot is released. The parent never passes a signing identity. Create each service after any application fork; inherited service instances are rejected. The low-level `make_server(custom_sdk)` testing/embedding interface uses the supplied object directly; wrap it in `IsolatedVerifier` for this process boundary.

The default video detector uses one CNN pass, cached logits and explicit search budgets. It can stop early after two matching individual reads. No result establishes whole-video coverage, human origin or factual truth. Legacy scheme absence cannot be certified if its engine is missing.

## Public provenance fields

`--public-sources` is a reviewed list of public provider/system/version strings. C2PA free-text fields are returned only for a matching profile **and** a trusted valid issuer. Registry records are operator-managed evidence; they use the same reviewed-name policy but are not treated as authenticated source evidence for arbitrary edited copies. Unknown text, arbitrary metadata and local debug evidence are not reflected in the public response. Optional signed flags/profile strings are type/enum-limited.

This is a whitelist, not an automatic PII classifier. The operator must keep personal data out of approved names and registry records and use random asset IDs. Full local `ariadne verify FILE` inspection is separate from the minimized public API.

## Persistent resolver and feedback

For metadata-loss recovery, export with a registry and mount its directory read-only in the verifier. The writing exporter and read-only reader must see the same durable database. Add `--registry /registry/registry.sqlite3`. A supported ID can be looked up through `GET /records/{token}`; an unknown ID returns 404 and a registry failure 503. This is an operator resolver, not cross-provider discovery or proof that an edited copy belongs to that entry.

Anonymous feedback is available in the result UI, at `GET /feedback`, and through:

```sh
curl --fail-with-body -H 'Content-Type: application/json' \
  --data '{"rating":"unable_to_check","media":"video"}' \
  http://127.0.0.1:8080/feedback
ariadne feedback-summary .ariadne/verifier-state/feedback.sqlite
```

Only `rating` (`correct_result`, `incorrect_result`, `unable_to_check`) and `media` (`image`, `video`, `unknown`) are accepted. The store contains nine aggregate counters, not free text, media, watermark IDs, contact details, IPs, timestamps or individual feedback history. Extra fields fail 400. The operator should review counter changes, investigate reproducible failures through a separate consent-aware process, and incorporate useful feedback into improvements.

## Before public operation

Use the [TLS-edge configuration](../../apps/verifier/nginx.conf), scoped public trust roots and `--production` when applicable; that flag rejects development roots. Provide truthful operator/privacy information for your deployment, persistent registry/backups where required and reviewed-source configuration. Configure a reachable feedback route and a product UI link. Validate the exact UI/API using your final exported media and its delivery transforms. Review proxy/host logging separately from application defaults. [Legal map](../compliance/launch-mapping.md).

Public hosting, operator identity, production certificate enrollment, trust/TSA arrangements and evidence of durability are deployment responsibilities. An offline passing test suite or private preview is not a completed public service.

For optional C2PA manifest storage, explicit publication and standard read-only
lookup endpoints, see [C2PA recovery](c2pa-recovery.md). Provisional algorithm IDs
are not yet enrolled for cross-provider discovery.
