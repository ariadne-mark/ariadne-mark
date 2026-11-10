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

## Public verifier output and feedback (0.6)

The HTTP API returns a compact, minimized report. It does not return arbitrary
manifest assertions, raw inspection/debug data, all sampled-frame observations
or unreviewed free-text metadata. Configured public provider/system/version
names are an operator-reviewed whitelist. C2PA fields also require a valid
trusted issuer to expose the full supported public record. Local registry
entries are a separate operator-managed source, not authentication of edited
copies. The whitelist does not automatically classify PII: the operator must
approve only public organizational/model values and random asset identifiers.
Unknown optional assertion strings/objects are type/enum-filtered.

Optional feedback storage contains only counters keyed by fixed rating/media
enums. It accepts no free text, identifiers, contact fields or individual event
timestamps. Extra fields are rejected. The state volume persists these counters
across restarts; the CLI summary opens it read-only. Operators should use the
aggregate observations to guide verification improvements. An external
feedback link can introduce separate data processing under its own policy.

The reference `/privacy` page describes application behavior, not the practices
of an unknown hosting operator. Supply actual operator/contact/retention
information when required by your deployment. Do not infer compliance from
running the software or setting a privacy-review flag.

The explicitly configured production timestamp request is a separate network
operation. Review the chosen TSA/request metadata and operator policy. Verifier
egress remains disabled in the kit. Application defaults do not describe unknown
proxy/host practices or establish complete data-protection compliance.
