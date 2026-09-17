"""Utility functions: image validation, preprocessing, URL checks and downloads."""

import base64
import io
import ipaddress
import os
import shutil
import socket
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageOps

# API limits for Doubao-Seed3D-2.0
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PIXELS = 4096 * 4096
MIN_ASPECT = 0.4
MAX_ASPECT = 2.5
VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
VALID_IMAGE_FORMATS = ("JPEG", "PNG", "WEBP", "BMP")

_MAX_REDIRECTS = 3
_USER_AGENT = "imageto3d/0.3"


# --------------------------------------------------------------------- #
# local image validation / preprocessing
# --------------------------------------------------------------------- #

def _check_dimensions(width: int, height: int, max_pixels: int = MAX_PIXELS) -> None:
    if width * height > max_pixels:
        raise ValueError(f"Image resolution {width}x{height} exceeds 4096x4096 limit")


def _check_aspect_ratio(
    width: int,
    height: int,
    min_aspect: float = MIN_ASPECT,
    max_aspect: float = MAX_ASPECT,
) -> None:
    ratio = width / height
    if ratio < min_aspect or ratio > max_aspect:
        raise ValueError(
            f"Aspect ratio {ratio:.2f} outside valid range ({min_aspect}, {max_aspect})"
        )


def validate_image(image_path: str) -> None:
    """
    Validate an image file against the API requirements.

    Args:
        image_path: Path to the image file.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the image doesn't meet the requirements.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    ext = Path(image_path).suffix.lower()
    if ext not in VALID_EXTS:
        raise ValueError(f"Unsupported format {ext}. Supported: {', '.join(VALID_EXTS)}")

    file_size = os.path.getsize(image_path)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"Image size {file_size / 1024 / 1024:.2f}MB exceeds 10MB limit")

    with Image.open(image_path) as img:
        img.load()  # force decoding so truncated files fail here
        width, height = img.size
        _check_dimensions(width, height)
        _check_aspect_ratio(width, height)


def get_image_info(image_path: str) -> Dict[str, Any]:
    """
    Get image file information.

    Returns:
        Dictionary with width, height, size_mb, format.
    """
    file_size = os.path.getsize(image_path)
    with Image.open(image_path) as img:
        return {
            "width": img.width,
            "height": img.height,
            "size_mb": file_size / 1024 / 1024,
            "format": img.format,
        }


def encode_image_to_base64(image_path: str) -> str:
    """Encode a local image file to a base64 data URI."""
    with open(image_path, "rb") as f:
        image_data = f.read()

    ext = Path(image_path).suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if not ext:
        with Image.open(image_path) as img:
            detected = (img.format or "").lower()
        ext = {"jpeg": "jpeg"}.get(detected, detected)

    b64_data = base64.b64encode(image_data).decode("utf-8")
    return f"data:image/{ext};base64,{b64_data}"


def _flatten_for_jpeg(img: Image.Image) -> Image.Image:
    """Convert an image with transparency to an opaque RGB image."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def _format_from_path(path: Path, fallback: Optional[str] = None) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        return "JPEG"
    if ext in ("png", "webp", "bmp"):
        return ext.upper()
    return (fallback or "JPEG").upper()


