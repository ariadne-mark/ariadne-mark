"""CPU TrustMark-Q adapter. Model provisioning is explicit, never on a request."""

import hashlib
import json
from pathlib import Path
import secrets
import threading

from ariadne_mark.errors import MissingModel, UnsupportedMedia

BITS = 61
PREFIX = 0x14D


def new_token() -> str:
    return f"{(PREFIX << 48) | secrets.randbits(48):016x}"


def valid_token(token: str) -> bool:
    return (isinstance(token, str) and len(token) == 16
            and all(c in "0123456789abcdef" for c in token)
            and int(token, 16) >> 48 == PREFIX)


def model_inventory() -> dict:
    import trustmark
    folder = Path(trustmark.__file__).parent / "models"
    result = {}
    for name in ("trustmark_Q.yaml", "encoder_Q.ckpt", "decoder_Q.ckpt"):
        path = folder / name
        if not path.is_file():
            raise MissingModel("TrustMark model is missing; run ariadne models fetch during setup")
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        result[name] = h.hexdigest()
    return result


def check_models() -> dict:
    expected = json.loads((Path(__file__).parent / "models.json").read_text())
    actual = model_inventory()
    if actual != expected:
        raise MissingModel("TrustMark model checksum mismatch; reinstall pinned models")
    return actual


def fetch_models() -> dict:
    """Explicit installation operation. May download official Adobe model files."""
    import os
    import tempfile
    import urllib.request
    import trustmark
    folder = Path(trustmark.__file__).parent / "models"
    folder.mkdir(parents=True, exist_ok=True)
    expected = json.loads((Path(__file__).parent / "models.json").read_text())
    host = "https://cai-watermark.adobe.net/watermarking/trustmark-models/"
    for name, digest in expected.items():
        path = folder / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            continue
        fd, temporary = tempfile.mkstemp(prefix=".download-", dir=folder)
        try:
            h, total = hashlib.sha256(), 0
            with os.fdopen(fd, "wb") as output, urllib.request.urlopen(host + name, timeout=60) as incoming:
                for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                    total += len(chunk)
                    if total > 512 * 1024 * 1024:
                        raise MissingModel("Model download exceeded size limit")
                    h.update(chunk)
                    output.write(chunk)
            if h.hexdigest() != digest:
                raise MissingModel("Downloaded model checksum mismatch")
            os.chmod(temporary, 0o644)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    # Verify before any model deserialization, including during first installation.
    return check_models()


class Watermarker:
    def __init__(self, *, threads: int = 2):
        import torch
        from trustmark import TrustMark
        if not 1 <= threads <= 64:
            raise ValueError("threads must be between 1 and 64")
        check_models()
        torch.set_num_threads(threads)
        self._engine = TrustMark(verbose=False, model_type="Q", device="cpu",
                                 encoding_type=TrustMark.Encoding.BCH_5,
                                 loadRemover=False, loadBBoxDetector=False)
        if self._engine.schemaCapacity() != BITS:
            raise MissingModel("Unsupported TrustMark payload capacity")
        self._lock = threading.Lock()

    def encode(self, image, token: str, *, strength: float = 1.0):
        if not valid_token(token):
            raise ValueError("Invalid Ariadne v1 token")
        if min(image.size) < 256 or max(image.size) > 4096:
            raise UnsupportedMedia("Image/frame dimensions must be 256–4096 pixels")
        if not 1 <= strength <= 2:
            raise ValueError("strength must be between 1 and 2")
        with self._lock:
            marked = self._engine.encode(image.convert("RGB"), f"{int(token, 16):061b}", MODE="binary")
        if strength != 1:
            import numpy as np
            from PIL import Image
            original = np.asarray(image.convert("RGB"), dtype=np.float32)
            residual = np.asarray(marked, dtype=np.float32) - original
            marked = Image.fromarray(np.clip(original + strength * residual, 0, 255).round().astype("uint8"))
        return marked

    def decode(self, image) -> str | None:
        if min(image.size) < 256 or max(image.size) > 4096:
            raise UnsupportedMedia("Image/frame dimensions must be 256–4096 pixels")
        with self._lock:
            bits, present, schema = self._engine.decode(image.convert("RGB"), MODE="binary")
        if not present or len(bits) != BITS or schema != 1:
            return None
        token = f"{int(bits, 2):016x}"
        return token if valid_token(token) else None
