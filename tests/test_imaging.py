import io

from PIL import Image

from data.plugins.astrbot_plugin_xavier_phone.imaging import crop_to_ratio, size_for_ratio


def png(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


def dims(data):
    return Image.open(io.BytesIO(data)).size


def test_size_for_ratio():
    assert size_for_ratio("3:4") == "1024x1536"
    assert size_for_ratio("3:2") == "1536x1024"
    assert size_for_ratio("1:1") == "1024x1024"
    assert size_for_ratio("bad") == "1024x1024"


def test_crop_square_to_portrait():
    assert dims(crop_to_ratio(png(1299, 1211), "3:4")) == (908, 1211)


def test_crop_portrait_to_landscape():
    assert dims(crop_to_ratio(png(1024, 1536), "3:2")) == (1024, 683)


def test_crop_keeps_center():
    img = Image.new("RGB", (300, 100), "black")
    img.paste((255, 0, 0), (100, 0, 200, 100))  # red centre third
    buf = io.BytesIO()
    img.save(buf, "PNG")
    out = Image.open(io.BytesIO(crop_to_ratio(buf.getvalue(), "1:1")))
    assert out.size == (100, 100) and out.getpixel((50, 50)) == (255, 0, 0)


def test_already_right_or_invalid_ratio_unchanged():
    data = png(1024, 1024)
    assert crop_to_ratio(data, "1:1") == data
    assert crop_to_ratio(data, "nonsense") == data


def jpeg(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=img.getexif())
    return buf.getvalue()


def test_prepare_reference_jpeg_downscaled():
    from data.plugins.astrbot_plugin_xavier_phone.imaging import prepare_reference

    out = prepare_reference(png(3000, 4000), "3:4")
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG" and img.size == (1152, 1536)


def test_prepare_reference_applies_exif_orientation():
    from data.plugins.astrbot_plugin_xavier_phone.imaging import prepare_reference

    raw = Image.new("RGB", (400, 300), "white")  # stored landscape
    exif = raw.getexif()
    exif[0x0112] = 6  # displayed rotated 90 degrees -> portrait 300x400
    buf = io.BytesIO()
    raw.save(buf, "JPEG", exif=exif)
    assert Image.open(io.BytesIO(prepare_reference(buf.getvalue(), "3:4"))).size == (300, 400)


def test_prepare_reference_handles_cmyk():
    from data.plugins.astrbot_plugin_xavier_phone.imaging import prepare_reference

    buf = io.BytesIO()
    Image.new("CMYK", (300, 400)).save(buf, "JPEG")
    assert Image.open(io.BytesIO(prepare_reference(buf.getvalue(), "3:4"))).mode == "RGB"


def test_crop_degenerate_size_unchanged():
    data = png(1, 1)
    assert crop_to_ratio(data, "1:3") == data
