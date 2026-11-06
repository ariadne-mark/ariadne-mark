"""CPU H.264 export with timestamp-preserving frame processing and audio remux."""

from contextlib import nullcontext
from fractions import Fraction
import json
from pathlib import Path
import subprocess

from ariadne_mark.errors import AriadneError, UnsupportedMedia


def probe(path: Path) -> dict:
    try:
        process = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file",
                                  "-f", "mov", "-codec_whitelist", "h264,hevc,aac", "-show_streams", "-show_format", "-of", "json", str(path)],
                                 capture_output=True, text=True, timeout=30, check=True)
        data = json.loads(process.stdout)
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        raise UnsupportedMedia("Cannot inspect video; FFmpeg/ffprobe and a readable MP4 are required") from exc
    videos = [s for s in data.get("streams", []) if s["codec_type"] == "video"]
    audios = [s for s in data.get("streams", []) if s["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) > 1 or len(data.get("streams", [])) != len(videos) + len(audios):
        raise UnsupportedMedia("Support is limited to one video stream and at most one audio stream")
    video = videos[0]
    if video.get("codec_name") not in {"h264", "hevc"}:
        raise UnsupportedMedia("MP4 input video codec must be H.264 or HEVC")
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


def validate_decoder_streams(container):
    """Check the actual PyAV decoder contexts before the first frame decode.

    The ffprobe preflight is separate; format/codec options alone are not
    relied on to constrain PyAV's bundled FFmpeg.
    """
    videos = list(container.streams.video)
    audios = list(container.streams.audio)
    if len(videos) != 1 or len(audios) > 1 or len(container.streams) != len(videos) + len(audios):
        raise UnsupportedMedia('Unexpected streams in PyAV decoder')
    if videos[0].codec_context.name not in {'h264', 'hevc'}:
        raise UnsupportedMedia('PyAV video decoder must be H.264 or HEVC')
    if audios and audios[0].codec_context.name != 'aac':
        raise UnsupportedMedia('PyAV audio decoder must be AAC')


def _orient(image, rotation: int):
    # ffprobe reports display-matrix counter-clockwise rotation.
    return image.rotate(rotation, expand=True) if rotation % 360 else image


def encode_video(source: Path, destination: Path, marker, token: str, *, visible=False, altered=False) -> dict:
    import av
    from ariadne_mark.disclosure import apply_label
    from ariadne_mark.video.color import ColorPolicy, ColorConverter

    info = probe(source)
    silent = destination.with_name("frames.mp4")
    frames = 0
    marked_frames = 0
    windows = {}
    from ariadne_mark.video.policy import WindowSelector, period_for
    profile = getattr(marker, "profile", "resilient")
    selector = WindowSelector(profile)
    last_pts = None
    decoded_end = Fraction(0)
    with (marker.encoding_session(token) if hasattr(marker, "encoding_session") else nullcontext()) as watermark_session, av.open(str(source), format="mp4", options={"protocol_whitelist": "file", "codec_whitelist": "h264,hevc,aac", "enable_drefs": "0"}) as incoming, av.open(str(silent), "w") as outgoing:
        validate_decoder_streams(incoming)
        stream = incoming.streams.video[0]
        rate = stream.average_rate or Fraction(24, 1)
        encoded = outgoing.add_stream("libx264", rate=rate)
        encoded.width, encoded.height = (info["height"], info["width"]) if info["rotation"] % 180 else (info["width"], info["height"])
        encoded.pix_fmt = "yuv420p"
        encoded.time_base = stream.time_base
        encoded.codec_context.time_base = stream.time_base
        encoded.codec_context.thread_count = 2
        encoded.options = {"crf": "18", "preset": "fast", "bf": "0"}
        converter = None
        pending = []
        durations = {}
        def mux(packet):
            if packet.pts is not None and packet.time_base is not None:
                duration = durations.pop(packet.pts * packet.time_base, None)
                if duration:
                    packet.duration = round(duration / packet.time_base)
            outgoing.mux(packet)
        def flush():
            images = [row[0] for row in pending]
            if hasattr(marker, "encode_frames"):
                marked = marker.encode_frames(images, token)
            else:
                marked = [marker.encode(image, token, strength=1.5) for image in images]
            if len(marked) != len(pending):
                raise AriadneError("Watermarker returned an incomplete frame batch")
            for image, (_, pts, time_base) in zip(marked, pending):
                output = converter.frame(image)
                output.pts, output.time_base = pts, time_base
                for packet in encoded.encode(output):
                    mux(packet)
            pending.clear()
        for frame in incoming.decode(stream):
            if frame.pts is None or frame.time_base is None:
                raise UnsupportedMedia("Video frames require timestamps")
            if last_pts is not None and frame.pts <= last_pts:
                raise UnsupportedMedia("Non-monotonic video timestamps")
            last_pts = frame.pts
            if frames >= 18000:
                raise UnsupportedMedia("Video exceeds 18000-frame limit")
            if converter is None:
                policy = ColorPolicy.from_frame(frame)
                converter = ColorConverter(policy)
                encoded.codec_context.colorspace = policy.matrix
                encoded.codec_context.color_range = policy.range
                encoded.codec_context.color_primaries = stream.codec_context.color_primaries
                encoded.codec_context.color_trc = stream.codec_context.color_trc
            converter.policy.check(frame)
            selected, window = selector.select(frame.pts * frame.time_base)
            duration = frame.duration * frame.time_base
            decoded_end = max(decoded_end, frame.pts * frame.time_base + duration)
            durations[frame.pts * frame.time_base] = duration
            if selected:
                image = _orient(converter.image(frame), info["rotation"])
                if visible:
                    image = apply_label(image, altered=altered)
                pending.append((image, frame.pts, frame.time_base))
                marked_frames += 1
                if window is not None:
                    windows[window] = windows.get(window, 0) + 1
            else:
                if pending:
                    flush()
                # Bypass PIL/RGBA/Node for unmarked frames; visible disclosure
                # and display rotation still apply to the complete export.
                output = converter.policy.tag(frame)
                if visible or info["rotation"] % 360:
                    image = _orient(converter.image(frame), info["rotation"])
                    if visible:
                        image = apply_label(image, altered=altered)
                    output = converter.frame(image)
                    output.pts, output.time_base = frame.pts, frame.time_base
                for packet in encoded.encode(output):
                    mux(packet)
            frames += 1
            if len(pending) == getattr(marker, "batch_size", 1):
                flush()
        if pending:
            flush()
        for packet in encoded.encode():
            mux(packet)
    if not frames:
        raise UnsupportedMedia("Video contains no decodable frames")
    # Preserve packet timing and AAC bytes; avoid shortening either stream silently.
    command = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-copyts", "-protocol_whitelist", "file", "-f", "mov", "-i", str(silent)]
    if info["audio"]:
        command += ["-protocol_whitelist", "file", "-f", "mov", "-i", str(source), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        command += ["-map", "0:v:0"]
    command += ["-c", "copy", "-map_metadata", "-1", "-metadata:s:v:0", "rotate=0", "-movflags", "+faststart", str(destination)]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)
    except (subprocess.SubprocessError, OSError) as exc:
        raise AriadneError("Video audio/container remux failed") from exc
    final = probe(destination)
    # Some VFR/B-frame MP4 headers under-report the final presentation end.
    # Preserve decoded frames instead of rejecting a correct, longer timeline.
    expected_duration = max(info["duration"], float(decoded_end))
    if abs(final["duration"] - expected_duration) > max(.15, 1 / float(rate)):
        raise AriadneError("Output duration differs from input beyond tolerance")
    if final["audio"] != info["audio"]:
        raise AriadneError("Output audio preservation failed")
    return {"frames_encoded": frames, "duration": final["duration"], "audio": "preserved_aac" if info["audio"] else "none",
            "rotation_normalized": info["rotation"], "width": final["width"], "height": final["height"],
            "watermark_algorithm": getattr(marker, "algorithm", "custom"),
            "batch_size": getattr(marker, "batch_size", 1), "h264_crf": 18,
            "color_pipeline": {"matrix": converter.policy.matrix, "range": converter.policy.range,
                               "rounding": "accurate_full_chroma", "version": 1},
            "profile": getattr(marker, "profile", "legacy"),
            "marked_frames": marked_frames,
            "watermark_period_s": period_for(profile),
            "watermark_window_ms": 125 if selector.period else None,
            "watermark_windows": [{"index": i, "marked_frames": n} for i, n in windows.items()],
            "watermark_stats": getattr(watermark_session, "stats", {})}


def selected_window_frames(path: Path, profile):
    """Decode scheduled export positions for read-back; no token is supplied.

    This is an export diagnostic for a known preset, not a blind detector.
    """
    import av
    from ariadne_mark.video.policy import WindowSelector
    selector = WindowSelector(profile)
    info = probe(path)
    with av.open(str(path), format="mp4", options={"protocol_whitelist": "file", "codec_whitelist": "h264,hevc,aac", "enable_drefs": "0"}) as container:
        validate_decoder_streams(container)
        last = None
        for index, frame in enumerate(container.decode(video=0)):
            if index >= 18000 or frame.pts is None or frame.time_base is None:
                raise UnsupportedMedia("Invalid or excessive video timeline during read-back")
            timestamp = frame.pts * frame.time_base
            if last is not None and timestamp <= last:
                raise UnsupportedMedia("Non-monotonic read-back timestamps")
            last = timestamp
            selected, window = selector.select(timestamp)
            if selected:
                # Defer the image conversion so callers can skip the rest of a
                # window after one independently decoded ID.
                yield frame, float(timestamp), window, info["rotation"]


def sample_frames(path: Path, *, samples: int = 5):
    """Decode a bounded sample; never claim the sample verifies every frame."""
    import av
    from ariadne_mark.video.color import frame_image
    info = probe(path)
    with av.open(str(path), format="mp4", options={"protocol_whitelist": "file", "codec_whitelist": "h264,hevc,aac", "enable_drefs": "0"}) as container:
        validate_decoder_streams(container)
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
                yield _orient(frame_image(chosen), info["rotation"]), chosen.time
