"""C2PA 2.4 soft-binding wire format for Ariadne payloads.

Algorithm identifiers are provisional and NOT registered with C2PA. The wire
shapes follow the specification; global discovery/conformance is not claimed.
"""
import base64
import re

from ariadne_mark.watermark import valid_token

ALGORITHMS = {
    'adobe.trustmark.Q.bch5': 'org.ariadne-mark.trustmark-q.bch5.v1',
    'adobe.trustmark.Q.variax-bch5': 'org.ariadne-mark.trustmark-q.video-bch5.v1',
    'meta.videoseal.1.0.bch20': 'org.ariadne-mark.videoseal.bch20.v1',
}

# TrustMark-Q/BCH-5 payload interoperability. Qualified against independent
# decoded frames and signed stores in release R3; does not authenticate a copy.
# Directional: Python Q reads video-Q marks. No VideoSeal or image aliasing.
VIDEO_DECODER_COMPATIBILITY = {
    'adobe.trustmark.Q.bch5': {'org.ariadne-mark.trustmark-q.video-bch5.v1'},
}


def compatible_manifest_algorithms(schemes, *, video=False):
    result = {ALGORITHMS[s] for s in schemes if s in ALGORITHMS}
    if video:
        for scheme in schemes:
            result.update(VIDEO_DECODER_COMPATIBILITY.get(scheme, ()))
    return result

MAX_MANIFEST_BYTES = 16 * 1024 * 1024


def algorithm_for(engine_algorithm):
    try:
        return ALGORITHMS[engine_algorithm]
    except KeyError:
        raise ValueError('Unsupported soft-binding algorithm') from None


def token_value(token):
    if not valid_token(token):
        raise ValueError('Invalid Ariadne watermark ID')
    return bytes.fromhex(token)


def query_value(token):
    return base64.b64encode(token_value(token)).decode('ascii')


def decode_query(algorithm, value):
    if algorithm not in ALGORITHMS.values() or not isinstance(value, str) or len(value) > 64:
        raise ValueError('Unsupported algorithm or invalid binding')
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError:
        raise ValueError('Invalid base64 binding') from None
    if len(raw) != 8 or base64.b64encode(raw).decode('ascii') != value or not valid_token(raw.hex()):
        raise ValueError('Invalid binding value')
    return raw.hex()


def assertion(engine_algorithm, token):
    # Native C2PA 0.91.11 normalizes this byte field into CBOR bstr (#2689).
    # A real-media regression checks the encoded bytes, not just JSON output.
    return {'label': 'c2pa.soft-binding', 'data': {'alg': algorithm_for(engine_algorithm),
            'blocks': [{'scope': {}, 'value': list(token_value(token))}]}}


def manifest_id_valid(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9:_.=-]{1,256}', value))


def _value_bytes(value):
    if isinstance(value, list) and all(type(x) is int and 0 <= x <= 255 for x in value):
        return bytes(value)
    if isinstance(value, str):
        if value.startswith("b64'") and value.endswith("'"):
            value = value[4:-1]
        try:
            return base64.b64decode(value, validate=True)
        except ValueError:
            pass
    return None


def validate_match(raw_manifest, algorithm, token):
    """Require all active soft-binding assertions to match the query.

    Multiple algorithms need a matcher capable of checking each; this SDK
    deliberately refuses to treat an unchecked additional binding as matched.
    """
    manifest_id = raw_manifest.get('active_manifest')
    if not manifest_id_valid(manifest_id):
        raise ValueError('Invalid active manifest ID')
    manifest = raw_manifest.get('manifests', {}).get(manifest_id, {})
    bindings = [a.get('data') for a in manifest.get('assertions', [])
                if isinstance(a, dict) and isinstance(a.get('label'), str)
                and re.fullmatch(r'c2pa\.soft-binding(?:__[1-9][0-9]*)?', a['label'])]
    expected = token_value(token)
    if not bindings:
        raise ValueError('Manifest has no soft binding')
    for binding in bindings:
        if (not isinstance(binding, dict) or binding.get('alg') != algorithm
                or not isinstance(binding.get('blocks'), list) or not binding['blocks']):
            raise ValueError('Manifest soft-binding algorithm mismatch')
        if any(not isinstance(b, dict) or _value_bytes(b.get('value')) != expected
               for b in binding['blocks']):
            raise ValueError('Manifest soft-binding value mismatch')
    return manifest_id


def observed_algorithms(watermark, token=None, *, video=False):
    """Identify engines that actually recovered the returned (or given) ID."""
    token = watermark.get('token') if token is None else token
    if token is None:
        return set()
    schemes = {row['algorithm'] for row in [*watermark.get('samples', []), *watermark.get('aggregates', [])]
               if row.get('token') == token and row.get('algorithm') in ALGORITHMS}
    return compatible_manifest_algorithms(schemes, video=video)


def inspect_recovered(store, asset, algorithm, token, *, trust_anchors=None, tsa_trust_anchors=None):
    from ariadne_mark.signing import read_recovered_manifest
    raw = read_recovered_manifest(store, asset, trust_anchors=trust_anchors, tsa_trust_anchors=tsa_trust_anchors)
    manifest_id = validate_match(raw, algorithm, token)
    active = raw.get('validation_results', {}).get('activeManifest', {})
    success = {r.get('code') for r in active.get('success', [])}
    failure = {r.get('code') for r in active.get('failure', [])}
    binding_failures = {'assertion.dataHash.mismatch', 'assertion.bmffHash.mismatch', 'assertion.boxesHash.mismatch'}
    binding_success = {'assertion.dataHash.match', 'assertion.bmffHash.match', 'assertion.boxesHash.match'}
    substantive = failure - binding_failures - {'signingCredential.untrusted'}
    signature = 'valid' if 'claimSignature.validated' in success and not substantive else 'not_verified'
    return {'manifest_id': manifest_id, 'soft_binding': 'matched', 'signature': signature,
            'issuer_trust': ('trusted' if 'signingCredential.trusted' in success else 'untrusted') if signature == 'valid' else 'not_checked',
            'asset_binding': 'valid' if binding_success & success and not failure & binding_failures else 'mismatch' if failure & binding_failures else 'not_checked',
            'validation_codes': sorted(code for code in success | failure if code),
            'interpretation': 'recovered_original_manifest_not_authentication_of_an_edited_copy'}
