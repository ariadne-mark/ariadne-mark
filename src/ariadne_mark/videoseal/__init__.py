"""Pinned official VideoSeal TorchScript, CPU streaming and BCH-protected IDs."""
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import urllib.request

from ariadne_mark.errors import MissingModel, UnsupportedMedia
from .payload import Payload, ALGORITHM, FORMAT

URL = "https://dl.fbaipublicfiles.com/videoseal/y_256b_img.jit"
SHA256 = "5c7a4581c36fc6090aafdcfb3999123bae5172a4847f22e2da4e7fd1a39d1e1b"


def model_path():
    return Path(os.environ.get("ARIADNE_VIDEOSEAL_MODEL", str(Path(__file__).parent / "models/y_256b_img.jit")))


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_models():
    path = model_path()
    if not path.is_file() or _digest(path) != SHA256:
        raise MissingModel("VideoSeal missing or checksum mismatch; run ariadne models fetch --engine videoseal")
    return {"y_256b_img.jit": SHA256}


def fetch_models():
    path = model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and _digest(path) == SHA256:
        return check_models()
    fd, name = tempfile.mkstemp(prefix=".download-", dir=path.parent)
    try:
        total = 0
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(URL, timeout=60) as incoming:
            for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise MissingModel("VideoSeal download exceeded limit")
                output.write(chunk)
        if _digest(Path(name)) != SHA256:
            raise MissingModel("VideoSeal download checksum mismatch")
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    return check_models()


class VideoSealWatermarker:
    algorithm = ALGORITHM
    payload_format = FORMAT
    implementation = 'python-torch-videoseal'
    batch_size = 4

    def __init__(self, *, threads=2):
        if not 1 <= threads <= 64:
            raise ValueError("threads must be between 1 and 64")
        self.threads = threads
        self._engine = None
        self._payload = None
        self._lock = threading.RLock()

    def _load(self):
        if self._engine is None:
            import torch
            check_models()  # Never deserialize an unverified model; never download here.
            torch.set_num_threads(self.threads)
            payload = Payload()
            engine = torch.jit.load(str(model_path()), map_location="cpu").eval()
            self._payload, self._engine = payload, engine

    @staticmethod
    def _tensor(image):
        import torch
        import numpy as np
        if min(image.size) < 256 or max(image.size) > 4096:
            raise UnsupportedMedia("Frame dimensions must be 256–4096 pixels")
        return torch.from_numpy(np.array(image.convert("RGB"), copy=True)).permute(2, 0, 1).float().div_(255)

    def encode_frames(self, images, token):
        import torch
        from PIL import Image
        if not 1 <= len(images) <= self.batch_size:
            raise ValueError("VideoSeal accepts one to four frames per batch")
        with self._lock, torch.inference_mode():
            self._load()
            frames = torch.stack([self._tensor(image) for image in images])
            message = torch.tensor([self._payload.encode(token)], dtype=torch.float32)
            marked = self._engine.embed(frames, message, True)
            if marked.shape != frames.shape or not torch.isfinite(marked).all():
                raise ValueError("Invalid VideoSeal encoder output")
            return [Image.fromarray(x.clamp(0, 1).mul(255).round().byte().permute(1, 2, 0).numpy()) for x in marked]

    def decode_frames(self, frames):
        import torch
        observations, logits = [], []
        with self._lock, torch.inference_mode():
            self._load()
            for image, timestamp in frames:
                values = self._engine.detect(self._tensor(image).unsqueeze(0), False)
                if values.shape != (1, 257) or not torch.isfinite(values).all():
                    raise ValueError("Invalid VideoSeal detector output")
                row = values[0, 1:]
                logits.append(row.clone())
                decoded = self._payload.decode((row > 0).int().tolist())
                observations.append({"time": timestamp, "token": decoded["token"] if decoded else None,
                                     "corrected_bits": decoded["corrected_bits"] if decoded else None})
            aggregate = self._payload.decode((torch.stack(logits).mean(0) > 0).int().tolist()) if logits else None
        return observations, aggregate
