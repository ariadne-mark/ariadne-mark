# Unsigned provenance records

Related: **REQ-003**. Record handling is implemented and tested in the Python core; product facts remain publisher assertions.

`ProvenanceRecord.create()` accepts a publisher, a `GenerativeSystem` with its
own name and version, image/video `MediaKind`, created/altered `Action`, and a
timezone-aware `created_at`. It creates a random UUIDv4 asset ID. Serialization
normalizes timestamps to UTC. The SDK version never substitutes for the
version of the generative system.

`to_json()` and `from_json()` round-trip the version 1 record schema. Parsing
rejects unknown/missing fields, duplicate JSON keys, unsupported schema
versions, empty identity fields, naive timestamps and non-UUIDv4 IDs. Data
classes are immutable. Python callers must supply the enums, not raw strings.

Run [the example](../../examples/provenance_record.py) after installing the
package. Tests: [test_records.py](../../tests/provenance/test_records.py).

## Boundaries

This is an **unsigned publisher assertion**, not a C2PA manifest or proof that a
media file contains a watermark. The record object alone has no file hash, signature or trust validation.
`SDK.mark` now embeds it in signed media with a verified content binding;
optional product profiles now check record/configuration consistency, while
legal sufficiency remains under review. The record's UUID is not an
assumption about a particular watermark engine's bit capacity; the adapter
must define the wire payload and any recovery mapping separately.

There is no user identifier field. Do not put personal data in publisher or
system strings; the SDK cannot determine whether arbitrary text is personal
data. Local operation requires no account, API key or network access.

Issuance rejects timestamps more than five minutes in the future; parsing external
claims remains possible. The allowance is engineering policy. See the
[current record/signing qualification](../validation/0.7.2a1-results.md) and
[requirements matrix](../compliance/requirements-matrix.md).
