"""Flask web application for Image to 3D conversion."""

import atexit
import hmac
import json
import logging
import os
import queue
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Optional

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    stream_with_context,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from . import __version__
from .client import MAX_IMAGES, VALID_FORMATS, VALID_LEVELS, Seed3DClient
from .config import load_dotenv_file, resolve_api_key, resolve_model
from .storage import TaskStore
from .utils import (
    MAX_FILE_SIZE,
    auto_process_image,
    check_remote_image,
    download_file,
    encode_image_to_base64,
    get_image_info,
    unwrap_model_archive,
    validate_image,
    validate_public_http_url,
)

load_dotenv_file()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("imageto3d.web")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
OUTPUT_FOLDER = PROJECT_ROOT / "outputs"
DB_PATH = PROJECT_ROOT / "data" / "tasks.db"

for folder in (UPLOAD_FOLDER, OUTPUT_FOLDER):
    folder.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)
# Allow 4 images per request with multipart overhead
app.config["MAX_CONTENT_LENGTH"] = (MAX_FILE_SIZE + 2 * 1024 * 1024) * MAX_IMAGES
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["OUTPUT_FOLDER"] = str(OUTPUT_FOLDER)

store = TaskStore(DB_PATH)
atexit.register(store.close)

# Formats the web UI can render in the browser.
PREVIEW_FORMATS = ("glb", "usdz", "obj")


def _mime_for_format(file_format: str) -> str:
    return {
        "glb": "model/gltf-binary",
        "usdz": "model/vnd.usdz+zip",
        "obj": "text/plain",
    }.get(file_format, "application/octet-stream")

# --------------------------------------------------------------------- #
# security configuration
# --------------------------------------------------------------------- #

WEB_TOKEN = os.environ.get("WEB_TOKEN") or None
TRUST_PROXY_HEADERS = os.environ.get("IMAGETO3D_TRUST_PROXY_HEADERS") == "1"
ALLOW_INSECURE_HOST = os.environ.get("IMAGETO3D_ALLOW_INSECURE_HOST") == "1"

RATE_WINDOW_SECONDS = 60
GLOBAL_RATE_LIMIT = 120
CONVERT_RATE_LIMIT = 10
_RATE_MAX_ENTRIES = 8192

_rate_windows: Dict[str, Deque[float]] = {}
_rate_lock = threading.Lock()


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if TRUST_PROXY_HEADERS and forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _evict_stale_rate_entries(now: float) -> None:
    if len(_rate_windows) <= _RATE_MAX_ENTRIES:
        return
    stale = [
        ip
        for ip, window in list(_rate_windows.items())
        if not window or now - window[-1] > RATE_WINDOW_SECONDS
    ]
    for ip in stale[:1024]:
        _rate_windows.pop(ip, None)
    while len(_rate_windows) > _RATE_MAX_ENTRIES:
        _rate_windows.pop(next(iter(_rate_windows)), None)


def _rate_ok(ip: str, limit: int) -> bool:
    now = time.monotonic()
    with _rate_lock:
        window = _rate_windows.setdefault(ip, deque())
        while window and now - window[0] > RATE_WINDOW_SECONDS:
            window.popleft()
        if len(window) >= limit:
            _evict_stale_rate_entries(now)
            return False
        window.append(now)
        _evict_stale_rate_entries(now)
    return True


def _check_token() -> Optional[Response]:
    if not WEB_TOKEN:
        return None
    provided = request.headers.get("X-Auth-Token")
    if not provided:
        auth = request.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            provided = auth[7:].strip()
    if not provided:
        # SameSite=Strict cookie set by the web UI; lets <a>, <model-viewer>
        # and three.js fetch the protected same-origin model/download URLs.
        provided = request.cookies.get("imageto3d_token")
    if not provided or not hmac.compare_digest(provided, WEB_TOKEN):
        return jsonify({"error": "unauthorized"}), 401
    return None


