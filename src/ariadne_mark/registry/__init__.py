"""Optional local SQLite lookup. IDs are references, not content authentication."""
import json
from pathlib import Path
import sqlite3
from ariadne_mark.provenance import ProvenanceRecord
from ariadne_mark.watermark import valid_token

class Registry:
    def __init__(self, path: Path, *, read_only=False):
        self.path = Path(path).resolve()
        self.read_only = read_only
        if read_only:
            with self.connect() as db:
                db.execute("SELECT token FROM assets LIMIT 0")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as db:
                db.execute("CREATE TABLE IF NOT EXISTS assets (token TEXT PRIMARY KEY, asset_id TEXT UNIQUE NOT NULL, record TEXT NOT NULL, sha256 TEXT NOT NULL, receipt TEXT NOT NULL)")

    def connect(self):
        if self.read_only:
            db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=30)
            db.execute('PRAGMA query_only=ON')
        else:
            db = sqlite3.connect(self.path, timeout=30)
            db.execute('PRAGMA synchronous=FULL')
        return db

    def contains(self, token):
        with self.connect() as db:
            return db.execute("SELECT 1 FROM assets WHERE token=?", (token,)).fetchone() is not None

    def add(self, token: str, record: ProvenanceRecord, sha256: str, receipt: dict):
        if self.read_only:
            raise PermissionError('Verification registry is read-only')
        if not valid_token(token):
            raise ValueError('Invalid token')
        with self.connect() as db:
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?)', (token, str(record.asset_id), record.to_json(), sha256, json.dumps(receipt)))

    def remove(self, token, sha256):
        """Rollback only this export's row; never remove a different binding."""
        if self.read_only:
            raise PermissionError('Verification registry is read-only')
        with self.connect() as db:
            db.execute('DELETE FROM assets WHERE token=? AND sha256=?', (token, sha256))

    def get(self, token):
        if not valid_token(token):
            return None
        with self.connect() as db:
            row = db.execute('SELECT record,sha256 FROM assets WHERE token=?', (token,)).fetchone()
        return {'record': json.loads(row[0]), 'sha256': row[1]} if row else None
