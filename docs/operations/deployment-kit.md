# SDK + verifier + registry kit

The kit connects existing qualified SDK components. It adds an operator-owned
deployment and batch integration, not a new watermark algorithm or a compliance
certificate. The supported initial workflow is your own image/video generation,
final rendition preparation, marking/signing, and publication of the returned
file. Synthetic audio and marking-only relay of upstream C2PA inputs remain
outside this workflow.

## Build and initialize

Use the source archive and wheel from the same release manifest. The source
archive includes Dockerfile, dependency locks, kit assets and test scripts.

```sh
tar -xzf ariadne_mark-0.7.2a0.tar.gz
cd ariadne_mark-0.7.2a0
docker build --platform linux/amd64 -t ariadne-mark:0.7.2a0 .
mkdir -p deployments
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD/deployments:/data" ariadne-mark:0.7.2a0 \
  kit init /data/demo --development --publisher 'Your Public Studio' \
  --system 'Your Generator' --system-version '1.0'
```

Init refuses an existing target directory. A failed initialization is marked
`INIT_INCOMPLETE`; inspect it instead of deploying. It never overwrites keys.
The development option creates test issuer/report/TLS identities. Local TLS
is self-signed and does not establish public trust. The default verifier URL
is `https://localhost:8443` and ports bind only to localhost.

For production omit `--development`, supply `--verifier-url https://YOUR-HOST`,
then provide the credentials listed in the generated README. Production init
creates the structure/report key but no provider identity, issuer roots or
public TLS certificate. The existing strict trusted-TSA export policy is
preserved. The kit does not enroll a C2PA product or issue certificates.

## Export final renditions

Put final PNG/JPEG/MP4 inputs under deployments/demo/inputs. Copy
batch.example.json to batch.json and replace the filenames/null timestamps.
For example:

```json
{
  "schema_version": 1,
  "jobs": [
    {"source": "image.png", "destination": "image.marked.png", "created_at": "2026-11-09T10:00:00Z"},
    {"source": "video.mp4", "destination": "video.economy5.mp4", "created_at": "2026-11-09T10:00:00Z", "video_profile": "economy_5s", "audio_kind": "none"},
    {"source": "video.mp4", "destination": "video.economy2.mp4", "created_at": "2026-11-09T10:00:00Z", "video_profile": "economy_2s", "audio_kind": "none"},
    {"source": "video.mp4", "destination": "video.resilient.mp4", "created_at": "2026-11-09T10:00:00Z", "video_profile": "resilient", "audio_kind": "none"}
  ]
}
```

Use actual generation timestamps, not these example values. Paths are relative
to inputs/outputs and must remain inside them. Destinations must be new and
unique. The complete batch is preflighted before any export. One SDK reuses
workers across the batch. Each file keeps the ordinary SDK publication gate,
receipt and registry transaction. A later job failure does not undo earlier
successes; retain the JSONL log and per-file receipts when retrying.

```sh
cd deployments/demo
docker compose pull edge                 # explicit one-time provisioning
docker compose run --rm exporter
docker compose up -d
docker compose ps
curl --cacert private/tls/cert.pem https://localhost:8443/health
curl --cacert private/tls/cert.pem --data-binary @outputs/image.marked.png \
  'https://localhost:8443/verify?format=png'
```

The edge image is pinned by digest in .env. Processing does not pull images or
download models. Exporter/verifier use an internal network; only the edge also
joins a standard bridge for publishing ports. The internal network blocks external TSA
requests; the generated production-egress.yaml adds exporter egress explicitly
after the operator configures production credentials and destination policy.
Verifier egress remains disabled.

## Check, configure and independently verify

Run `ariadne kit check DIRECTORY --runtime` in the SDK image/environment. The
full kit directory is needed for this operator check. Each service mounts only
its own required paths at runtime. Check reports configuration errors separately
from the jurisdiction planner's unresolved declarations. No DNS/reachability,
CA enrollment, conformance or legal assessment is inferred from local readiness.

Edit config/product.json to describe actual scope, dates, disclosure and reviews.
Edit config/public-sources.json using public organization/system information
only. Its values must match the product configuration. Do not put user IDs,
prompts or contact details in provenance. After changing URLs, upload size or
timeout, run `ariadne kit render DIRECTORY`, then recreate the affected services.

The public verifier returns the reviewed fields, separate signature/issuer
trust/asset-binding states and a signed JWS receipt. Independently pin
config/report.pub; downloading a key from a response does not authenticate it.
Verify a saved response with:

```sh
ariadne report verify response.json --public-key config/report.pub \
  --asset outputs/image.marked.png --verifier-id https://localhost:8443
```

Metadata-loss recovery uses the persistent registry. Recovered source metadata
does not automatically authenticate the edited copy. Full manifest publication
is off by default; it requires both init `--public-manifests` and an explicit
per-job `publish_manifest: true` after reviewing the full history. Existing
read-only C2PA-shaped endpoints are documented in [C2PA recovery](c2pa-recovery.md).
Algorithm IDs remain provisional, not automatic cross-provider discovery.

## Operator-owned state and public release scope

Back up registry, keys and configuration with appropriate permissions. Test
restore/restart, final delivery transformations, privacy/retention and feedback.
The verifier cannot mount the provider key or write the registry. Only edge
ports are published. nginx request access logging is off; the default kit does
not retain user uploads. The TLS edge is a reference configuration, not a
maintained Ariadne hosting service.

Publish only the SDK wheel/source, public guides, notices and sanitized release
evidence. Never publish generated deployments, keys, media, registry contents,
internal review prompts or server access instructions. The SDK's Apache-2.0
AS-IS terms remain unchanged; they do not establish a provider's legal compliance.

See [supported formats](support.md), [legal mapping](../compliance/launch-mapping.md)
and [qualification protocol](../validation/0.7.2a0.md). All presets and known
crop/temporal/remover limits remain unchanged.
