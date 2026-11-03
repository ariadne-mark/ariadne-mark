"""Run locally after installation. This prepares data; it does not mark media."""

from datetime import datetime, timezone

from ariadne_mark.provenance import Action, GenerativeSystem, MediaKind, ProvenanceRecord


record = ProvenanceRecord.create(
    publisher="Example Studio",
    system=GenerativeSystem(name="Example Generator", version="2026.11"),
    media_kind=MediaKind.VIDEO,
    action=Action.CREATED,
    # Supply the asset's actual generation/editing time, not the installation time.
    created_at=datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc),
)
serialized = record.to_json()
assert ProvenanceRecord.from_json(serialized) == record
print(serialized)
