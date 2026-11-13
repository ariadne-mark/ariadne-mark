"""Reproducible local exporter / read-only registry verifier deployment.

The kit configures existing SDK controls; it never declares legal compliance,
issues production credentials or changes watermark profiles.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from importlib.resources import files
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit
from ariadne_mark.errors import AriadneError

NGINX_IMAGE = 'nginx@sha256:583b7f2fce1cdb8da5ad5c39ebd3c33b98b87d493190e548bdee1fa8c619c311'
PROFILES = {'economy_5s', 'economy_2s', 'resilient'}


def _json(path):
    from ariadne_mark.reports import _strict_json
    raw = Path(path).read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError('Kit JSON exceeds 1 MiB')
    return _strict_json(raw)


def _write(path, value, mode=0o644):
    raw = value if isinstance(value, bytes) else value.encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def _dump(path, value):
    _write(path, json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def _url(value, *, development=False):
    if not isinstance(value, str) or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError('Configure a verifier URL')
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in {'', '/'}):
        raise ValueError('Verifier URL must be an HTTPS origin without credentials or query')
    _ = url.port  # Reject invalid port syntax.
    if not development:
        from ariadne_mark.profiles import _public_https
        if not _public_https(value) or url.hostname.endswith(('.example', '.test', '.invalid', '.example.org', '.example.com')) or url.hostname in {'example.org', 'example.com'}:
            raise ValueError('Production needs your public HTTPS origin, not a placeholder')
    return value.rstrip('/')


def load(root):
    from ariadne_mark.profiles import load as load_profile
    root = Path(root).resolve()
    value = _json(root / 'config/kit.json')
    if not isinstance(value, dict):
        raise ValueError('Invalid kit schema')
    value.setdefault('verification_scope', 'all')  # Preserve scope of existing deployments.
    if not isinstance(value['verification_scope'], str) or value['verification_scope'] not in {'all', 'current'}:
        raise ValueError('Invalid kit verification_scope')
    expected = {'verification_scope', 'schema_version', 'mode', 'verifier_url', 'timestamp_url',
                'public_manifests', 'threads', 'max_upload_mb', 'verification_timeout'}
    if not isinstance(value, dict) or set(value) != expected or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Invalid kit schema')
    if not isinstance(value['mode'], str) or value['mode'] not in {'development', 'production'} or type(value['public_manifests']) is not bool:
        raise ValueError('Invalid kit mode/publication choice')
    for key, low, high in [('threads', 1, 8), ('max_upload_mb', 1, 512), ('verification_timeout', 1, 600)]:
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError('Invalid kit limit: ' + key)
    value['verifier_url'] = _url(value['verifier_url'], development=value['mode'] == 'development')
    if value['timestamp_url'] is not None:
        if not isinstance(value['timestamp_url'], str):
            raise ValueError('Timestamp URL must be text or null')
        tsa = urlsplit(value['timestamp_url'])
        if tsa.scheme != 'https' or not tsa.hostname or tsa.username or tsa.password or tsa.fragment or tsa.query:
            raise ValueError('Timestamp URL must be HTTPS without credentials or query')
    profile = load_profile(root / 'config/product.json')
    if profile['sdk']['video_profile'] not in PROFILES:
        raise ValueError('Kit supports Economy5s, Economy2s and Resilient')
    if set(profile['media_kinds']) - {'image', 'video'} or profile['sdk']['audio_kind'] not in {'none', 'original'}:
        raise ValueError('Kit covers visual media with no/original audio only')
    from ariadne_mark.public_verifier import load_public_sources
    sources = load_public_sources(root / 'config/public-sources.json')
    expected_source = (profile['publisher'], profile['system']['name'], profile['system']['version'])
    if expected_source not in sources:
        raise ValueError('Product publisher/system must match reviewed public sources')
    if profile['deployment']['verifier_url'] != value['verifier_url']:
        raise ValueError('Product and kit verifier URLs must match')
    return value, profile


def _dev_tls(root):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    import ipaddress
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Ariadne kit DEVELOPMENT localhost')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=30)).add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.DNSName('kit.test'),
                            x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), False).sign(key, hashes.SHA256()))
    _write(root / 'private/tls/key.pem', key.private_bytes(serialization.Encoding.PEM,
           serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), 0o600)
    _write(root / 'private/tls/cert.pem', cert.public_bytes(serialization.Encoding.PEM))


def _nginx(config):
    raw = files('ariadne_mark').joinpath('kit_assets', 'nginx.conf').read_text()
    route = 'include /etc/nginx/kit-proxy.conf;'
    if config['mode'] == 'production':
        route = ('return 308 ' + config['verifier_url'] + '$request_uri;') if config['verifier_url'] else 'return 503;'
    return (raw.replace('@@HTTP_ROUTE@@', route).replace('@@MAX_UPLOAD_MB@@', str(config['max_upload_mb']))
            .replace('@@PROXY_TIMEOUT@@', str(config['verification_timeout'] + 10)))


def render(root):
    """Explicitly regenerate the edge config after an operator config change."""
    root = Path(root).resolve(); config, _ = load(root)
    path = root / 'nginx.conf.new'
    _write(path, _nginx(config))
    os.replace(path, root / 'nginx.conf')
    return {'status': 'rendered', 'path': str(root / 'nginx.conf'), 'verifier_url': config['verifier_url']}


def initialize(directory, *, publisher, system, system_version, development=False, verifier_url=None,
               public_manifests=False):
    from ariadne_mark.provenance import GenerativeSystem, _text
    from ariadne_mark.profiles import template
    from ariadne_mark.version import sdk_version
    _text(publisher, 'publisher'); GenerativeSystem(system, system_version)
    if type(development) is not bool or type(public_manifests) is not bool:
        raise ValueError('Explicit boolean mode/publication flags required')
    if verifier_url is None and development:
        verifier_url = 'https://localhost:8443'
    if verifier_url is not None:
        verifier_url = _url(verifier_url, development=development)
    root = Path(directory).absolute()
    root.mkdir(mode=0o750, parents=True, exist_ok=False)
    # A failed init stays visibly incomplete rather than deleting files in a
    # user-owned directory. Never overwrite an existing kit or key.
    _write(root / 'INIT_INCOMPLETE', 'Initialization did not finish. Do not deploy.\n')
    for name in ['config', 'registry', 'state', 'inputs', 'outputs', 'private',
                 'private/provider', 'private/tls']:
        (root / name).mkdir(mode=0o700 if name.startswith('private') else 0o750)
    from ariadne_mark.reports import generate_report_key
    generate_report_key(root / 'private/reports')
    _write(root / 'config/report.pub', (root / 'private/reports/report.pub').read_bytes())
    if development:
        from ariadne_mark.signing import create_development_identity
        # The generator requires a new directory; the parent is private already.
        (root / 'private/provider').rmdir()
        create_development_identity(root / 'private/provider')
        _write(root / 'config/issuer-roots.pem', (root / 'private/provider/trust.pem').read_bytes())
        _dev_tls(root)
    kit = {'schema_version': 1, 'mode': 'development' if development else 'production',
           'verifier_url': verifier_url, 'timestamp_url': None, 'public_manifests': public_manifests,
           'threads': 2, 'max_upload_mb': 128, 'verification_timeout': 180,
           'verification_scope': 'current'}
    profile = template()
    profile.update(publisher=publisher, system={'name': system, 'version': system_version}, role='provider')
    profile['sdk'].update(audio_kind='none')
    profile['deployment'].update(verifier_url=verifier_url, verifier_free=True, verifier_upload=True,
        verifier_api=True, verifier_url_submission=False, verifier_provider='own',
        feedback_url=(verifier_url + '/feedback') if verifier_url else None)
    # Scope/privacy/accessibility/evidence declarations remain unknown until
    # the operator reviews them. Initialization is not an assessment.
    _dump(root / 'config/kit.json', kit)
    _dump(root / 'config/product.json', profile)
    _dump(root / 'config/public-sources.json', {'schema_version': 1, 'sources': [
        {'publisher': publisher, 'system': {'name': system, 'version': system_version}}]})
    _dump(root / 'batch.example.json', {'schema_version': 1, 'jobs': [
        {'source': 'your-final-image.png', 'destination': 'marked-image.png', 'created_at': None},
        {'source': 'your-final-video.mp4', 'destination': 'marked-video.mp4', 'created_at': None,
         'video_profile': 'economy_5s', 'audio_kind': 'none'}]})
    _write(root / '.env', f'KIT_SDK_IMAGE=ariadne-mark:{sdk_version()}\nKIT_NGINX_IMAGE={NGINX_IMAGE}\n'
        f'KIT_UID={os.getuid()}\nKIT_GID={os.getgid()}\nKIT_BIND_ADDRESS=127.0.0.1\n'
        'KIT_HTTP_PORT=8800\nKIT_HTTPS_PORT=8443\n')
    for name in ['compose.yaml', 'README.md', 'production-egress.yaml']:
        raw = files('ariadne_mark').joinpath('kit_assets', name).read_text()
        _write(root / name, raw)
    _write(root / 'nginx.conf', _nginx(kit))
    _write(root / 'kit-proxy.conf', files('ariadne_mark').joinpath('kit_assets', 'kit-proxy.conf').read_text())
    _write(root / '.gitignore', 'private/\nregistry/\nstate/\ninputs/\noutputs/\n.env\n')
    from ariadne_mark.registry import Registry
    Registry(root / 'registry/assets.sqlite3')
    os.chmod(root / 'registry/assets.sqlite3', 0o600)
    (root / 'INIT_INCOMPLETE').unlink()
    return {'directory': str(root), 'mode': kit['mode'], 'status': 'initialized',
            'production_credentials_supplied': False, 'legal_determination': 'not_performed',
            'next': 'kit check; supply final media and actual generation timestamps; see README.md'}


def check(root, *, runtime=False):
    root = Path(root).resolve(); errors = []
    if (root / 'INIT_INCOMPLETE').exists():
        errors.append('Initialization is incomplete')
    try:
        config, profile = load(root)
    except (ValueError, OSError) as exc:
        return {'status': 'configuration_required', 'errors': [str(exc)], 'legal_determination': 'not_performed'}
    from ariadne_mark.verification.scope import runtime_warnings
    warnings = runtime_warnings(config['verification_scope'])
    needed = ['private/provider/identity.json', 'private/provider/private.key',
              'private/provider/certificate.pem', 'private/reports/report.key',
              'private/tls/key.pem', 'private/tls/cert.pem', 'config/issuer-roots.pem', 'config/report.pub', 'registry/assets.sqlite3']
    if config['mode'] == 'production':
        needed.append('config/tsa-roots.pem')
        if not config['timestamp_url']:
            errors.append('Configure timestamp_url: the SDK currently requires a trusted TSA for production exports')
    for name in needed:
        path = root / name
        if not path.is_file() or path.is_symlink():
            errors.append('Missing regular file: ' + name)
        elif name.endswith(('.key', 'key.pem')) and stat.S_IMODE(path.stat().st_mode) & 0o077:
            errors.append('Private key must not be group/world-readable: ' + name)
    if not errors:
        try:
            from ariadne_mark.signing import SigningIdentity, validate_trust_roots
            identity = SigningIdentity.from_directory(root / 'private/provider',
                allow_dev=config['mode'] == 'development', timestamp_url=config['timestamp_url'])
            if identity.development != (config['mode'] == 'development'):
                raise ValueError('Signing identity and kit mode differ')
            if config['mode'] == 'production':
                validate_trust_roots(root / 'config/issuer-roots.pem')
                validate_trust_roots(root / 'config/tsa-roots.pem')
                from ariadne_mark.signing import validate_provider_chain
                validate_provider_chain(identity.certificate, root / 'config/issuer-roots.pem')
            import ssl
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(root / 'private/tls/cert.pem', root / 'private/tls/key.pem')
            from ariadne_mark.reports import ReportSigner
            signer = ReportSigner.from_file(root / 'private/reports/report.key', config['verifier_url'])
            if signer.public_pem() != (root / 'config/report.pub').read_bytes():
                raise ValueError('Pinned report public key differs from the signing key')
            from ariadne_mark.registry import Registry
            Registry(root / 'registry/assets.sqlite3', read_only=True)
            from cryptography import x509
            from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PublicFormat
            cert = x509.load_pem_x509_certificates(identity.certificate.read_bytes())[0]
            key = load_pem_private_key(identity.private_key.read_bytes(), password=None)
            if key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo) != cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo):
                raise ValueError('Provider key does not match its certificate')
            if not cert.not_valid_before_utc <= datetime.now(timezone.utc) <= cert.not_valid_after_utc:
                raise ValueError('Provider certificate is not currently valid')
        except (ValueError, OSError, AriadneError) as exc:
            errors.append(str(exc))
    if runtime:
        from ariadne_mark.c2pa_runtime import runtime_info
        info = runtime_info()
        if info['status'] != 'qualified':
            errors.append('Native C2PA runtime is not qualified')
    from ariadne_mark.profiles import evaluate
    return {'status': 'configuration_required' if errors else 'ready_for_development' if config['mode'] == 'development' else 'local_configuration_checked',
            'errors': errors, 'mode': config['mode'], 'profile': evaluate(profile),
            'warnings': warnings, 'legal_determination': 'not_performed', 'public_reachability': 'not_checked',
            'certificate_enrollment': 'not_checked',
            'issuer_chain': 'checked_against_configured_roots' if not errors and config['mode'] == 'production' else 'not_checked',
            'default_video_profile': profile['sdk']['video_profile']}


def _inside(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('Batch paths must be relative to inputs/outputs')
    result = (root / value).resolve()
    if not result.is_relative_to(root.resolve()) or result == root.resolve():
        raise ValueError('Batch path escapes inputs/outputs')
    return result


def export_batch(root, batch):
    """Fail-fast preflight, then one resident SDK across the batch.

    Each export retains the SDK's atomic publication/rollback boundary. Earlier
    successful exports remain if a later job fails; there is no batch-wide ACID
    promise. The per-file receipts identify exactly what was committed.
    """
    root = Path(root).resolve(); config, profile = load(root)
    data = _json(batch)
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'jobs'} or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not isinstance(data['jobs'], list) or not 1 <= len(data['jobs']) <= 1000):
        raise ValueError('Batch needs 1–1000 jobs')
    from ariadne_mark.provenance import ProvenanceRecord, GenerativeSystem, MediaKind, Action
    jobs, destinations = [], set()
    for row in data['jobs']:
        if (not isinstance(row, dict) or not {'source', 'destination', 'created_at'} <= set(row)
                or set(row) - {'source', 'destination', 'created_at', 'video_profile', 'audio_kind', 'publish_manifest'}):
            raise ValueError('Invalid batch job fields')
        source, destination = _inside(root / 'inputs', row['source']), _inside(root / 'outputs', row['destination'])
        if not source.is_file() or source.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.mp4'}:
            raise ValueError('Job needs an existing supported final input')
        if source.suffix.lower() != destination.suffix.lower() or destination in destinations or destination.exists():
            raise ValueError('Destination must be new, unique and have the same media extension')
        destinations.add(destination)
        mode = row.get('video_profile', profile['sdk']['video_profile'])
        if not isinstance(mode, str) or mode not in PROFILES or row.get('audio_kind', 'none') not in ('none', 'original'):
            raise ValueError('Unsupported video profile/audio kind')
        publish = row.get('publish_manifest', False)
        if type(publish) is not bool or publish and not config['public_manifests']:
            raise ValueError('Full manifest publication requires the explicit kit opt-in')
        if not isinstance(row['created_at'], str):
            raise ValueError('Supply the actual generation time with timezone for each job')
        record = ProvenanceRecord.create(publisher=profile['publisher'], system=GenerativeSystem(**profile['system']),
            media_kind=MediaKind.VIDEO if source.suffix.lower() == '.mp4' else MediaKind.IMAGE,
            action=Action.CREATED, created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')))
        record.validate_for_export()
        if source.suffix.lower() == '.mp4':
            from ariadne_mark.video import probe
            if probe(source)['audio'] and row.get('audio_kind', 'none') == 'none':
                raise ValueError('Input contains audio; select audio_kind=original for non-synthetic audio')
        selected = deepcopy(profile); selected['sdk'].update(video_profile=mode, audio_kind=row.get('audio_kind', 'none'))
        jobs.append((source, destination, record, selected, publish))
    from ariadne_mark.signing import SigningIdentity
    from ariadne_mark.pipeline import SDK
    from ariadne_mark.registry import Registry
    from ariadne_mark.watermark import LazyWatermarker
    from ariadne_mark.videoq import VideoWatermarker
    identity = SigningIdentity.from_directory(root / 'private/provider', allow_dev=config['mode'] == 'development', timestamp_url=config['timestamp_url'])
    if identity.development != (config['mode'] == 'development'):
        raise ValueError('Signing identity and kit mode differ')
    with SDK(marker=LazyWatermarker(threads=config['threads']), identity=identity,
             registry=Registry(root / 'registry/assets.sqlite3'), trust_anchors=root / 'config/issuer-roots.pem',
             tsa_trust_anchors=(root / 'config/tsa-roots.pem') if config['mode'] == 'production' else None,
             video_marker=VideoWatermarker(threads=config['threads'], profile=profile['sdk']['video_profile'])) as sdk:
        results = []
        for number, (source, destination, record, selected, publish) in enumerate(jobs):
            destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            receipt = sdk.mark(source, destination, record, profile=selected,
                video_profile=selected['sdk']['video_profile'] if record.media_kind is MediaKind.VIDEO else None,
                audio_kind=selected['sdk']['audio_kind'], publish_manifest=publish)
            results.append({'job': number, 'destination': str(destination.relative_to(root / 'outputs')),
                            'token': receipt['token'], 'sha256': receipt['sha256'], 'sdk_version': receipt['sdk_version']})
            print(json.dumps({'kind': 'kit_export', **results[-1]}), flush=True)
    return {'status': 'complete', 'exports': results, 'sdk_reused_per_batch': True}


def serve(root):
    root = Path(root).resolve(); config, _ = load(root)
    from ariadne_mark.isolated_verifier import IsolatedVerifier
    from ariadne_mark.reports import ReportSigner
    from ariadne_mark.server import serve as run_server
    with IsolatedVerifier(registry=root / 'registry/assets.sqlite3', trust_anchors=root / 'config/issuer-roots.pem',
            tsa_trust_anchors=(root / 'config/tsa-roots.pem') if config['mode'] == 'production' else None,
            threads=config['threads'], timeout=config['verification_timeout'],
            verification_scope=config['verification_scope']) as verifier:
        run_server(verifier, host='0.0.0.0', port=8080, production=config['mode'] == 'production',
            max_upload_mb=config['max_upload_mb'], public_sources=root / 'config/public-sources.json',
            feedback_url=config['verifier_url'] + '/feedback',
            feedback_db=root / 'state/feedback.sqlite', public_manifests=config['public_manifests'],
            report_signer=ReportSigner.from_file(root / 'private/reports/report.key', config['verifier_url']))
