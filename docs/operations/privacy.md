# Data handling

The SDK processes local files. No account, analytics, telemetry, hosted signing
or remote watermark service is used. Model downloads occur only during explicit
setup. C2PA remote fetching is disabled by default.

The verifier uses a random temporary directory per request and deletes uploads
on success and failure before returning a response. It does not log client IPs,
original filenames or upload contents. Tests exercise cleanup on both paths.
The reference service is single-operator, not a multi-tenant storage service.
Its optional registry stores public provenance records and technical receipts;
it does not retain uploaded media. Registry retention and backups are operated
separately from transient uploads.

Public records have no end-user ID, email or arbitrary metadata extension field.
The SDK does not classify whether publisher/model text contains personal data.
Use only public organization/model information. Do not put user names, prompts,
account IDs or personal data in those fields. A public verifier is not a PII
redaction product; deployment privacy review remains necessary.

External reverse proxies, hosts, monitoring tools and feedback services can
introduce their own logs and retention. Configure them consistently with your
privacy notice and applicable obligations. A feedback contact is optional for
local development but must be made operational when required by a deployment.