def _check_csrf() -> Optional[Response]:
    """Protect browser-simple requests when optional token auth is disabled."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if WEB_TOKEN:
        return None  # a custom auth header already forces a CORS preflight
    if request.path == "/api/callback":
        return None  # called by the external API service, not by browsers
    if request.headers.get("X-Requested-With", "").lower() == "xmlhttprequest":
        return None
    return jsonify({"error": "missing X-Requested-With header (CSRF protection)"}), 403


@app.before_request
def protect_api() -> Optional[Response]:
    if not request.path.startswith("/api/"):
        return None

    # /api/config is public metadata; /api/callback must stay reachable by
    # the external API service (it only refreshes a task already in the store).
    if request.path in ("/api/config", "/api/callback"):
        pass
    else:
        auth_error = _check_token()
        if auth_error is not None:
            return auth_error

    csrf_error = _check_csrf()
    if csrf_error is not None:
        return csrf_error

    if request.path == "/api/stream":
        return None  # long-lived connection, not rate limited

    limit = CONVERT_RATE_LIMIT if request.path == "/api/convert" else GLOBAL_RATE_LIMIT
    if not _rate_ok(_client_ip(), limit):
        return jsonify({"error": "too many requests, slow down"}), 429
    return None


# --------------------------------------------------------------------- #
# client singleton
# --------------------------------------------------------------------- #

_client: Optional[Seed3DClient] = None
_client_lock = threading.Lock()


def get_client() -> Seed3DClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = Seed3DClient(api_key=resolve_api_key())
        return _client


# --------------------------------------------------------------------- #
# events (SSE broadcast) + background poller
# --------------------------------------------------------------------- #

_subscribers: set = set()
_sub_lock = threading.Lock()


def _task_payload(task: Dict[str, Any]) -> Dict[str, Any]:
    """Return a client-safe task dictionary (no internal filesystem paths)."""
    payload = {
        "id": task.get("id"),
        "status": task.get("status"),
        "subdivision_level": task.get("subdivision_level"),
        "file_format": task.get("file_format"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "image_count": task.get("image_count"),
        "image_info": task.get("image_info"),
        "output_url": task.get("output_url"),
        "draft": bool(task.get("draft")),
        "seed": task.get("seed"),
        "error": task.get("error"),
    }
    local_path = task.get("local_path")
    if local_path and Path(local_path).exists():
        payload["has_local"] = True
        payload["download_url"] = f"/api/download/{task.get('id')}"
    else:
        payload["has_local"] = False

    file_format = str(task.get("file_format") or "").lower()
    if (
        task.get("status") == "succeeded"
        and file_format in PREVIEW_FORMATS
        and (payload["has_local"] or task.get("output_url"))
    ):
        payload["preview_url"] = f"/api/preview/{task.get('id')}"
    return payload


def publish_event(event_type: str, task: Dict[str, Any]) -> None:
    payload = json.dumps({"type": event_type, "task": task}, ensure_ascii=False)
    with _sub_lock:
        subscribers = list(_subscribers)
    for q in subscribers:
        try:
            q.put_nowait(payload)
        except queue.Full:
            pass


def _auto_download(task_id: str, url: str, file_format: Optional[str]) -> Optional[Path]:
    """Download a finished model into the local cache."""
    try:
        ext = file_format if file_format in VALID_FORMATS else "glb"
        target = OUTPUT_FOLDER / f"{task_id}.{ext}"
        download_file(url, str(target), resume=True)
        target = unwrap_model_archive(target, ext)
        return target
    except Exception:
        logger.exception("auto-download failed for task %s", task_id)
        return None


def _refresh_task(task_id: str, auto_download: bool = False) -> Optional[Dict[str, Any]]:
    """Query the API for one task and persist the result in the store."""
    result = get_client().get_task(task_id)
    status = result.status
    update: Dict[str, Any] = {"status": status, "updated_at": time.time()}

    if status == "succeeded":
        content = getattr(result, "content", None)
        url = getattr(content, "file_url", None) if content else None
        if url:
            update["output_url"] = url
            stored = store.get(task_id) or {}
            if auto_download and not stored.get("local_path"):
                local = _auto_download(task_id, url, stored.get("file_format"))
                if local:
                    update["local_path"] = str(local)
    elif status in ("failed", "cancelled"):
        error = getattr(result, "error", None)
        if error:
            update["error"] = getattr(error, "message", None) or str(error)

    store.update(task_id, **update)
    refreshed = store.get(task_id)
    if refreshed:
        publish_event("task_update", _task_payload(refreshed))
    return refreshed


def _poll_loop(poll_interval: int = 5) -> None:
    """Poll unfinished tasks, update the store and auto-download results."""
    get_client()
    while True:
        try:
            for task in store.list_unfinished():
                try:
                    _refresh_task(task["id"], auto_download=True)
                    logger.debug("polled task %s", task["id"])
                except Exception:
                    logger.warning("poll failed for task %s", task["id"], exc_info=True)
                    continue
        except Exception:
            logger.exception("poller iteration failed")
        time.sleep(poll_interval)


_poller_started = False
_poller_lock = threading.Lock()


def _cleanup_uploads(max_age_seconds: int = 24 * 3600) -> None:
    try:
        now = time.time()
        for path in UPLOAD_FOLDER.glob("*"):
            if path.is_file() and now - path.stat().st_mtime > max_age_seconds:
                path.unlink(missing_ok=True)
    except OSError:
        logger.warning("upload cleanup failed", exc_info=True)


def start_background_workers(poll_interval: int = 5) -> None:
    global _poller_started
    with _poller_lock:
        if _poller_started:
            return
        _poller_started = True
    _cleanup_uploads()
    thread = threading.Thread(
        target=_poll_loop, kwargs={"poll_interval": poll_interval}, daemon=True, name="task-poller"
    )
    thread.start()


# --------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------- #

@app.route("/")
def index():
    """Render main page."""
    return render_template("index.html")


@app.route("/api/config")
def config_info():
    """Public metadata used by the frontend."""
    return jsonify(
        {
            "auth_required": bool(WEB_TOKEN),
            "csrf_header_required": not bool(WEB_TOKEN),
            "max_images": MAX_IMAGES,
            "model": resolve_model(),
            "version": __version__,
            "limits": {
                "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
                "max_pixels": "4096x4096",
                "aspect_ratio": "0.4-2.5",
            },
            "formats": list(VALID_FORMATS),
            "qualities": list(VALID_LEVELS),
        }
    )


# --------------------------------------------------------------------- #
# conversion API
# --------------------------------------------------------------------- #

@app.route("/api/convert", methods=["POST"])
def convert():
    """Handle image to 3D conversion request (1-4 images)."""
    try:
        subdivision_level = request.form.get("subdivision_level", "medium")
        file_format = request.form.get("file_format", "glb")
        if subdivision_level not in VALID_LEVELS:
            return jsonify({"error": f"subdivision_level must be one of {VALID_LEVELS}"}), 400
        if file_format not in VALID_FORMATS:
            return jsonify({"error": f"file_format must be one of {VALID_FORMATS}"}), 400

        draft = request.form.get("draft", "false").lower() in ("1", "true", "yes", "on")
        auto_process = request.form.get("auto_process", "false").lower() in ("1", "true", "yes", "on")

        seed_raw = request.form.get("seed")
        seed = int(seed_raw) if seed_raw not in (None, "") else None

        callback_url = request.form.get("callback_url") or None
        if callback_url:
            ok, err = validate_public_http_url(callback_url)
            if not ok:
                return jsonify({"error": f"invalid callback_url: {err}"}), 400

        image_sources = []
        image_info = []

        # Uploaded files (multi-view input supported)
        files = request.files.getlist("images") or request.files.getlist("image")
        files = [f for f in files if f and f.filename]
        if files:
            if len(files) > MAX_IMAGES:
                return jsonify({"error": f"Up to {MAX_IMAGES} images are supported"}), 400
            for f in files:
                filename = secure_filename(f.filename) or "upload"
                saved = UPLOAD_FOLDER / f"{uuid.uuid4().hex}_{filename}"
                f.save(str(saved))
                processed_path: Optional[Path] = None
                try:
                    source = saved
                    if auto_process:
                        processed, changed = auto_process_image(str(saved))
                        source = Path(processed)
                        if changed and source != saved:
                            processed_path = source
                    validate_image(str(source))
                    image_sources.append(encode_image_to_base64(str(source)))
                    image_info.append(get_image_info(str(source)))
                except ValueError as e:
                    return jsonify({"error": str(e)}), 400
                finally:
                    saved.unlink(missing_ok=True)
                    if processed_path is not None and processed_path.exists():
                        processed_path.unlink(missing_ok=True)

        # Remote URLs (one per line, or comma separated)
        urls_text = request.form.get("image_urls") or request.form.get("image_url") or ""
        urls = [u.strip() for u in urls_text.replace(",", "\n").splitlines() if u.strip()]
        for url in urls:
            ok, err, info = check_remote_image(url)
            if not ok:
                return jsonify({"error": f"URL check failed: {err}"}), 400
            image_sources.append(url)
            image_info.append(info or {})

        if not image_sources:
            return jsonify({"error": "No image provided"}), 400
        if len(image_sources) > MAX_IMAGES:
            return jsonify({"error": f"Up to {MAX_IMAGES} images are supported"}), 400

        result = get_client().create_task(
            image_urls=image_sources,
            subdivision_level=subdivision_level,
            file_format=file_format,
            draft=draft,
            seed=seed,
            callback_url=callback_url,
        )

        task = {
            "id": result.id,
            "status": "queued",
            "subdivision_level": subdivision_level,
            "file_format": file_format,
            "created_at": time.time(),
            "updated_at": time.time(),
            "image_count": len(image_sources),
            "image_info": image_info,
            "output_url": None,
            "local_path": None,
            "draft": 1 if draft else 0,
            "seed": seed,
            "error": None,
        }
        store.upsert(task)
        publish_event("task_created", _task_payload(task))

        return jsonify(
            {"task_id": result.id, "status": task["status"], "image_info": image_info}
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("convert failed")
        return jsonify({"error": "internal server error"}), 500


@app.route("/api/status/<task_id>", methods=["GET"])
def get_status(task_id: str):
    """Get live task status from the API (also updates the local store)."""
    if store.get(task_id) is None:
        return jsonify({"error": "task not found"}), 404

    try:
        result = get_client().get_task(task_id)

        response = {
            "task_id": result.id,
            "status": result.status,
            "model": result.model,
            "created_at": result.created_at,
        }

        update: Dict[str, Any] = {"status": result.status, "updated_at": time.time()}
        if result.status == "succeeded":
            url = getattr(result.content, "file_url", None) if getattr(result, "content", None) else None
            response["output_url"] = url
            if url:
                update["output_url"] = url
        elif result.status in ("failed", "cancelled"):
            error = getattr(result, "error", None)
            message = getattr(error, "message", None) or (str(error) if error else "unknown error")
            response["error"] = message
            update["error"] = message

        store.update(task_id, **update)
        refreshed = store.get(task_id)
        if refreshed:
            publish_event("task_update", _task_payload(refreshed))

        return jsonify(response)
    except Exception:
        logger.exception("status query failed for task %s", task_id)
        return jsonify({"error": "failed to query task status"}), 500


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    """List tasks from the persistent local store."""
    try:
        status = request.args.get("status") or None
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("size", 20))
        result = store.list(status=status, page=page, page_size=page_size)
        result["tasks"] = [_task_payload(task) for task in result["tasks"]]
        return jsonify(result)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid page or size"}), 400
    except Exception:
        logger.exception("task listing failed")
        return jsonify({"error": "failed to list tasks"}), 500


@app.route("/api/delete/<task_id>", methods=["DELETE"])
def delete_task(task_id: str):
    """Delete a task from the API, the store and the local cache."""
    task = store.get(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    try:
        get_client().delete_task(task_id)

        local_path = task.get("local_path")
        if local_path:
            try:
                Path(local_path).unlink(missing_ok=True)
            except OSError:
                logger.warning("failed to delete local cache for %s", task_id, exc_info=True)

        store.delete(task_id)
        publish_event("task_deleted", {"id": task_id})
        return jsonify({"success": True})
    except Exception:
        logger.exception("delete failed for task %s", task_id)
        return jsonify({"error": "failed to delete task"}), 500


@app.route("/api/download/<task_id>", methods=["GET"])
def download_task(task_id: str):
    """Serve the locally cached model, downloading/caching it first if needed."""
    task = store.get(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404

    file_format = str(task.get("file_format") or "glb").lower()
    local_path = task.get("local_path")

    if not (local_path and Path(local_path).exists()):
        output_url = task.get("output_url")
        if not output_url:
            return jsonify({"error": "no downloadable output yet"}), 404
        try:
            target = OUTPUT_FOLDER / f"{task_id}.{file_format}"
            download_file(output_url, str(target), resume=True)
            target = unwrap_model_archive(target, file_format)
        except Exception:
            logger.exception("download-cache failed for task %s", task_id)
            return jsonify({"error": "failed to download model"}), 502
        store.update(task_id, local_path=str(target), updated_at=time.time())
        refreshed = store.get(task_id)
        if refreshed:
            publish_event("task_update", _task_payload(refreshed))
        local_path = str(target)

    normalized = unwrap_model_archive(local_path, file_format)
    if normalized != Path(local_path):
        store.update(task_id, local_path=str(normalized), updated_at=time.time())
        local_path = str(normalized)

    return send_file(
        local_path,
        as_attachment=True,
        mimetype=_mime_for_format(file_format),
        conditional=True,
        download_name=f"{task_id}.{file_format}",
    )


@app.route("/api/preview/<task_id>", methods=["GET"])
def preview_task(task_id: str):
    """
    Serve a model inline (same-origin) so the browser viewer can render it.

    Local files are streamed directly with Range support. If only a remote
    URL is available, the model is first downloaded into the local cache.
    """
    task = store.get(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    if task.get("status") != "succeeded":
        return jsonify({"error": "task is not finished"}), 409

    file_format = str(task.get("file_format") or "glb").lower()
    if file_format not in PREVIEW_FORMATS:
        return jsonify({"error": f"no in-browser preview available for {file_format}"}), 415

    local_path = task.get("local_path")
    if not (local_path and Path(local_path).exists()):
        output_url = task.get("output_url")
        if not output_url:
            return jsonify({"error": "no model file available"}), 404
        try:
            target = OUTPUT_FOLDER / f"{task_id}.{file_format}"
            download_file(output_url, str(target), resume=True)
            target = unwrap_model_archive(target, file_format)
        except Exception:
            logger.exception("preview download failed for task %s", task_id)
            return jsonify({"error": "failed to fetch model for preview"}), 502
        store.update(task_id, local_path=str(target), updated_at=time.time())
        refreshed = store.get(task_id)
        if refreshed:
            publish_event("task_update", _task_payload(refreshed))
        local_path = str(target)

    normalized = unwrap_model_archive(local_path, file_format)
    if normalized != Path(local_path):
        store.update(task_id, local_path=str(normalized), updated_at=time.time())
        local_path = str(normalized)

    return send_file(
        local_path,
        as_attachment=False,
        mimetype=_mime_for_format(file_format),
        conditional=True,
        download_name=f"{task_id}.{file_format}",
    )


@app.route("/api/callback", methods=["POST"])
def callback():
    """
    Webhook endpoint for the API service. Parses the task id from the body
    and immediately refreshes the store from the API. Auth-exempt on purpose
    (the external service cannot send our token); harmless because it only
    refreshes tasks that already exist in the local store.
    """
    try:
        data = request.get_json(silent=True) or {}
        task_id = None
        for key in ("task_id", "id", "TaskId"):
            if isinstance(data, dict) and data.get(key):
                task_id = str(data[key])
                break
        if not task_id:
            return jsonify({"error": "no task_id in callback payload"}), 400
        if store.get(task_id) is None:
            return jsonify({"error": "task not found"}), 404

        refreshed = _refresh_task(task_id, auto_download=True)
        return jsonify({"ok": True, "status": refreshed.get("status") if refreshed else None})
    except Exception:
        logger.exception("callback failed")
        return jsonify({"error": "failed to refresh task"}), 500


# --------------------------------------------------------------------- #
# SSE stream
# --------------------------------------------------------------------- #

@app.route("/api/stream")
def stream():
    """Server-sent events: broadcasts task_created/task_update/task_deleted."""

    q: queue.Queue[str] = queue.Queue(maxsize=100)
    with _sub_lock:
        _subscribers.add(q)

    def generate():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    item = q.get(timeout=15)
                    yield f"data: {item}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with _sub_lock:
                _subscribers.discard(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------- #
# error handlers
# --------------------------------------------------------------------- #

@app.errorhandler(RequestEntityTooLarge)
def too_large(_e):
    return jsonify({"error": f"Request too large (max {MAX_IMAGES} images x 10MB)"}), 413


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found"}), 404
    return render_template("index.html"), 404


@app.errorhandler(500)
def internal_error(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "internal server error"}), 500
    return render_template("index.html"), 500


# --------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------- #

def _is_loopback_host(host: str) -> bool:
    return host.strip("[]") in ("127.0.0.1", "localhost", "::1")


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Start the web server with background workers."""
    if debug and not _is_loopback_host(host):
        raise RuntimeError(
            "Refusing to enable the Werkzeug debugger on a non-loopback address. "
            "The debugger allows remote code execution."
        )
    if not _is_loopback_host(host) and not WEB_TOKEN and not ALLOW_INSECURE_HOST:
        raise RuntimeError(
            "Refusing to bind a non-loopback address without WEB_TOKEN. "
            "Set WEB_TOKEN, or set IMAGETO3D_ALLOW_INSECURE_HOST=1 to accept the risk."
        )

    # Avoid running the poller twice under the Werkzeug reloader.
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_background_workers()
    # debug=True enables the Werkzeug debugger, which is a security risk on
    # any non-loopback interface -- kept strictly opt-in via --debug.
    app.run(host=host, port=port, debug=debug, use_reloader=debug)


def create_app() -> Flask:
    """WSGI application factory (starts the background poller once per process)."""
    start_background_workers()
    return app


if __name__ == "__main__":
    run_server(debug=False)
