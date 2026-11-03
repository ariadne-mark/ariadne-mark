"""Optional visible disclosure; applications still own their surrounding UI."""


def apply_label(image, *, altered: bool = False):
    from PIL import ImageDraw, ImageFont
    result = image.copy()
    label = "AI-altered" if altered else "AI-generated"
    size = max(14, min(40, result.width // 30))
    font = ImageFont.load_default(size=size)
    draw = ImageDraw.Draw(result)
    box = draw.textbbox((0, 0), label, font=font)
    pad = max(8, size // 2)
    width, height = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    y = result.height - height
    draw.rectangle((0, y, width, result.height), fill="black")
    draw.text((pad, y + pad - box[1]), label, font=font, fill="white")
    return result
