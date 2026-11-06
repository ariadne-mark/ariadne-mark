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

    @classmethod
    def from_directory(cls, directory: Path, *, allow_dev: bool = False, timestamp_url=None):
        directory = Path(directory)
        config = json.loads((directory / "identity.json").read_text())
        if config.get("development") is not False and not allow_dev:
            raise AriadneError("Development identity requires explicit allow_dev / --allow-dev")
        return cls(directory / "certificate.pem", directory / "private.key", config.get("development") is not False, timestamp_url)


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


def context(trust_anchors: Path | None = None, *, tsa_trust_anchors: Path | None = None):
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
    info = c2pa.C2paSignerInfo("es256", identity.certificate.read_bytes(), identity.private_key.read_bytes(), identity.timestamp_url)
    with context(tsa_trust_anchors=tsa_trust_anchors) as ctx, c2pa.Signer.from_info(info) as signer, c2pa.Builder(manifest, ctx) as builder:
        if parent is not None:
            builder.set_intent(c2pa.C2paBuilderIntent.EDIT)
            with parent.open("rb") as stream:
                builder.add_ingredient({"title": "Source material", "relationship": "parentOf"}, MIME[parent.suffix.lower()], stream)
        return builder.sign_file(source, destination, signer)


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