def _save_under_size_limit(
    img: Image.Image,
    output_path: Path,
    max_file_size: int = MAX_FILE_SIZE,
) -> Path:
    """Save ``img`` to ``output_path``, recompressing/resizing until small enough."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_format = _format_from_path(output_path, img.format)
    current = img
    path = output_path

    # Try the requested format first with progressively lower quality.
    if target_format in ("JPEG", "WEBP", "PNG"):
        qualities = (90, 80, 70, 60, 50)
        for quality in qualities:
            params: Dict[str, Any] = {}
            if target_format == "JPEG":
                params = {"quality": quality, "optimize": True}
            elif target_format == "WEBP":
                params = {"quality": quality, "method": 6}
            else:
                params = {"optimize": True}
            current.save(path, format=target_format, **params)
            if path.stat().st_size <= max_file_size:
                return path

    # Lossless BMP (and stubborn PNG/WEBP) files are converted to JPEG.
    if target_format != "JPEG":
        path = path.with_suffix(".jpg")
        target_format = "JPEG"
        current = _flatten_for_jpeg(img)
        for quality in (85, 75, 65, 55):
            current.save(path, format="JPEG", quality=quality, optimize=True)
            if path.stat().st_size <= max_file_size:
                current.close()
                return path

    # Last resort: progressively scale the image down.
    scale = 0.9
    working = current
    while working.width > 64 and working.height > 64:
        new_size = (max(1, int(working.width * scale)), max(1, int(working.height * scale)))
        resized = working.resize(new_size, Image.Resampling.LANCZOS)
        if working is not img:
            working.close()
        working = resized
        working.save(path, format="JPEG", quality=72, optimize=True)
        if path.stat().st_size <= max_file_size:
            if working is not img:
                working.close()
            return path
        scale *= 0.85

    if working is not img:
        working.close()
    raise ValueError(
        f"Unable to compress image below {max_file_size / 1024 / 1024:.1f}MB automatically"
    )


def auto_process_image(
    image_path: str,
    output_path: Optional[str] = None,
    max_pixels: int = MAX_PIXELS,
    min_aspect: float = MIN_ASPECT,
    max_aspect: float = MAX_ASPECT,
    max_file_size: int = MAX_FILE_SIZE,
) -> Tuple[str, bool]:
    """
    Automatically fix an image so it meets the API requirements:
    scale it down if it has too many pixels, center-crop it if the
    aspect ratio is out of range, and recompress/rescale it if the file
    is still larger than ``max_file_size``.

    Returns:
        Tuple of (path to the processed image, whether it was modified).
        The original path is returned unchanged when no fix was needed.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    src = Path(image_path)
    file_size = os.path.getsize(image_path)

    with Image.open(image_path) as opened:
        opened.load()
        img = ImageOps.exif_transpose(opened)
        if img is opened:
            img = opened.copy()

    width, height = img.size
    changed = False

    # Scale down oversized images (keep aspect ratio).
    total = width * height
    if total > max_pixels:
        scale = (max_pixels / total) ** 0.5
        new_width, new_height = max(1, int(width * scale)), max(1, int(height * scale))
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        if img is not opened:
            img.close()
        img = resized
        width, height = new_width, new_height
        changed = True

    # Center-crop out-of-range aspect ratios.
    ratio = width / height
    if ratio < min_aspect:
        new_w = int(height * min_aspect)
        left = (width - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, height))
        img.close()
        img = cropped
        changed = True
    elif ratio > max_aspect:
        new_h = int(width / max_aspect)
        top = (height - new_h) // 2
        cropped = img.crop((0, top, width, top + new_h))
        img.close()
        img = cropped
        changed = True

    # No dimension/aspect fix needed and the file is already small enough.
    if not changed and file_size <= max_file_size:
        img.close()
        return image_path, False

    if output_path is None:
        out_path = src.with_name(f"{src.stem}_processed{src.suffix}")
    else:
        out_path = Path(output_path)

    try:
        final_path = _save_under_size_limit(img, out_path, max_file_size=max_file_size)
    finally:
        img.close()

    return str(final_path), True


# --------------------------------------------------------------------- #
# remote URL preflight checks
# --------------------------------------------------------------------- #

def validate_public_http_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Reject URLs that are not http(s) or that resolve to non-global IPs.

    This is a best-effort SSRF mitigation. For high-security deployments the
    check should move to an egress proxy / allow-list.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "invalid URL"

    if parsed.scheme not in ("http", "https"):
        return False, f"unsupported URL scheme: {parsed.scheme or 'missing'}"
    if not parsed.hostname:
        return False, "URL has no hostname"
    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials are not allowed"

    host = parsed.hostname
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return False, f"could not resolve host: {host}"

    addresses = {info[4][0] for info in infos}
    if not addresses:
        return False, f"could not resolve host: {host}"

    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False, f"invalid address: {addr}"
        if not ip.is_global:
            return False, f"URL resolves to a non-public address ({addr})"
    return True, None


