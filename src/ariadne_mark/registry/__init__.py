"""Optional local SQLite recovery registry; no central service or user accounts."""

import json
from pathlib import Path
import sqlite3

from ariadne_mark.provenance import ProvenanceRecord
from ariadne_mark.watermark import valid_token


class Registry:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS assets (token TEXT PRIMARY KEY, asset_id TEXT UNIQUE NOT NULL, record TEXT NOT NULL, sha256 TEXT NOT NULL, receipt TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def contains(self, token: str) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM assets WHERE token=?", (token,)).fetchone() is not None

    def add(self, token: str, record: ProvenanceRecord, sha256: str, receipt: dict):
        if not valid_token(token):
            raise ValueError("Invalid token")
        with self.connect() as db:
            # Uniqueness failures abort the export rather than silently rebinding an ID.
            db.execute("INSERT INTO assets VALUES (?,?,?,?,?)", (token, str(record.asset_id), record.to_json(), sha256, json.dumps(receipt)))

    def get(self, token: str) -> dict | None:
        if not valid_token(token):
            return None
        with self.connect() as db:
            row = db.execute("SELECT record,sha256 FROM assets WHERE token=?", (token,)).fetchone()
        return {"record": json.loads(row[0]), "sha256": row[1]} if row else None
