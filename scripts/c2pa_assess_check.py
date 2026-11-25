#!/usr/bin/env python3
"""Native assessment smoke tests on independently generated synthetic inputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import zlib


PNG = b'\x89PNG\r\n\x1a\n'


def png_chunk(kind, payload):
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))


def test_png():
    payload = (b'\x00' + bytes((61, 120, 210)) * 64) * 64
    return PNG + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 64, 64, 8, 2, 0, 0, 0)) + \
        png_chunk(b'IDAT', zlib.compress(payload)) + png_chunk(b'IEND', b'')


def bad_claim_png(data):
    """Change only the CBOR map header inside the fixture's existing caBX chunk."""
    assert data.startswith(PNG)
    output = bytearray(PNG)
    offset = len(PNG)
    damaged = 0
    while offset < len(data):
        length = int.from_bytes(data[offset:offset + 4], 'big')
        kind = data[offset + 4:offset + 8]
        payload = bytearray(data[offset + 8:offset + 8 + length])
        if kind == b'caBX':
            tag = b'c2pa.claim.v2\x00'
            start = payload.index(tag) + len(tag)
            assert payload[start + 4:start + 8] == b'cbor'
            assert 0xA0 <= payload[start + 8] < 0xB8
            payload[start + 8] = 0xFF
            damaged += 1
        output.extend(png_chunk(kind, payload))
        offset += length + 12
    assert offset == len(data) and damaged == 1
    return bytes(output)


def main(clock):
    from ariadne_mark.provenance import Action, GenerativeSystem, MediaKind, ProvenanceRecord
    from ariadne_mark.signing import SigningIdentity, create_development_identity, sign_file
    from ariadne_mark.watermark import new_token

    clock = Path(clock).resolve(strict=True)
    clock_hash = hashlib.sha256(clock.read_bytes()).hexdigest()
    cli = Path(__file__).with_name('c2pa_assess.py')
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        create_development_identity(root / 'signer')
        trust = root / 'signer/trust.pem'
        unsigned = root / 'unsigned.png'
        unsigned.write_bytes(test_png())
        (root / 'truncated.png').write_bytes(unsigned.read_bytes()[:25])
        record = ProvenanceRecord.create(publisher='Synthetic native smoke test',
                                         system=GenerativeSystem('Fixture', '1'), media_kind=MediaKind.IMAGE,
                                         action=Action.CREATED, created_at=now)
        signed = root / 'signed.png'
        identity = SigningIdentity.from_directory(root / 'signer', allow_dev=True)
        sign_file(unsigned, signed, record, new_token(), identity)
        (root / 'invalid-claim.png').write_bytes(bad_claim_png(signed.read_bytes()))

        def invoke(name, hash_value=clock_hash):
            return subprocess.run([sys.executable, cli, root / name, '--trust-list', trust,
                                   '--tsa-trust-list', trust, '--validation-time', now.isoformat(),
                                   '--clock-library', clock, '--clock-sha256', hash_value],
                                  check=False, capture_output=True, timeout=105)

        valid = invoke('signed.png')
        assert valid.returncode == 0, valid.stderr
        assert json.loads(valid.stdout)['manifests']
        for name, exit_code, outcome in (('unsigned.png', 3, 'manifest_not_found'),
                                         ('truncated.png', 6, 'native_validation_failed')):
            run = invoke(name)
            assert run.returncode == exit_code and not run.stdout, run
            assert json.loads(run.stderr)['outcome'] == outcome, run
        invalid = invoke('invalid-claim.png')
        if invalid.returncode == 0:
            failures = json.loads(invalid.stdout)['manifests'][0]['validationResults']['failure']
            assert any(entry['code'].startswith('claim.') for entry in failures), failures
        else:
            assert invalid.returncode in (4, 6) and not invalid.stdout, invalid
        failure = invoke('signed.png', '0' * 64)
        assert failure.returncode == 2 and not failure.stdout, failure
        print('PASS signed, unsigned, truncated, invalid claim and assessment infrastructure error')


if __name__ == '__main__':
    main(sys.argv[1])