def check_remote_image(
    url: str,
    timeout: float = 15.0,
    max_redirects: int = _MAX_REDIRECTS,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Preflight-check a remote image URL before spending money on a task.

    Checks that the URL is public http(s), responds with HTTP 200, has an
    image/* content type, is not larger than the 10MB limit, and decodes to a
    supported image with valid dimensions and aspect ratio.

    Returns:
        Tuple of (ok, error_message, info_dict).
    """
    current_url = url
    for _ in range(max_redirects + 1):
        ok, err = validate_public_http_url(current_url)
        if not ok:
            return False, err, None

        try:
            resp = requests.get(
                current_url,
                stream=True,
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
                allow_redirects=False,
            )
        except requests.RequestException as e:
            return False, f"request failed: {e}", None

        with resp:
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    return False, "redirect without Location header", None
                current_url = urljoin(current_url, location)
                continue

            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}", None

            content_type = (resp.headers.get("Content-Type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                return False, f"not an image (Content-Type: {content_type})", None

            content_length = resp.headers.get("Content-Length")
            declared_size = None
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > MAX_FILE_SIZE:
                    return False, "exceeds 10MB limit", None

            total = 0
            body = bytearray()
            for chunk in resp.iter_content(chunk_size=65536):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    return False, "exceeds 10MB limit", None
                body.extend(chunk)

            try:
                with Image.open(io.BytesIO(bytes(body))) as img:
                    img.load()
                    detected_format = img.format
                    width, height = img.size
            except Exception:
                return False, "not a decodable image", None

            if detected_format not in VALID_IMAGE_FORMATS:
                return False, f"unsupported image format: {detected_format}", None
            try:
                _check_dimensions(width, height)
                _check_aspect_ratio(width, height)
            except ValueError as e:
                return False, str(e), None

            return True, None, {
                "size_bytes": total,
                "content_type": content_type,
                "width": width,
                "height": height,
                "format": detected_format,
            }

    return False, "too many redirects", None


# --------------------------------------------------------------------- #
# model archive unwrapping
# --------------------------------------------------------------------- #

def _is_zip_archive(path: Path) -> bool:
    try:
        return path.stat().st_size >= 4 and path.read_bytes()[:4] == b"PK\x03\x04"
    except OSError:
        return False


def unwrap_model_archive(path: str, file_format: str = "glb") -> Path:
    """
    Some Seed3D ``file_url`` downloads are delivered as ZIP containers even
    though the URL ends with the requested extension (observed for GLB).

    For GLB this replaces the ZIP with the real ``.glb`` member. For OBJ it
    extracts all members next to the archive and returns the main ``.obj``.
    Other formats (notably USDZ, which *is* a ZIP format) are left untouched.
    """
    path = Path(path)
    file_format = file_format.lower().lstrip(".")
    if file_format not in ("glb", "obj") or not _is_zip_archive(path):
        return path

    try:
        with zipfile.ZipFile(path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]

            if file_format == "glb":
                candidates = [m for m in members if m.filename.lower().endswith(".glb")]
                if not candidates:
                    return path
                # Prefer the textured mesh member produced by Seed3D.
                member = next(
                    (m for m in candidates if m.filename.lower().endswith("mesh_textured_pbr.glb")),
                    max(candidates, key=lambda m: m.file_size),
                )
                tmp = path.with_name(f"{path.name}.tmp")
                with archive.open(member) as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                try:
                    tmp.replace(path)
                    return path
                except PermissionError:
                    # The downloaded file is currently locked (for example by
                    # Blender after a failed import attempt). Keep the zip and
                    # return the extracted real GLB as a sibling file instead.
                    alternate = path.with_name(f"{path.stem}_unwrapped.glb")
                    os.replace(tmp, alternate)
                    return alternate

            # OBJ: extract the whole archive so MTL/texture references survive.
            extract_dir = path.with_name(f"{path.stem}_model")
            extract_dir.mkdir(parents=True, exist_ok=True)
            for member in members:
                rel = Path(member.filename)
                if rel.is_absolute() or ".." in rel.parts:
                    continue
                target = extract_dir.joinpath(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
            obj_files = sorted(extract_dir.rglob("*.obj"))
            return obj_files[0] if obj_files else path
    except (OSError, zipfile.BadZipFile):
        return path


# --------------------------------------------------------------------- #
# downloads
# --------------------------------------------------------------------- #

def download_file(url: str, output_path: str, resume: bool = True, timeout: float = 60.0) -> Path:
    """
    Download a file from URL to local path, optionally resuming a
    partially downloaded file with an HTTP Range request.

    Raises:
        requests.RequestException: If the download fails.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": _USER_AGENT}
    mode = "wb"
    if resume and output_path.exists() and output_path.stat().st_size > 0:
        headers["Range"] = f"bytes={output_path.stat().st_size}-"
        mode = "ab"

    with requests.get(url, stream=True, timeout=timeout, headers=headers) as resp:
        if resp.status_code == 206:
            pass  # resume accepted, append
        elif resp.status_code == 200:
            if mode == "ab":
                mode = "wb"  # server ignored the Range header, restart
        elif resp.status_code == 416 and mode == "ab":
            return output_path  # local copy is already complete
        else:
            resp.raise_for_status()

        with open(output_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    return output_path
