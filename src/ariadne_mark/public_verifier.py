"""Public-response minimization and aggregate-only efficacy feedback.

Local SDK/CLI inspection remains unchanged. Public endpoints do not echo
unreviewed free-text provenance fields or arbitrary embedded metadata.
"""
from copy import deepcopy
from contextlib import contextmanager, closing
import json
import os
from pathlib import Path
import sqlite3


def load_public_sources(path):
    if path is None:
        return []
    raw = Path(path).read_bytes()
    if len(raw) > 65536:
        raise ValueError("Public source configuration exceeds64KiB")
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'sources'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(value['sources'], list) or len(value['sources']) > 100):
        raise ValueError("Invalid public source configuration")
    sources = []
    for entry in value['sources']:
        if not isinstance(entry, dict) or set(entry) != {'publisher', 'system'}:
            raise ValueError("Public sources require publisher and system only")
        system = entry['system']
        if not isinstance(system, dict) or set(system) != {'name', 'version'}:
            raise ValueError("Public sources require system.name/version")
        strings = [entry['publisher'], system['name'], system['version']]
        if any(not isinstance(s, str) or not s.strip() or len(s) > 512
               or any(ord(c) < 32 or ord(c) == 127 for c in s) for s in strings):
            raise ValueError("Public source fields must be reviewed public product text")
        sources.append(tuple(strings))
    return sources


def public_record(record, sources):
    """Only operator-reviewed system names are eligible for public disclosure.

    This is a whitelist, not automatic recognition/redaction of arbitrary PII.
    The operator must use public organization/model text and random asset IDs.
    """
    if not isinstance(record, dict):
        return None, []
    minimal = {'schema_version': 1}
    if record.get('media_kind') in {'image', 'video'}:
        minimal['media_kind'] = record['media_kind']
    if record.get('action') in {'created', 'altered'}:
        minimal['action'] = record['action']
    system = record.get('system', {})
    key = (record.get('publisher'), system.get('name'), system.get('version')) if isinstance(system, dict) else None
    if key not in sources:
        return minimal, ['publisher', 'system', 'created_at', 'asset_id']
    # Reparse the fixed SDK schema; unknown metadata extensions never escape.
    from ariadne_mark.provenance import ProvenanceRecord
    try:
        return ProvenanceRecord.from_json(json.dumps(record)).to_dict(), []
    except ValueError:
        return minimal, ['invalid_public_record']


def public_report(report, sources=()):
    """Return a compact public API report, keeping private debug data local."""
    result = {k: deepcopy(report[k]) for k in ['schema_version', 'label', 'token_mismatch'] if k in report}
    redacted = []
    c2pa = report.get('c2pa', {})
    if c2pa:
        allowed = ['status', 'signature', 'issuer_trust', 'timestamp_trust', 'credential_time',
                   'revocation', 'reason', 'claim_scope', 'record_scope', 'ingredient_count',
                   'watermark_algorithm', 'token']
        result['c2pa'] = {k: deepcopy(c2pa[k]) for k in allowed if k in c2pa}
        for flag in ['development_identity', 'visible_disclosure']:
            if type(c2pa.get(flag)) is bool:
                result['c2pa'][flag] = c2pa[flag]
        if c2pa.get('audio') in ('none', 'original', 'synthetic', 'unknown'):
            result['c2pa']['audio'] = c2pa['audio']
        known_profiles = {'fast-cpu-v1', 'fast-cpu-v2', 'fast-cpu-candidate-v1',
                          'resilient-cpu-candidate-v1', 'economy-5s-125ms-cpu-v1', 'economy-2s-125ms-cpu-v1'}
        if isinstance(c2pa.get('watermark_profile'), str) and c2pa['watermark_profile'] in known_profiles:
            result['c2pa']['watermark_profile'] = c2pa['watermark_profile']
        if c2pa.get('record'):
            # Uploaded self-declared names cannot unlock fields by themselves.
            approved = sources if c2pa.get('issuer_trust') == 'trusted' and c2pa.get('status') == 'verified_claim' else ()
            result['c2pa']['record'], fields = public_record(c2pa['record'], approved)
            redacted.extend('c2pa.record.' + x for x in fields)
    watermark = report.get('watermark', {})
    if watermark:
        allowed = ['status', 'reason', 'token', 'algorithm_scope', 'engines_checked',
                   'coverage', 'scope', 'sample_coverage', 'checked_frames']
        result['watermark'] = {k: deepcopy(watermark[k]) for k in allowed if k in watermark}
        searches = [a['search'] for a in watermark.get('attempts', []) if 'search' in a]
        if searches:
            allowed = ['reason', 'frames_decoded', 'file_exhausted', 'hypotheses_complete',
                       'max_frames', 'max_seconds', 'cnn_passes', 'whole_video_coverage']
            result['watermark']['search'] = {k: searches[-1][k] for k in allowed if k in searches[-1]}
    recovery = report.get('recovery', {})
    if recovery:
        allowed = ['status', 'binding', 'content_binding', 'record_scope']
        result['recovery'] = {k: recovery[k] for k in allowed if k in recovery}
        if recovery.get('record'):
            result['recovery']['record'], fields = public_record(recovery['record'], sources)
            redacted.extend('recovery.record.' + x for x in fields)
    result['public_output'] = {'policy': 'reviewed_system_fields_only', 'redacted_fields': redacted,
                               'raw_metadata_and_debug_omitted': True}
    return result


class FeedbackStore:
    """Nine counters; no media, IDs, IPs, contact data, text or event history."""
    RATINGS = {'correct_result', 'incorrect_result', 'unable_to_check'}
    MEDIA = {'image', 'video', 'unknown'}

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        existed = self.path.exists()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS feedback (rating TEXT NOT NULL, media TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(rating,media))')
        if not existed:
            os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, value):
        if (not isinstance(value, dict) or set(value) != {'rating', 'media'}
                or not isinstance(value['rating'], str) or value['rating'] not in self.RATINGS
                or not isinstance(value['media'], str) or value['media'] not in self.MEDIA):
            raise ValueError('Use rating and media enums only; no personal information or free text')
        with self.connect() as db:
            db.execute('INSERT INTO feedback(rating,media,count) VALUES(?,?,1) ON CONFLICT(rating,media) DO UPDATE SET count=count+1',
                       (value['rating'], value['media']))

    def summary(self):
        return self.read_summary(self.path)

    @staticmethod
    def read_summary(path):
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
            rows = [{'rating': r, 'media': m, 'count': n} for r, m, n in db.execute('SELECT rating,media,count FROM feedback ORDER BY rating,media')]
        return {'schema_version': 1, 'storage': 'aggregate_counters_only', 'counts': rows}
