"""Unsigned provenance records for images and video (partial REQ-003).

These records are publisher-supplied assertions, not C2PA manifests, media
bindings, or proof of compliance. No network access or account is required.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from uuid import UUID, uuid4


class MediaKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class Action(str, Enum):
    CREATED = "created"
    ALTERED = "altered"


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{field} must be at most 512 characters without controls")


@dataclass(frozen=True)
class GenerativeSystem:
    name: str
    version: str

    def __post_init__(self) -> None:
        _text(self.name, "system.name")
        _text(self.version, "system.version")


@dataclass(frozen=True)
class ProvenanceRecord:
    publisher: str
    system: GenerativeSystem
    media_kind: MediaKind
    action: Action
    created_at: datetime
    asset_id: UUID

    def __post_init__(self) -> None:
        _text(self.publisher, "publisher")
        if not isinstance(self.system, GenerativeSystem):
            raise ValueError("system must be a GenerativeSystem")
        if not isinstance(self.media_kind, MediaKind):
            raise ValueError("media_kind must be a MediaKind")
        if not isinstance(self.action, Action):
            raise ValueError("action must be an Action")
        if not isinstance(self.created_at, datetime) or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be a timezone-aware datetime")
        if not isinstance(self.asset_id, UUID) or self.asset_id.version != 4:
            raise ValueError("asset_id must be a UUIDv4, not a user identifier")

    @classmethod
    def create(
        cls, *, publisher: str, system: GenerativeSystem, media_kind: MediaKind,
        action: Action, created_at: datetime,
    ) -> "ProvenanceRecord":
        """Create a record with a random public asset ID, without a user ID."""
        return cls(publisher, system, media_kind, action, created_at, uuid4())

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "publisher": self.publisher,
            "system": {"name": self.system.name, "version": self.system.version},
            "media_kind": self.media_kind.value,
            "action": self.action.value,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "asset_id": str(self.asset_id),
        }

    def to_json(self) -> str:
        """Serialize unsigned data. This is not a signing/canonicalization format."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "ProvenanceRecord":
        """Parse a record strictly; parsing does not authenticate its contents."""
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate field: {key}")
                result[key] = value
            return result

        if not isinstance(text, str) or len(text) > 16384:
            raise ValueError("record must be a JSON string of at most 16384 characters")
        try:
            data = json.loads(text, object_pairs_hook=unique_object)
            fields = {"schema_version", "publisher", "system", "media_kind", "action", "created_at", "asset_id"}
            if not isinstance(data, dict) or set(data) != fields:
                raise ValueError("missing or unknown record fields")
            if type(data["schema_version"]) is not int or data["schema_version"] != 1:
                raise ValueError("unsupported schema_version")
            system = data["system"]
            if not isinstance(system, dict) or set(system) != {"name", "version"}:
                raise ValueError("system requires only name and version")
            if not isinstance(data["created_at"], str) or not isinstance(data["asset_id"], str):
                raise ValueError("created_at and asset_id must be strings")
            return cls(
                publisher=data["publisher"], system=GenerativeSystem(**system),
                media_kind=MediaKind(data["media_kind"]), action=Action(data["action"]),
                created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
                asset_id=UUID(data["asset_id"]),
            )
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ValueError(f"invalid provenance record: {exc}") from exc
