"""Local C2PA signing and read-back validation via the official native SDK."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from ariadne_mark.c2pa_types import DigitalSourceType
from ariadne_mark.errors import AriadneError
from ariadne_mark.provenance import ProvenanceRecord
from ariadne_mark.version import sdk_version

ASSERTION = "org.ariadne-mark.provenance"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}


@dataclass(frozen=True)
class SigningIdentity:
    certificate: Path
    private_key: Path
    development: bool = False
    timestamp_url: str | None = None
    # Authenticated TSA (e.g. SSL.com C2PA TSA, ``Authorization: Bearer``):
    # path to an owner-only file holding the token, never the token itself.
    timestamp_credential_file: Path | None = None
    timestamp_timeout: float = 10.0
    timestamp_ca_bundle: Path | None = None

    def __post_init__(self):
        if self.timestamp_url is not None:
            validate_timestamp_url(self.timestamp_url, allow_loopback_http=self.development)
        if self.timestamp_credential_file is not None and not self.timestamp_url:
            raise ValueError('A TSA credential file requires a TSA URL')
        if (type(self.timestamp_timeout) not in (int, float) or not 0 < self.timestamp_timeout <= 60):
            raise ValueError('TSA timeout must be between 0 and 60 seconds')

    def __repr__(self):
        return (f'SigningIdentity(development={self.development}, timestamp_url={self.timestamp_url!r}, '
                f'authenticated_tsa={self.timestamp_credential_file is not None})')

    @classmethod
    def from_directory(cls, directory: Path, *, allow_dev: bool = False, timestamp_url=None,
                       timestamp_credential_file=None, timestamp_timeout=10.0, timestamp_ca_bundle=None):
        directory = Path(directory)
        config = json.loads((directory / "identity.json").read_text())
        if config.get("development") is not False and not allow_dev:
            raise AriadneError("Development identity requires explicit allow_dev / --allow-dev")
        return cls(directory / "certificate.pem", directory / "private.key", config.get("development") is not False, timestamp_url,
                   Path(timestamp_credential_file) if timestamp_credential_file else None, timestamp_timeout,
                   Path(timestamp_ca_bundle) if timestamp_ca_bundle else None)


def validate_timestamp_url(value, *, allow_loopback_http=False):
    """An RFC 3161 TSA endpoint: HTTPS, no credentials, query or fragment.

    The pinned C2PA pair (c2pa-python 0.38.3 / native 0.91.11) sends the
    timestamp request from its own HTTP client with bundled public roots and
    no hook for request headers, so an authenticating TSA cannot be used and
    secrets must never be placed in the URL. See production onboarding.
    """
    from urllib.parse import urlsplit
    if not isinstance(value, str) or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError('TSA URL must be text without whitespace')
    url = urlsplit(value)
    # Development identities may use a local offline test TSA over loopback
    # HTTP (RFC 3161 tokens are signed; the qualification suite uses OpenSSL).
    # Production identities always require HTTPS.
    loopback = url.hostname in {'127.0.0.1', '::1', 'localhost'}
    scheme_ok = url.scheme == 'https' or (allow_loopback_http and url.scheme == 'http' and loopback)
    if not scheme_ok or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('TSA URL must be HTTPS without credentials, query or fragment; '
                         'the pinned C2PA runtime cannot authenticate to a TSA')
    _ = url.port  # reject invalid port syntax
    return value


def create_development_identity(directory: Path) -> None:
    """Create new test keys, never overwrite credentials or fetch a certificate."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    now = datetime.now(timezone.utc)
    root_key = ec.generate_private_key(ec.SECP256R1())
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Ariadne Mark development CA")])
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Ariadne Mark development signer")])

    def base(subject, issuer, public_key):
        return (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
                .public_key(public_key).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=30)))

    root = (base(root_name, root_name, root_key.public_key())
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    leaf = (base(leaf_name, root_name, leaf_key.public_key())
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    pem = serialization.Encoding.PEM
    key_bytes = leaf_key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    fd = os.open(directory / "private.key", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(key_bytes)
    (directory / "certificate.pem").write_bytes(leaf.public_bytes(pem) + root.public_bytes(pem))
    (directory / "trust.pem").write_bytes(root.public_bytes(pem))
    (directory / "identity.json").write_text(json.dumps({"development": True, "expires_at": (now + timedelta(days=30)).isoformat()}))


def validate_trust_roots(path: Path):
    """Fail before serving on missing/empty/malformed public root configuration."""
    data = Path(path).read_bytes()
    if not data.strip() or b'PRIVATE KEY' in data:
        raise ValueError('Trust roots must contain public certificates only')
    from cryptography import x509
    roots = x509.load_pem_x509_certificates(data)
    if not roots:
        raise ValueError('Trust roots contain no certificates')
    now = datetime.now(timezone.utc)
    for root in roots:
        if 'Ariadne Mark development' in root.subject.rfc4514_string() or 'Ariadne Mark development' in root.issuer.rfc4514_string():
            raise ValueError('Development roots are not allowed in production')
        if not root.not_valid_before_utc <= now <= root.not_valid_after_utc:
            raise ValueError('Production trust root is not currently valid')
        try:
            constraints = root.extensions.get_extension_for_class(x509.BasicConstraints).value
        except x509.ExtensionNotFound as exc:
            raise ValueError('Production trust roots require CA basic constraints') from exc
        if not constraints.ca:
            raise ValueError('Production trust root must be a CA certificate')
        try:
            if not root.extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign:
                raise ValueError('Production trust root cannot sign certificates')
        except x509.ExtensionNotFound:
            pass
    return len(roots)


def validate_provider_chain(certificate: Path, trust_roots: Path) -> None:
    """Offline path validation to operator roots, with a C2PA signer EKU policy.

    Uses cryptography's path builder (signatures, constraints, validity, depth),
    not a hand-written issuer-name/signature walk. Override its TLS-specific
    SAN/EKU requirements: this is a document/claim signer, not a TLS client.
    Does not establish C2PA enrollment, revocation status or public trust.
    """
    from cryptography import x509
    from cryptography.x509.verification import (
        PolicyBuilder, Store, ExtensionPolicy, Criticality, VerificationError,
    )
    from cryptography.x509.oid import ExtendedKeyUsageOID, ObjectIdentifier
    accepted = {ExtendedKeyUsageOID.EMAIL_PROTECTION, ObjectIdentifier('1.3.6.1.5.5.7.3.36'),
                ObjectIdentifier('1.3.6.1.4.1.62558.2.1')}
    forbidden = {ExtendedKeyUsageOID.TIME_STAMPING, ExtendedKeyUsageOID.OCSP_SIGNING,
                 ExtendedKeyUsageOID.ANY_EXTENDED_KEY_USAGE}

    def signer_eku(policy, cert, extension):
        values = set(extension)
        if not values.intersection(accepted) or values.intersection(forbidden):
            raise ValueError('Provider certificate requires a C2PA signing EKU without timestamp/OCSP/any-purpose use')

    def ca_eku(policy, cert, extension):
        if extension is not None:
            values = set(extension)
            if not values.intersection(accepted | {ExtendedKeyUsageOID.ANY_EXTENDED_KEY_USAGE}):
                raise ValueError('CA EKU does not permit C2PA signing')

    chain = x509.load_pem_x509_certificates(Path(certificate).read_bytes())
    roots = x509.load_pem_x509_certificates(Path(trust_roots).read_bytes())
    if not chain or not roots:
        raise ValueError('Provider certificate chain and configured issuer roots are required')
    ee = (ExtensionPolicy.webpki_defaults_ee()
          .may_be_present(x509.SubjectAlternativeName, Criticality.AGNOSTIC, None)
          .require_present(x509.ExtendedKeyUsage, Criticality.AGNOSTIC, signer_eku))
    ca = (ExtensionPolicy.webpki_defaults_ca()
          .may_be_present(x509.ExtendedKeyUsage, Criticality.AGNOSTIC, ca_eku))
    try:
        verifier = (PolicyBuilder().store(Store(roots)).time(datetime.now(timezone.utc))
                    .max_chain_depth(8).extension_policies(ca_policy=ca, ee_policy=ee)
                    .build_client_verifier())
        verifier.verify(chain[0], chain[1:])
    except (VerificationError, ValueError) as exc:
        raise ValueError('Provider certificate chain/EKU is not valid against configured issuer roots: ' + str(exc)) from exc


def context(trust_anchors: Path | None = None, *, tsa_trust_anchors: Path | None = None):
    from ariadne_mark.c2pa_runtime import require_runtime
    require_runtime()
    import c2pa
    settings = {
        "verify": {"verify_after_reading": True, "verify_after_sign": True, "verify_trust": True,
                   "remote_manifest_fetch": False, "ocsp_fetch": False, "verify_timestamp_trust": True},
        "builder": {"thumbnail": {"enabled": False}},
    }
    anchors = []
    if trust_anchors:
        anchors.append({"trust_anchors": Path(trust_anchors).read_text(),
                        "trust_kind": "manifest", "trust_uri": "ariadne:operator:manifest"})
    if tsa_trust_anchors:
        anchors.append({"trust_anchors": Path(tsa_trust_anchors).read_text(),
                        "trust_kind": "tsa", "trust_uri": "ariadne:operator:tsa"})
    if anchors:
        # Native overlays merge these lists with built-in roots. A signer root
        # is never silently promoted to timestamp-authority trust.
        settings["trust"] = {"anchors": anchors}
    return c2pa.Context.from_dict(settings)


def sign_file(source: Path, destination: Path, record: ProvenanceRecord, token: str,
              identity: SigningIdentity, *, parent: Path | None = None, disclosure: bool = False,
              audio: str = "none", algorithm: str = "adobe.trustmark.Q.bch5",
              payload_format: str = "ariadne-v1", watermark_profile: str | None = None, tsa_trust_anchors: Path | None = None) -> bytes:
    record.validate_for_export()
    from ariadne_mark.c2pa_runtime import require_runtime
    require_runtime()
    import c2pa
    if not identity.development and not identity.timestamp_url:
        raise AriadneError("Production signing requires an explicit TSA URL; development fixtures use allow_dev")
    action = "c2pa.created" if record.action.value == "created" else "c2pa.edited"
    source_type = (DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA if record.action.value == "created"
                   else DigitalSourceType.COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA)
    manifest = {
        "claim_generator_info": [{"name": "Ariadne Mark", "version": sdk_version()}],
        "title": "AI-generated media" if record.action.value == "created" else "AI-altered media",
        "format": MIME[source.suffix.lower()],
        "assertions": [
            {"label": "c2pa.actions", "data": {"actions": [{"action": action,
                "digitalSourceType": source_type.value,
                "when": record.to_dict()["created_at"],
                "softwareAgent": {"name": record.system.name, "version": record.system.version}}]}},
            {"label": ASSERTION, "data": {"record": record.to_dict(), "watermark": {
                "algorithm": algorithm, "format": payload_format, "token": token,
                **({"profile": watermark_profile} if watermark_profile else {})},
                "development_identity": identity.development, "visible_disclosure": disclosure,
                "audio": audio}},
        ],
    }
    from ariadne_mark.softbinding import assertion
    manifest['assertions'].append(assertion(algorithm, token))
    manifest['assertions'][0]['data']['actions'].append({'action': 'c2pa.watermarked.bound'})
    import contextlib
    with contextlib.ExitStack() as stack:
        tsa_url = identity.timestamp_url
        if identity.timestamp_credential_file is not None:
            # The pinned native signer accepts only a URL; a loopback relay
            # adds the credential for this one signing operation.
            from ariadne_mark.signing.tsa_relay import TimestampRelay
            relay = stack.enter_context(TimestampRelay(identity.timestamp_url, identity.timestamp_credential_file,
                                                       timeout=identity.timestamp_timeout,
                                                       ca_bundle=identity.timestamp_ca_bundle))
            tsa_url = relay.url
        return _sign_with(c2pa, manifest, source, destination, identity, parent, tsa_url, tsa_trust_anchors)


def _sign_with(c2pa, manifest, source, destination, identity, parent, tsa_url, tsa_trust_anchors):
    info = c2pa.C2paSignerInfo("es256", identity.certificate.read_bytes(), identity.private_key.read_bytes(), tsa_url)
    with context(tsa_trust_anchors=tsa_trust_anchors) as ctx, c2pa.Signer.from_info(info) as signer, c2pa.Builder(manifest, ctx) as builder:
        if parent is not None:
            builder.set_intent(c2pa.C2paBuilderIntent.EDIT)
            with parent.open("rb") as stream:
                builder.add_ingredient({"title": "Source material", "relationship": "parentOf"}, MIME[parent.suffix.lower()], stream)
        existed = Path(destination).exists()
        try:
            return builder.sign_file(source, destination, signer)
        except Exception as exc:
            # The native builder can leave its output behind after a failed
            # timestamp call (observed: TSA timeout). Never leave an unsigned or
            # partially signed file at a path this call created.
            if not existed:
                Path(destination).unlink(missing_ok=True)
            # Native errors can echo endpoints or local paths; keep the cause
            # chained for local debugging, never in the message (receipts,
            # CLI JSON, worker IPC). Nothing has been published at this point.
            stage = 'with a timestamp authority' if identity.timestamp_url else 'locally'
            raise AriadneError(f'C2PA signing {stage} failed; no output published') from exc


def read_manifest(path: Path, *, trust_anchors: Path | None = None, tsa_trust_anchors: Path | None = None) -> dict:
    import c2pa
    # Remote manifests and OCSP fetching are disabled: reading an upload cannot
    # trigger arbitrary network requests through its embedded URLs.
    with context(trust_anchors, tsa_trust_anchors=tsa_trust_anchors) as ctx, c2pa.Reader(path, context=ctx) as reader:
        return json.loads(reader.json())


def read_recovered_manifest(store: bytes, asset: Path, *, trust_anchors: Path | None = None, tsa_trust_anchors: Path | None = None) -> dict:
    """Validate a retrieved manifest store against a supplied asset, offline.

    Modified assets may have a data-hash mismatch even when a recoverable
    watermark and a valid signature remain. Never suppress that mismatch.
    """
    import c2pa
    from ariadne_mark.softbinding import MAX_MANIFEST_BYTES
    if not isinstance(store, bytes) or not 0 < len(store) <= MAX_MANIFEST_BYTES:
        raise ValueError('Invalid manifest store size')
    with context(trust_anchors, tsa_trust_anchors=tsa_trust_anchors) as ctx, Path(asset).open('rb') as stream:
        with c2pa.Reader(MIME[Path(asset).suffix.lower()], stream, manifest_data=store, context=ctx) as reader:
            return json.loads(reader.json())
