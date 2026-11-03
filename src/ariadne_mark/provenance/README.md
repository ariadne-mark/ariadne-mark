# Provenance core

Immutable records validate publisher, generator/version, timestamp, action and
public UUID for image/video media. `SDK.mark` embeds these records in signed
C2PA assertions. See [usage](../../../docs/implementation/provenance.md).

REQ-003 remains in progress for jurisdiction-specific mapping; the technical
record and media binding are implemented and exercised by integration tests.
