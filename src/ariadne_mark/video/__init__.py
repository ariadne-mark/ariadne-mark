"""CPU H.264 export with timestamp-preserving frame processing and audio remux."""

from fractions import Fraction
import json
from pathlib import Path
import subprocess

from ariadne_mark.errors import AriadneError, UnsupportedMedia


def probe(path: Path) -> dict:
    try:
        process = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                                  "-show_streams", "-show_format", "-of", "json", str(path)],
                                 capture_output=True, text=True, timeout=30, check=True)
        data = json.loads(process.stdout)
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        raise UnsupportedMedia("Cannot inspect video; FFmpeg/ffprobe and a readable MP4 are required") from exc
    videos = [s for s in data.get("streams", []) if s["codec_type"] == "video"]
    audios = [s for s in data.get("streams", []) if s["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) > 1 or len(data.get("streams", [])) != len(videos) + len(audios):
        raise UnsupportedMedia("Support is limited to one video stream and at most one audio stream")
    video = videos[0]
    duration = float(data.get("format", {}).get("duration", 0))
    width, height = video.get("width", 0), video.get("height", 0)
    if not 0 < duration <= 300 or min(width, height) < 256 or max(width, height) > 1920:
        raise UnsupportedMedia("Video must be at most 5 minutes and 256–1920 pixels per dimension")
    if width % 2 or height % 2:
        raise UnsupportedMedia("H.264 export requires even frame dimensions")
    if video.get("sample_aspect_ratio", "1:1") not in {"1:1", "0:1", "N/A"}:
        raise UnsupportedMedia("Anamorphic pixels require explicit square-pixel conversion")
    if video.get("field_order", "progressive") not in {"progressive", "unknown"}:
        raise UnsupportedMedia("Interlaced video requires explicit deinterlacing")
    if video.get("color_transfer") in {"smpte2084", "arib-std-b67"} or "10" in video.get("pix_fmt", ""):
        raise UnsupportedMedia("HDR / high-bit-depth video is not supported; explicit SDR conversion is required")
    if audios and audios[0].get("codec_name") != "aac":
        raise UnsupportedMedia("Only AAC audio can be preserved in this MP4 exporter")
    rotation = int(next((s.get("rotation", 0) for s in video.get("side_data_list", []) if "rotation" in s), video.get("tags", {}).get("rotate", 0)))
    if rotation % 90:
        raise UnsupportedMedia("Only multiples of 90-degree rotation are supported")
    return {"width": width, "height": height, "duration": duration, "rotation": rotation,
            "audio": bool(audios), "source": data}


def _orient(image, rotation: int):
    # ffprobe reports display-matrix counter-clockwise rotation.
    return image.rotate(rotation, expand=True) if rotation % 360 else image


def encode_video(source: Path, destination: Path, marker, token: str, *, visible=False, altered=False) -> dict:
    import av
    from ariadne_mark.disclosure import apply_label

    info = probe(source)
    silent = destination.with_name("frames.mp4")
    frames = 0
    first_time = None
    last_pts = None
    with av.open(str(source), options={"protocol_whitelist": "file,pipe"}) as incoming, av.open(str(silent), "w") as outgoing:
        stream = incoming.streams.video[0]
        rate = stream.average_rate or Fraction(24, 1)
        encoded = outgoing.add_stream("libx264", rate=rate)
        encoded.width, encoded.height = (info["height"], info["width"]) if info["rotation"] % 180 else (info["width"], info["height"])
        encoded.pix_fmt = "yuv420p"
        encoded.time_base = stream.time_base
        encoded.codec_context.time_base = stream.time_base
        encoded.codec_context.thread_count = 2
        encoded.options = {"crf": "18", "preset": "fast", "bf": "0"}
        for frame in incoming.decode(stream):
            if frame.pts is None or frame.time_base is None:
                raise UnsupportedMedia("Video frames require timestamps")
            if last_pts is not None and frame.pts <= last_pts:
                raise UnsupportedMedia("Non-monotonic video timestamps")
            last_pts = frame.pts
            if first_time is None:
                first_time = frame.pts * frame.time_base
            if frames >= 18000:
                raise UnsupportedMedia("Video exceeds 18000-frame limit")
            image = _orient(frame.to_image(), info["rotation"])
            if visible:
                image = apply_label(image, altered=altered)
            # Video is always re-encoded; reserve a modest signal margin for H.264.
            image = marker.encode(image, token, strength=1.5)
            output = av.VideoFrame.from_image(image)
            output.pts = frame.pts
            output.time_base = frame.time_base
            for packet in encoded.encode(output):
                outgoing.mux(packet)
            frames += 1
        for packet in encoded.encode():
            outgoing.mux(packet)
    if not frames:
        raise UnsupportedMedia("Video contains no decodable frames")
    # Preserve packet timing and AAC bytes; avoid shortening either stream silently.
    command = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-copyts", "-protocol_whitelist", "file,pipe", "-i", str(silent)]
    if info["audio"]:
        command += ["-protocol_whitelist", "file,pipe", "-i", str(source), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        command += ["-map", "0:v:0"]
    command += ["-c", "copy", "-map_metadata", "-1", "-metadata:s:v:0", "rotate=0", "-movflags", "+faststart", str(destination)]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)
    except (subprocess.SubprocessError, OSError) as exc:
        raise AriadneError("Video audio/container remux failed") from exc
    final = probe(destination)
    if abs(final["duration"] - info["duration"]) > max(.15, 1 / float(rate)):
        raise AriadneError("Output duration differs from input beyond tolerance")
    if final["audio"] != info["audio"]:
        raise AriadneError("Output audio preservation failed")
    return {"frames_encoded": frames, "duration": final["duration"], "audio": "preserved_aac" if info["audio"] else "none",
            "rotation_normalized": info["rotation"], "width": final["width"], "height": final["height"],
            "watermark_strength": 1.5, "h264_crf": 18}


def sample_frames(path: Path, *, samples: int = 5):
    """Decode a bounded sample; never claim the sample verifies every frame."""
    import av
    info = probe(path)
    with av.open(str(path), options={"protocol_whitelist": "file,pipe"}) as container:
        stream = container.streams.video[0]
        seen = set()
        start = float((stream.start_time or 0) * stream.time_base)
        for i in range(samples):
            target = start + max(0, info["duration"] - .1) * i / max(samples - 1, 1)
            container.seek(int(target / float(stream.time_base)), stream=stream, backward=True)
            chosen = None
            for count, frame in enumerate(container.decode(stream)):
                chosen = frame
                if frame.time >= target or count >= 600:
                    break
            if chosen is not None and chosen.pts not in seen:
                seen.add(chosen.pts)
                yield _orient(chosen.to_image(), info["rotation"]), chosen.time
