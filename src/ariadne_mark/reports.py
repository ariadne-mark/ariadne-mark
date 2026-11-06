"""Portable JWS receipts. A signature authenticates a result, not its correctness.

JWS uses Ed25519/EdDSA (RFC 8037) and exact encoded bytes (RFC 7515), not a
claim of RFC 8785 canonicalization. Public keys must be pinned independently.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from ariadne_mark.version import sdk_version

TYPE = 'application/vnd.ariadne.verification+json'
MAX_REPORT_BYTES = 2 * 1024 * 1024


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _unb64(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Invalid base64url')
    raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    if _b64(raw) != value:
        raise ValueError('Non-canonical base64url')
    return raw


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def _public_bytes(key):
    from cryptography.hazmat.primitives import serialization
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public_key):
    return 'sha256:' + hashlib.sha256(_public_bytes(public_key)).hexdigest()


def file_digest(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def generate_report_key(directory):
    """Create a separate signing key; never overwrite an existing directory."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    raw = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    fd = os.open(directory / 'report.key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    (directory / 'report.pub').write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return {'key_id': key_id(key.public_key()), 'private_key': str(directory / 'report.key'),
            'public_key': str(directory / 'report.pub')}


class ReportSigner:
    def __init__(self, private_key, verifier_id):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError('Report key must be Ed25519')
        if (not isinstance(verifier_id, str) or not verifier_id.strip()
                or len(verifier_id) > 512 or any(ord(c) < 33 or ord(c) == 127 for c in verifier_id)):
            raise ValueError('Supply a stable public verifier identifier without whitespace')
        self._key, self.verifier_id = private_key, verifier_id
        self.key_id = key_id(private_key.public_key())

    @classmethod
    def from_file(cls, path, verifier_id):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        return cls(load_pem_private_key(Path(path).read_bytes(), password=None), verifier_id)

    def public_pem(self):
        from cryptography.hazmat.primitives import serialization
        return self._key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def public_jwk(self):
        return {'kty': 'OKP', 'crv': 'Ed25519', 'use': 'sig', 'alg': 'EdDSA',
                'kid': self.key_id, 'x': _b64(_public_bytes(self._key.public_key()))}

    def sign(self, result, *, sha256, size_bytes, media_type):
        if not isinstance(sha256, str) or not re.fullmatch('[0-9a-f]{64}', sha256):
            raise ValueError('Invalid asset SHA-256')
        if type(size_bytes) is not int or size_bytes < 0 or media_type not in {'image/png', 'image/jpeg', 'video/mp4'}:
            raise ValueError('Invalid asset size or type')
        if not isinstance(result, dict) or 'signed_report' in result:
            raise ValueError('Supply one result without a nested receipt')
        payload = {'schema_version': 1, 'type': TYPE,
            'asset': {'sha256': sha256, 'size_bytes': size_bytes, 'media_type': media_type},
            'verified_at': datetime.now(timezone.utc).isoformat(),
            'verifier': {'id': self.verifier_id, 'sdk_version': sdk_version(), 'key_id': self.key_id},
            'result': result}
        protected = _b64(_json({'alg': 'EdDSA', 'typ': TYPE, 'kid': self.key_id}))
        encoded = _b64(_json(payload))
        message = (protected + '.' + encoded).encode('ascii')
        compact = message.decode('ascii') + '.' + _b64(self._key.sign(message))
        if len(compact) > MAX_REPORT_BYTES:
            raise ValueError('Report exceeds maximum size')
        return {'format': 'JWS-compact', 'jws': compact}


def verify_report(envelope, public_key_pem, *, asset=None, verifier_id=None):
    """Verify against a caller-pinned key; never trust an embedded key/URL."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if isinstance(envelope, dict) and 'signed_report' in envelope:
        envelope = envelope['signed_report']
    if not isinstance(envelope, dict) or set(envelope) != {'format', 'jws'} or envelope['format'] != 'JWS-compact':
        raise ValueError('Expected a JWS-compact receipt')
    compact = envelope['jws']
    if not isinstance(compact, str) or len(compact) > MAX_REPORT_BYTES:
        raise ValueError('Invalid report size')
    parts = compact.split('.')
    if len(parts) != 3:
        raise ValueError('Invalid compact JWS')
    protected = _strict_json(_unb64(parts[0]))
    key = load_pem_public_key(public_key_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError('Pinned report key must be Ed25519')
    if protected != {'alg': 'EdDSA', 'typ': TYPE, 'kid': key_id(key)}:
        raise ValueError('Unexpected signature algorithm, type or key ID')
    try:
        key.verify(_unb64(parts[2]), (parts[0] + '.' + parts[1]).encode('ascii'))
    except InvalidSignature:
        raise ValueError('Report signature is invalid') from None
    payload = _strict_json(_unb64(parts[1]))
    if (not isinstance(payload, dict) or set(payload) != {'schema_version','type','asset','verified_at','verifier','result'}
            or type(payload['schema_version']) is not int or payload['schema_version'] != 1 or payload['type'] != TYPE
            or not isinstance(payload['result'], dict)):
        raise ValueError('Invalid report schema')
    info, description = payload['verifier'], payload['asset']
    if (not isinstance(info, dict) or set(info) != {'id','sdk_version','key_id'} or info['key_id'] != key_id(key)
            or not all(isinstance(info[k], str) and info[k] for k in info)):
        raise ValueError('Invalid verifier identity')
    if verifier_id is not None and info['id'] != verifier_id:
        raise ValueError('Unexpected verifier identifier')
    if (not isinstance(description, dict) or set(description) != {'sha256','size_bytes','media_type'}
            or not isinstance(description['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', description['sha256'])
            or type(description['size_bytes']) is not int or description['size_bytes'] < 0
            or description['media_type'] not in {'image/png','image/jpeg','video/mp4'}):
        raise ValueError('Invalid asset description')
    if not isinstance(payload['verified_at'], str):
        raise ValueError('Invalid verification time')
    instant = datetime.fromisoformat(payload['verified_at'])
    if instant.tzinfo is None:
        raise ValueError('Verification time requires a timezone')
    if asset is not None and file_digest(asset) != (description['sha256'], description['size_bytes']):
        raise ValueError('Asset does not match the signed report')
    return payload
