"""Tests for image utilities and URL safety checks."""

import os
from unittest.mock import MagicMock, patch

from PIL import Image

from imageto3d.utils import (
    auto_process_image,
    check_remote_image,
    unwrap_model_archive,
    validate_image,
    validate_public_http_url,
)


def _make_image(path, width=100, height=300, color="red"):
    Image.new("RGB", (width, height), color=color).save(path)
    return path


def test_auto_process_crops_out_of_range_image(tmp_path):
    src = _make_image(str(tmp_path / "tall.png"), width=100, height=300)
    processed, changed = auto_process_image(src)

    assert changed is True
    validate_image(processed)
    with Image.open(processed) as img:
        width, height = img.size
    assert 0.39 <= width / height <= 2.5
    assert processed != src


def test_auto_process_scales_custom_pixel_limit(tmp_path):
    src = _make_image(str(tmp_path / "big.png"), width=200, height=100)
    processed, changed = auto_process_image(src, max_pixels=10000)

    assert changed is True
    with Image.open(processed) as img:
        assert img.width * img.height <= 10000


def test_validate_public_url_blocks_private_addresses():
    ok, err = validate_public_http_url("http://127.0.0.1/admin")
    assert ok is False
    assert "non-public" in err or "public" in err

    ok, err = validate_public_http_url("http://169.254.169.254/latest/meta-data")
    assert ok is False

    ok, err = validate_public_http_url("file:///etc/passwd")
    assert ok is False


def test_check_remote_image_rejects_invalid_dimensions():
    import io

    too_tall = Image.new("RGB", (100, 300), "red")
    buf = io.BytesIO()
    too_tall.save(buf, format="PNG")
    body = buf.getvalue()

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"Content-Type": "image/png", "Content-Length": str(len(body))}
    fake_response.iter_content.return_value = [bytes(body)]
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("imageto3d.utils.validate_public_http_url", return_value=(True, None)):
        with patch("imageto3d.utils.requests.get", return_value=fake_response):
            ok, err, _ = check_remote_image("http://public.example/image.png")

    assert ok is False
    assert "Aspect ratio" in err


def test_validate_image_accepts_valid_png(tmp_path):
    src = _make_image(str(tmp_path / "ok.png"), width=800, height=600)
    validate_image(src)


def test_cleanup_processed_files():
    # Processing returns a different path only when a fix was actually needed.
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        Image.new("RGB", (100, 300), "red").save(path)
        processed, changed = auto_process_image(path)
        assert changed is True
        assert os.path.exists(processed)
        os.unlink(processed)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_unwrap_glb_zip_archive(tmp_path):
    import zipfile

    archive = tmp_path / "model.glb"
    real_glb = b"glTF-fake-binary-content"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("pbr/mesh_textured_pbr.glb", real_glb)

    result = unwrap_model_archive(str(archive), "glb")
    assert result.suffix == ".glb"
    assert result.read_bytes() == real_glb


def test_unwrap_leaves_usdz_zip_untouched(tmp_path):
    import zipfile

    archive = tmp_path / "model.usdz"
    original = b"usdz-zip-content"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("payload.bin", original)

    result = unwrap_model_archive(str(archive), "usdz")
    assert result == archive
    assert archive.read_bytes().startswith(b"PK")
