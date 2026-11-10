"""Explicit 8-bit SDR conversions for both export and watermark read-back.

PyAV 16 only configures swscale details when matrix/range arguments differ.
An RGB endpoint has no YCbCr matrix: use a different, immaterial matrix there
so even full-range YUV gets the requested coefficients (PyAV issue #2149).
ACCURATE_RND + FULL_CHR_H_INT avoid the default SIMD truncation bias. These
are upstream libswscale flags, not a brightness correction to model output.
"""
from dataclasses import dataclass

from ariadne_mark.errors import UnsupportedMedia

# SWS_BILINEAR | SWS_ACCURATE_RND | SWS_FULL_CHR_H_INT
SCALE_FLAGS = 2 | 0x40000 | 0x2000
_MATRIX = {1: 1, 4: 4, 5: 5, 6: 5, 7: 7}


@dataclass(frozen=True)
class ColorPolicy:
    matrix: int
    range: int

    @classmethod
    def from_frame(cls, frame):
        if {component.bits for component in frame.format.components} != {8}:
            raise UnsupportedMedia('Color conversion requires 8-bit SDR frames')
        matrix = int(frame.colorspace)
        if matrix == 2:  # FFmpeg's historical SD matrix fallback, now explicit.
            matrix = 6
        if matrix not in _MATRIX:
            raise UnsupportedMedia("Unsupported SDR color matrix; convert explicitly to BT.709 or BT.601")
        color_range = int(frame.color_range)
        if not color_range:
            color_range = 2 if frame.format.name.startswith('yuvj') else 1
        if color_range not in {1, 2}:
            raise UnsupportedMedia("Unsupported color range")
        return cls(matrix, color_range)

    def tag(self, frame):
        frame.colorspace, frame.color_range = self.matrix, self.range
        return frame

    def check(self, frame):
        if self.from_frame(frame) != self:
            raise UnsupportedMedia("Changing color matrix/range within a stream requires explicit normalization")


class ColorConverter:
    def __init__(self, policy):
        from av.video.reformatter import VideoReformatter
        self.policy = policy
        self.reader, self.writer = VideoReformatter(), VideoReformatter()

    def image(self, frame):
        self.policy.check(frame)
        matrix = _MATRIX[self.policy.matrix]
        rgb = self.reader.reformat(frame, format='rgb24',
            src_colorspace=matrix, dst_colorspace=5 if matrix != 5 else 1,
            src_color_range=self.policy.range, dst_color_range=2,
            interpolation=SCALE_FLAGS)
        return rgb.to_image()

    def frame(self, image):
        import av
        matrix = _MATRIX[self.policy.matrix]
        rgb = av.VideoFrame.from_image(image.convert('RGB'))
        frame = self.writer.reformat(rgb, format='yuv420p',
            src_colorspace=5 if matrix != 5 else 1, dst_colorspace=matrix,
            src_color_range=2, dst_color_range=self.policy.range,
            interpolation=SCALE_FLAGS)
        return self.policy.tag(frame)

    def encoder_frame(self, frame):
        """Give x264 its actual pixel format, preventing implicit range conversion.

        yuvj420p and yuv420p have identical 8-bit plane layouts. Copy code
        values rather than asking swscale to convert deprecated full-range
        yuvj420p into limited-range yuv420p. The stream/frame range remains
        explicit. Other chroma layouts use the already-qualified converter.
        No NumPy, PIL or model inference on the common 4:2:0 bypass path.
        """
        self.policy.check(frame)
        if frame.format.name == 'yuv420p':
            return self.policy.tag(frame)
        if frame.format.name == 'yuvj420p':
            import av
            output = av.VideoFrame(frame.width, frame.height, 'yuv420p')
            for source, target in zip(frame.planes, output.planes):
                if source.line_size == target.line_size and source.buffer_size == target.buffer_size:
                    target.update(source)
                else:
                    # Decoder and allocator row strides need not match. Never
                    # copy padding into visible pixels or leave output padding uninitialized.
                    target.update(bytes(target.buffer_size))
                    before, after = memoryview(source), memoryview(target)
                    for row in range(target.height):
                        start, dest = row * source.line_size, row * target.line_size
                        after[dest:dest + target.width] = before[start:start + target.width]
            output.pts, output.time_base = frame.pts, frame.time_base
            return self.policy.tag(output)
        output = self.frame(self.image(frame))
        output.pts, output.time_base = frame.pts, frame.time_base
        return output


def frame_image(frame):
    """Decode using the same explicit matrix/range as the exporter."""
    return ColorConverter(ColorPolicy.from_frame(frame)).image(frame)
