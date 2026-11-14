"""Export only after real watermark and C2PA read-back succeed."""

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import threading

from ariadne_mark.errors import AriadneError, UnsupportedMedia, VerificationFailed
from ariadne_mark.provenance import ProvenanceRecord
from ariadne_mark.signing import SigningIdentity, sign_file, MIME
from ariadne_mark.verification.media import open_image, verify_file, inspect_c2pa
from ariadne_mark.watermark import new_token, LazyWatermarker
from ariadne_mark.videoq import VideoWatermarker
from ariadne_mark.version import sdk_version
from ariadne_mark.video.policy import DEFAULT_PROFILE, validate_profile

MAX_OUTPUT_BYTES = 512 * 1024 * 1024

def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class SDK:
    marker: object = field(default_factory=LazyWatermarker)
    identity: SigningIdentity | None = None
    registry: object | None = None
    trust_anchors: Path | None = None

    video_marker: object | None = None
    video_profile: str = DEFAULT_PROFILE
    tsa_trust_anchors: Path | None = None
    verification_scope: str | tuple = "all"

    def __post_init__(self):
        validate_profile(self.video_profile)
        from ariadne_mark.verification.scope import normalize_scope
        normalize_scope(self.verification_scope)
        from ariadne_mark.c2pa_runtime import check_if_installed
        # Pure core construction must not be broken by another application's
        # optional C2PA installation. Export/verification and HTTP preflight
        # still require the qualified runtime before touching media.
        self.c2pa_runtime = check_if_installed() if self.identity is not None else None
        if self.video_marker is None:
            self.video_marker = VideoWatermarker(profile=self.video_profile)
        from ariadne_mark.videoseal import VideoSealWatermarker
        self._legacy_video_marker = VideoSealWatermarker()
        self._video_markers = {}
        self._video_markers_lock = threading.Lock()

    def check_runtime(self):
        from ariadne_mark.c2pa_runtime import require_runtime
        self.c2pa_runtime = require_runtime()
        return self.c2pa_runtime

    def close(self):
        for marker in [self.video_marker, *self._video_markers.values()]:
            close = getattr(marker, "close", None)
            if close:
                close()

    def _select_video_marker(self, profile):
        if profile is None:
            return self.video_marker
        validate_profile(profile)
        if getattr(self.video_marker, "profile", None) == profile:
            return self.video_marker
        if not isinstance(self.video_marker, VideoWatermarker):
            raise ValueError("A video profile override requires the built-in VideoWatermarker")
        with self._video_markers_lock:
            if profile not in self._video_markers:
                # One Node worker per SDK for every preset (ISS-12); see with_profile.
                self._video_markers[profile] = self.video_marker.with_profile(profile)
            return self._video_markers[profile]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def verify(self, path: Path) -> dict:
        self.check_runtime()
        # All new presets share a decoder. Reuse a configured export's resident
        # worker instead of loading the otherwise-unused default worker as well.
        engine = self.video_marker
        if isinstance(engine, VideoWatermarker) and engine._process is None:
            with self._video_markers_lock:
                engine = next((m for m in self._video_markers.values() if m._process is not None), engine)
        return verify_file(path, marker=self.marker, video_marker=engine, legacy_video_marker=self._legacy_video_marker, registry=self.registry, trust_anchors=self.trust_anchors, tsa_trust_anchors=self.tsa_trust_anchors, verification_scope=self.verification_scope)

    def _verify_export(self, path, engine):
        """Known local encoder controls read-back, never an input-supplied claim.

        Public ``verify`` keeps its independent operator scan. This check still
        reads actual bytes and the gate below still checks the signed ID/record,
        every sampled value and atomic publication before accepting an export.
        """
        return verify_file(path, marker=self.marker, video_marker=engine,
            legacy_video_marker=self._legacy_video_marker, registry=self.registry,
            trust_anchors=self.trust_anchors, tsa_trust_anchors=self.tsa_trust_anchors,
            verification_scope=(getattr(engine, "algorithm", "adobe.trustmark.Q.bch5"),))

    def recover_manifest(self, path: Path, destination: Path, *, token: str | None = None) -> dict:
        """Blindly recover an ID, match its signed manifest and save exact bytes.

        With several recovered IDs there is no automatic choice. ``token``
        selects one of the confirmed IDs *after* blind detection; it is never
        given to the detector, and it must have its own validated manifest.
        """
        if self.registry is None or not hasattr(self.registry, 'get_manifest'):
            raise AriadneError('A manifest-enabled registry is required')
        if token is not None:
            from ariadne_mark.watermark import valid_token
            if not valid_token(token):
                raise ValueError('Invalid Ariadne watermark ID')
        report = self.verify(path)
        recovery = report.get('recovery', {})
        if recovery.get('status') == 'per_id':
            if token is None:
                raise VerificationFailed('Multiple watermark IDs found; automatic manifest recovery is ambiguous. '
                                         'Select one confirmed ID explicitly')
            selected = next((row for row in recovery['per_id'] if row['token'] == token), None)
            if selected is None or selected.get('status') != 'found':
                raise VerificationFailed('The selected ID was not a confirmed, registered ID in this file')
            recovered = selected.get('manifest', {})
        else:
            if token is not None and token != report['watermark'].get('token'):
                raise VerificationFailed('The selected ID was not recovered from this file')
            token = report['watermark'].get('token')
            recovered = recovery.get('manifest', {})
        if (not token or recovered.get('soft_binding') != 'matched'
                or recovered.get('signature') != 'valid'):
            raise VerificationFailed('No matching manifest with a validated signature was recovered')
        bundle = self.registry.get_manifest(token=token)
        if bundle is None or bundle['sha256'] != recovered['sha256']:
            raise VerificationFailed('Recovered manifest changed during lookup')
        with Path(destination).open('xb') as stream:
            stream.write(bundle['bytes'])
            stream.flush()
            os.fsync(stream.fileno())
        return {'manifest': recovered, 'saved_to': str(destination), 'verification': report}

    def mark(self, source: Path, destination: Path, record: ProvenanceRecord, *, visible=False, audio_kind="unknown", profile=None, video_profile=None, publish_manifest=False) -> dict:
        self.check_runtime()
        if not isinstance(record, ProvenanceRecord):
            raise ValueError("record must be a ProvenanceRecord")
        record.validate_for_export()
        if type(publish_manifest) is not bool:
            raise ValueError('publish_manifest must be a boolean')
        if publish_manifest and self.registry is None:
            raise ValueError('Publishing a manifest requires a durable registry')
        if video_profile is not None:
            validate_profile(video_profile)
        profile_report = None
        if profile is not None:
            from ariadne_mark.profiles import export_settings
            profile_report = export_settings(profile, record)
            visible = visible or profile_report["sdk_options"]["visible"]
            configured_audio = profile_report["sdk_options"]["audio_kind"]
            if audio_kind != "unknown" and audio_kind != configured_audio:
                raise ValueError("audio_kind conflicts with the selected profile")
            audio_kind = configured_audio
        source, destination = Path(source).resolve(), Path(destination).resolve()
        if self.identity is None:
            raise AriadneError("A signing identity is required; unsigned export is not supported")
        if not source.is_file() or source.suffix.lower() not in MIME or destination.suffix.lower() not in MIME:
            raise UnsupportedMedia("Supported files: PNG, JPEG and MP4")
        video = source.suffix.lower() == ".mp4"
        if video != (destination.suffix.lower() == ".mp4") or record.media_kind.value != ("video" if video else "image"):
            raise UnsupportedMedia("Input, output and provenance media kinds must match")
        video_engine = self.video_marker
        if video:
            configured = profile_report["sdk_options"]["video_profile"] if profile_report else None
            if video_profile is not None and configured is not None and video_profile != configured:
                raise ValueError("video_profile conflicts with the selected product profile")
            video_engine = self._select_video_marker(video_profile or configured)
        # Never issue a mark that this SDK's own verification scope would not
        # detect (Code Sub-measure 2.1.1): refuse before touching media (P-03).
        from ariadne_mark.verification.scope import media_scope
        scheme = getattr(video_engine if video else self.marker, "algorithm", "adobe.trustmark.Q.bch5")
        if scheme not in media_scope(self.verification_scope, video=video):
            raise ValueError(f"Encoder scheme {scheme} is outside this SDK's verification_scope; "
                             "widen the scope or use an encoder its verifier covers")
        if audio_kind not in {"original", "synthetic", "unknown", "none"}:
            raise ValueError("audio_kind must be original, synthetic, unknown or none")
        receipt_path = destination.with_name(destination.name + ".receipt.json")
        if destination.exists() or receipt_path.exists() or source == destination:
            raise AriadneError("Output already exists; choose a new destination")
        parent_status = inspect_c2pa(source)
        if parent_status["status"] in {"invalid", "not_checked", "expired_credential"}:
            raise VerificationFailed("Input C2PA is invalid or could not be checked")
        if parent_status["status"] == "verified_claim" and record.action.value == "created":
            raise UnsupportedMedia("A credentialed input requires action=altered to retain its provenance history")
        parent = source if record.action.value == "altered" else None
        token = new_token()
        while self.registry is not None and self.registry.contains(token):
            token = new_token()
        start = time.monotonic()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ariadne-", dir=destination.parent) as temporary:
            work = Path(temporary)
            marked = work / ("watermarked" + destination.suffix.lower())
            signed = work / ("signed" + destination.suffix.lower())
            details = {}
            audio = "none"
            if video:
                from ariadne_mark.video import encode_video, probe
                if probe(source)["audio"] and audio_kind == "none":
                    raise UnsupportedMedia("Input contains audio; select its provenance explicitly")
                details = encode_video(source, marked, video_engine, token, visible=visible, altered=record.action.value == "altered")
                audio = audio_kind if details["audio"] != "none" else "none"
            else:
                from ariadne_mark.disclosure import apply_label
                image = open_image(source)
                if visible:
                    image = apply_label(image, altered=record.action.value == "altered")
                alpha = image.getchannel("A") if "A" in image.getbands() else None
                image = self.marker.encode(image, token)
                if alpha is not None:
                    if marked.suffix.lower() != ".png":
                        raise UnsupportedMedia("Preserving transparency requires PNG output")
                    image.putalpha(alpha)
                if marked.suffix.lower() in {".jpg", ".jpeg"}:
                    image.save(marked, "JPEG", quality=95, subsampling=0)
                else:
                    image.save(marked, "PNG")
            engine = video_engine if video else self.marker
            manifest_bytes = sign_file(marked, signed, record, token, self.identity, parent=parent, disclosure=visible, audio=audio,
                      algorithm=getattr(engine, "algorithm", "adobe.trustmark.Q.bch5"),
                      payload_format=getattr(engine, "payload_format", "ariadne-v1"),
                      watermark_profile=getattr(engine, "profile_id", None), tsa_trust_anchors=self.tsa_trust_anchors)
            economy = video and getattr(engine, "profile", None) in {"economy_5s", "economy_2s"}
            if video and isinstance(engine, VideoWatermarker):
                from ariadne_mark.verification.media import verify_video_export
                checked = verify_video_export(signed, engine,
                    [w["index"] for w in details["watermark_windows"]], trust_anchors=self.trust_anchors, tsa_trust_anchors=self.tsa_trust_anchors)
            else:
                checked = self._verify_export(signed, engine)
            samples = checked["watermark"].get("samples", [])
            if (checked["c2pa"]["status"] != "verified_claim" or checked["c2pa"].get("token") != token
                    or checked["c2pa"].get("record") != record.to_dict()
                    or checked["watermark"].get("status") != "recovered_claim"
                    or checked["watermark"].get("token") != token
                    or not samples
                    or any(row["token"] not in {None, token} for row in samples)
                    or (economy and not checked["watermark"]["export_window_readback"]["all_windows_have_id"])
                    or (not economy and any(row["token"] != token for row in samples))):
                matches = sum(row["token"] == token for row in samples)
                raise VerificationFailed(f"Final read-back failed: C2PA={checked['c2pa']['status']}, watermark={checked['watermark']['status']}, matching frames={matches}/{len(samples)}; no output published")
            if signed.stat().st_size > MAX_OUTPUT_BYTES:
                raise UnsupportedMedia("Signed export exceeds the 512 MiB verifier/export boundary")
            if not self.identity.development and checked["c2pa"].get("timestamp_trust") != "trusted":
                raise VerificationFailed("Production export requires a validated trusted timestamp")
            with signed.open("rb") as media_file:
                os.fsync(media_file.fileno())
            digest = file_hash(signed)
            manifest_bundle = None
            if isinstance(manifest_bytes, bytes) and self.registry is not None:
                from ariadne_mark.softbinding import algorithm_for, validate_match
                from ariadne_mark.signing import read_recovered_manifest
                binding_algorithm = algorithm_for(getattr(engine, "algorithm", "adobe.trustmark.Q.bch5"))
                detached = read_recovered_manifest(manifest_bytes, signed, trust_anchors=self.trust_anchors, tsa_trust_anchors=self.tsa_trust_anchors)
                manifest_id = validate_match(detached, binding_algorithm, token)
                if manifest_id != checked['c2pa'].get('manifest_id'):
                    raise VerificationFailed('Stored manifest does not match final export')
                manifest_bundle = {'id': manifest_id, 'bytes': manifest_bytes,
                                   'algorithm': binding_algorithm, 'public': publish_manifest}
            elif publish_manifest:
                raise VerificationFailed('No final manifest bytes available for publication')
            receipt = {"schema_version": 1, "sdk_version": sdk_version(), "asset_id": str(record.asset_id),
                       "token": token, "sha256": digest, "seconds": round(time.monotonic() - start, 3),
                       "development_identity": self.identity.development, "audio_kind": audio,
                       "export_settings": {"visible_disclosure": bool(visible), "audio_kind": audio},
                       "video": details, "verification": checked}
            if profile_report is not None:
                # Keep product planning separate from cryptographic media evidence.
                # Store before publication/registry commit; never patch receipts later.
                receipt["profile_assessment"] = profile_report
            receipt["registry_recorded"] = self.registry is not None
            receipt['manifest_recovery'] = {'stored': manifest_bundle is not None,
                'public': bool(manifest_bundle and publish_manifest),
                'manifest_id': manifest_bundle['id'] if manifest_bundle else None,
                'algorithm_registration': 'provisional_not_registered'}
            checked["recovery"] = {"status": "not_attempted", "reason": "export_readback_before_registry_commit"}
            # Store recovery data durably before exposing the media commit marker.
            # A crash can leave an orphan registry row/receipt, never published
            # media with a receipt claiming a missing registry insert.
            registry_added = receipt_created = media_created = False
            try:
                if self.registry is not None:
                    if manifest_bundle is None:
                        self.registry.add(token, record, digest, receipt)
                    else:
                        self.registry.add(token, record, digest, receipt, manifest_bundle)
                    registry_added = True
                pending_receipt = work / "receipt.json"
                with pending_receipt.open("x") as file:
                    json.dump(receipt, file, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
                os.link(pending_receipt, receipt_path)
                receipt_created = True
                sync_directory(destination.parent)
                # Publish media last. Its existence is the result commit marker.
                os.link(signed, destination)
                media_created = True
                sync_directory(destination.parent)
            except BaseException:
                if media_created:
                    destination.unlink(missing_ok=True)
                if receipt_created:
                    receipt_path.unlink(missing_ok=True)
                if registry_added and hasattr(self.registry, "remove"):
                    self.registry.remove(token, digest)
                raise
        return receipt
