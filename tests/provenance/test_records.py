import dataclasses
from datetime import datetime, timedelta, timezone
import json
import unittest
from uuid import uuid1

from ariadne_mark.provenance import Action, GenerativeSystem, MediaKind, ProvenanceRecord


def example_record(**changes):
    fields = dict(
        publisher="Example Studio", system=GenerativeSystem("Example Generator", "2026.11"),
        media_kind=MediaKind.IMAGE, action=Action.CREATED,
        created_at=datetime(2026, 11, 3, 17, 0, tzinfo=timezone(timedelta(hours=7))),
    )
    fields.update(changes)
    return ProvenanceRecord.create(**fields)


class RecordTests(unittest.TestCase):
    def test_image_and_video_created_and_altered_roundtrip(self):
        for media in MediaKind:
            for action in Action:
                with self.subTest(media=media, action=action):
                    record = example_record(media_kind=media, action=action)
                    self.assertEqual(ProvenanceRecord.from_json(record.to_json()), record)
                    self.assertEqual(record.to_dict()["created_at"], "2026-11-03T10:00:00Z")
                    self.assertEqual(record.to_dict()["system"]["version"], "2026.11")

    def test_new_public_ids_are_random_and_distinct(self):
        records = [example_record() for _ in range(100)]
        self.assertEqual(len({r.asset_id for r in records}), 100)
        self.assertTrue(all(r.asset_id.version == 4 for r in records))

    def test_naive_timestamp_and_non_random_uuid_rejected(self):
        with self.assertRaises(ValueError):
            example_record(created_at=datetime(2026, 11, 3))
        with self.assertRaises(ValueError):
            dataclasses.replace(example_record(), asset_id=uuid1())

    def test_records_are_immutable(self):
        record = example_record()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.publisher = "another publisher"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.system.version = "another version"

    def test_missing_unknown_and_personal_fields_rejected(self):
        data = example_record().to_dict()
        for key in data:
            broken = dict(data)
            del broken[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                ProvenanceRecord.from_json(json.dumps(broken))
        for key in ("user_id", "email", "compliant", "trusted"):
            with self.subTest(extra=key), self.assertRaises(ValueError):
                ProvenanceRecord.from_json(json.dumps(dict(data, **{key: "unexpected"})))

    def test_malformed_values_rejected(self):
        data = example_record().to_dict()
        cases = {
            "schema_version": [True, 1.0, "1", 2, None],
            "publisher": [None, 42, " ", "a\nb", "x" * 513],
            "system": [None, [], {}, {"name": "X", "version": ""}, {"name": "X", "version": "1", "user_id": "1"}],
            "media_kind": ["audio", None, []],
            "action": ["human", None, {}],
            "created_at": [None, "yesterday", "2026-11-03", "2026-11-03T10:00:00"],
            "asset_id": [None, 123, "user@example.org", str(uuid1())],
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    ProvenanceRecord.from_json(json.dumps(dict(data, **{field: value})))

    def test_duplicate_fields_and_invalid_json_rejected(self):
        original = example_record().to_json()
        duplicate = original.replace('"schema_version": 1', '"schema_version": 2, "schema_version": 1')
        nested = original.replace('"version": "2026.11"', '"version": "wrong", "version": "2026.11"')
        for value in (duplicate, nested, "[]", "null", "{", " " * 16385, "[" * 2000, None):
            with self.subTest(value=str(value)[:50]), self.assertRaises(ValueError):
                ProvenanceRecord.from_json(value)

    def test_python_api_rejects_untyped_inputs(self):
        for changes in ({"media_kind": "image"}, {"action": "created"}, {"system": {}}, {"created_at": "now"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                example_record(**changes)


if __name__ == "__main__":
    unittest.main()
