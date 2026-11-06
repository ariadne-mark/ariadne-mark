"""Optional durable SQLite provenance/manifest lookup; IDs are not authentication."""
from contextlib import closing, contextmanager
import hashlib
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
                db.execute("CREATE TABLE IF NOT EXISTS manifests (token TEXT PRIMARY KEY REFERENCES assets(token), manifest_id TEXT UNIQUE NOT NULL, store BLOB NOT NULL, store_sha256 TEXT NOT NULL, algorithm TEXT NOT NULL, public INTEGER NOT NULL CHECK(public IN (0,1)))")

    @contextmanager
    def connect(self):
        # sqlite3's transaction context does not close a connection by itself.
        mode = '?mode=ro' if self.read_only else '?mode=rwc'
        with closing(sqlite3.connect(self.path.as_uri() + mode, uri=True, timeout=30)) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA query_only=ON' if self.read_only else 'PRAGMA synchronous=FULL')
            with db:
                yield db

    def contains(self, token):
        with self.connect() as db:
            return db.execute("SELECT 1 FROM assets WHERE token=?", (token,)).fetchone() is not None

    def add(self, token: str, record: ProvenanceRecord, sha256: str, receipt: dict, manifest=None):
        """Commit the record and optional final binary manifest atomically.

        An identical retry succeeds. A changed record, asset, receipt, manifest
        or publication choice never silently replaces an existing association.
        """
        if self.read_only:
            raise PermissionError('Verification registry is read-only')
        if not valid_token(token):
            raise ValueError('Invalid token')
        bundle = None
        if manifest is not None:
            from ariadne_mark.softbinding import ALGORITHMS, MAX_MANIFEST_BYTES, manifest_id_valid
            if (not isinstance(manifest, dict) or set(manifest) != {'id','bytes','algorithm','public'}
                    or not manifest_id_valid(manifest['id']) or manifest['algorithm'] not in ALGORITHMS.values()
                    or not isinstance(manifest['bytes'], bytes) or not 0 < len(manifest['bytes']) <= MAX_MANIFEST_BYTES
                    or type(manifest['public']) is not bool):
                raise ValueError('Invalid manifest bundle')
            bundle = (manifest['id'], manifest['bytes'], hashlib.sha256(manifest['bytes']).hexdigest(),
                      manifest['algorithm'], int(manifest['public']))
        with self.connect() as db:
            old = db.execute('SELECT asset_id,record,sha256,receipt FROM assets WHERE token=?', (token,)).fetchone()
            if old is not None:
                same = (old[0] == str(record.asset_id) and json.loads(old[1]) == record.to_dict()
                        and old[2] == sha256 and json.loads(old[3]) == receipt)
                previous = db.execute('SELECT manifest_id,store,store_sha256,algorithm,public FROM manifests WHERE token=?', (token,)).fetchone()
                if not same or previous != bundle:
                    raise ValueError('Conflicting immutable registry entry')
                return
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?)', (token, str(record.asset_id), record.to_json(), sha256, json.dumps(receipt)))
            if bundle is not None:
                db.execute('INSERT INTO manifests VALUES (?,?,?,?,?,?)', (token, *bundle))

    def remove(self, token, sha256):
        """Rollback only this export's row and manifest, in one transaction."""
        if self.read_only:
            raise PermissionError('Verification registry is read-only')
        with self.connect() as db:
            db.execute('DELETE FROM manifests WHERE token=? AND EXISTS (SELECT 1 FROM assets WHERE token=? AND sha256=?)', (token, token, sha256))
            db.execute('DELETE FROM assets WHERE token=? AND sha256=?', (token, sha256))

    def get(self, token):
        if not valid_token(token):
            return None
        with self.connect() as db:
            row = db.execute('SELECT record,sha256 FROM assets WHERE token=?', (token,)).fetchone()
        return {'record': json.loads(row[0]), 'sha256': row[1]} if row else None

    def get_manifest(self, *, token=None, manifest_id=None, public_only=False):
        if (token is None) == (manifest_id is None):
            raise ValueError('Supply exactly one manifest identifier or token')
        from ariadne_mark.softbinding import manifest_id_valid
        if token is not None and not valid_token(token) or manifest_id is not None and not manifest_id_valid(manifest_id):
            return None
        with self.connect() as db:
            # Old databases remain readable; their records have no stored manifest.
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='manifests'").fetchone():
                return None
            field, value = ('token', token) if token is not None else ('manifest_id', manifest_id)
            row = db.execute('SELECT token,manifest_id,store,store_sha256,algorithm,public FROM manifests WHERE '
                             + field + '=?' + (' AND public=1' if public_only else ''), (value,)).fetchone()
        if row is None:
            return None
        if hashlib.sha256(row[2]).hexdigest() != row[3]:
            raise ValueError('Manifest store integrity check failed')
        return dict(zip(('token','id','bytes','sha256','algorithm','public'), row))
