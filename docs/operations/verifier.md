# Operate the verifier and recovery registry

The current kit provides a minimized public UI/API, isolated inference, signed
reports and a read-only registry. It has no provider content-signing key. Its
HTTP parent uses a separate Ed25519 report key, never passed to the media child;
the TLS edge has its own key. Use the [complete kit](deployment-kit.md) for the
reference deployment or [quickstart](verifier-quickstart.md) for standalone setup.

## Standalone production configuration

After supplying actual files and a real public origin, the command shape is:

```sh
ariadne serve --host 127.0.0.1 --port 8080 --production   --trust-anchors issuer-roots.pem --registry state/assets.sqlite3   --public-sources reviewed-public-sources.json   --report-key private/verifier-report/report.key   --verifier-id https://YOUR-REAL-VERIFIER-HOST   --feedback-db state/feedback.sqlite
```

Replace the uppercase hostname and files with your actual configuration. For a
private TSA, add `--tsa-trust-anchors tsa-roots.pem` separately; manifest roots
do not become TSA roots. Built-in native TSA trust remains in use. Production
startup requires appropriate non-development roots and a report signer. A local
root does not establish public C2PA trust-list enrollment or truth of claims.
Place a buffering/rate-limiting TLS proxy in front; defaults bind to localhost.

## Evidence and privacy

`POST /verify?format=png|jpg|jpeg|mp4` accepts a raw binary upload. Local output
is minimized using reviewed public provider/system/version fields. The public
source allowlist is not a PII classifier. Invalid, incomplete, recovered and
trusted/untrusted evidence remain separate. Do not turn missing evidence into
a human-origin or authenticity verdict. See [result reference](../reference/api-cli.md).

Use [signed report verification](signed-reports.md) with a separately pinned
public key and submitted asset. Signed negatives/incomplete results remain
negative/incomplete. Full manifest publication is off by default and needs
explicit per-record review/opt-in; see [recovery API](c2pa-recovery.md).

Uploads are temporary and removed on success/failure. Anonymous feedback stores
fixed aggregate counters. Operator proxy/host logging, retention, disclosure
and useful feedback review remain separate responsibilities. The service is
single-operator, not a multi-tenant storage isolation product.

## Limits and persistence

Standalone application/export ceiling: 512 MiB. Generated kit TLS edge default:
128 MiB; configure a larger or narrower product scope consistently and render
updated config. The verifier has four upload slots, one inference slot and no
queue. Busy requests can return 429; unsupported content and exhausted scans
are not successful negatives. Do not promise throughput from a single positive
scan. Configure and validate capacity for the actual deployment.

Mount the registry directory read-only in the verifier and writable only to the
exporter. The reference writer uses rollback journaling; never use `immutable=1`
on a live database. A separate WAL configuration requires sidecars or a managed
reader snapshot. Persistent state, backup/restore, crash reconciliation and
service availability need operator evidence. The kit tests restart persistence,
not universal power-loss recovery or production backups.

Follow [production onboarding](production-onboarding.md) and retain the
[operator record](../compliance/operator-evidence-template.md). Public TLS/DNS,
accessibility, long-running load and real CA/TSA arrangements were not supplied
by the development-credential qualification.
