"""Aspect-ratio helpers: pick a request size and center-crop images."""

import io

from PIL import Image, ImageOps


def _parse_ratio(ratio: str) -> tuple[int, int] | None:
    try:
        w, h = (int(x) for x in ratio.split(":"))
    except (ValueError, AttributeError):
        return None
    return (w, h) if w > 0 and h > 0 else None


def size_for_ratio(ratio: str) -> str:
    """Return the gpt-image size closest to an aspect ratio.

    Args:
        ratio: Ratio such as "3:4".

    Returns:
        "1024x1536" for portrait, "1536x1024" for landscape, else "1024x1024".
    """
    parsed = _parse_ratio(ratio)
    if not parsed or parsed[0] == parsed[1]:
        return "1024x1024"
    return "1024x1536" if parsed[0] < parsed[1] else "1536x1024"


def crop_to_ratio(data: bytes, ratio: str) -> bytes:
    """Center-crop an image to an aspect ratio.

    Args:
        data: Encoded image bytes.
        ratio: Ratio such as "3:4"; invalid values leave the image unchanged.

    Returns:
        PNG bytes of the cropped image, or the original bytes if no crop is needed.
    """
    parsed = _parse_ratio(ratio)
    if not parsed:
        return data
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    target_w = min(w, round(h * parsed[0] / parsed[1]))
    target_h = min(h, round(w * parsed[1] / parsed[0]))
    if (target_w, target_h) == (w, h) or min(target_w, target_h) < 1:
        return data
    left, top = (w - target_w) // 2, (h - target_h) // 2
    buf = io.BytesIO()
    img.crop((left, top, left + target_w, top + target_h)).save(buf, "PNG")
    return buf.getvalue()


def prepare_reference(data: bytes, ratio: str, max_side: int = 1536) -> bytes:
    """Turn a reference photo into an upright, cropped, downscaled JPEG.

    Phone photos often rely on the EXIF orientation tag, so it is applied
    before cropping; CMYK or palette images are converted to RGB.

    Args:
        data: Encoded image bytes.
        ratio: Target ratio such as "3:4"; invalid values skip the crop.
        max_side: Longest side of the result in pixels.

    Returns:
        JPEG bytes.

    Raises:
        PIL.UnidentifiedImageError: If the bytes are not a readable image.
    """
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    img = Image.open(io.BytesIO(crop_to_ratio(buf.getvalue(), ratio)))
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()
