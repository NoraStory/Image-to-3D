"""Command line interface for Image to 3D conversion."""

import argparse
import csv
import io
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import __version__
from .client import (
    MAX_IMAGES,
    VALID_FORMATS,
    VALID_LEVELS,
    Seed3DClient,
)
from .config import DEFAULT_MODEL, get_defaults, load_dotenv_file, mask_secret, resolve_api_key
from .utils import (
    auto_process_image,
    check_remote_image,
    download_file,
    encode_image_to_base64,
    get_image_info,
    unwrap_model_archive,
    validate_image,
)

# --------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------- #

def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _add_api_key_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api-key",
        default=argparse.SUPPRESS,
        help="API key (defaults to ARK_API_KEY env var, then 'imageto3d config')",
    )


def _add_model_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model",
        default=None,
        help=f"Model name (defaults to IMAGETO3D_MODEL, config, or {DEFAULT_MODEL})",
    )


def _make_client(args: argparse.Namespace) -> Seed3DClient:
    key = resolve_api_key(getattr(args, "api_key", None))
    return Seed3DClient(api_key=key, model=getattr(args, "model", None))


def _progress_printer(task: Any) -> None:
    print(f"  ... status: {task.status}", flush=True)


def _load_local_image(path: str, auto_process: bool) -> str:
    """Validate, optionally auto-fix, and encode a local image to base64."""
    source = path
    processed = False

    if auto_process:
        # Fix first, then validate: validate_image() must never run before
        # auto_process_image(), otherwise there is nothing left to auto-fix.
        source, processed = auto_process_image(path)
        if processed:
            print(f"  auto-processed {path} -> {source}")

    try:
        validate_image(source)
        info = get_image_info(source)
        print(f"  loaded: {path} ({info['width']}x{info['height']}px, {info['size_mb']:.2f}MB)")
        return encode_image_to_base64(source)
    finally:
        if processed and source != path and Path(source).exists():
            Path(source).unlink(missing_ok=True)


def _load_sources(args: argparse.Namespace) -> List[str]:
    """Collect image sources from --image-file and --image-url arguments."""
    sources: List[str] = []
    for path in args.image_file or []:
        sources.append(_load_local_image(path, args.auto_process))
    for url in args.image_url or []:
        ok, err, _ = check_remote_image(url)
        if not ok:
            raise ValueError(f"URL check failed for {url}: {err}")
        sources.append(url)
    if not sources:
        raise ValueError("Provide at least one --image-file or --image-url")
    if len(sources) > MAX_IMAGES:
        raise ValueError(f"Up to {MAX_IMAGES} images are supported (multi-view input)")
    return sources


def _plan_batch_outputs(
    files: List[Path], output_dir: Path, file_format: str
) -> List[Tuple[Path, Path]]:
    """Assign collision-free output paths for a batch of images."""
    grouped: Dict[Path, List[Path]] = {}
    for f in files:
        out = output_dir / f"{f.stem}.{file_format}"
        grouped.setdefault(out, []).append(f)

    planned: List[Tuple[Path, Path]] = []
    for out, group in grouped.items():
        if len(group) == 1:
            planned.append((group[0], out))
            continue
        for index, f in enumerate(group, start=1):
            source_suffix = f.suffix.lstrip(".") or "img"
            unique_name = f"{f.parent.name}__{f.stem}__{source_suffix}__{index}.{file_format}"
            planned.append((f, output_dir / unique_name))
    return planned


def _resolve_output_arg(
    output: Optional[str], index: int, variants: int, file_format: str
) -> Optional[str]:
    if not output:
        return None
    path = Path(output)
    if not path.suffix:
        path = path.with_suffix(f".{file_format}")
    if variants <= 1:
        return str(path)
    stem, suffix = path.stem, path.suffix
    return str(path.with_name(f"{stem}__v{index + 1}{suffix}"))


# --------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------- #

def create_command(args: argparse.Namespace) -> int:
    """Handle the 'create' command."""
    try:
        if args.draft_task_id and (args.image_file or args.image_url):
            raise ValueError("--draft-task-id cannot be combined with --image-file/--image-url")
        if args.output and not args.wait:
            raise ValueError("--output requires --wait")

        client = _make_client(args)

        if args.draft_task_id:
            sources: List[str] = []
        else:
            sources = _load_sources(args)

        variants = args.variants
        created: List[Tuple[Any, Optional[str]]] = []
        print(f"\nCreating {variants} task(s) ...")
        print(f"  Model: {client.model}")
        print(f"  Subdivision level: {args.subdivision_level}")
        print(f"  Output format: {args.file_format}")
        if args.draft:
            print("  Draft mode: yes")

        for i in range(variants):
            seed = None
            if args.seed is not None:
                seed = args.seed + i
            elif variants > 1:
                seed = i

            result = client.create_task(
                image_urls=sources or None,
                subdivision_level=args.subdivision_level,
                file_format=args.file_format,
                draft=args.draft,
                draft_task_id=args.draft_task_id,
                seed=seed,
                callback_url=args.callback_url,
                priority=args.priority,
                execution_expires_after=args.expires_after,
                timeout=args.request_timeout,
            )
            print(f"  ✓ Task created: {result.id}")
            created.append(
                (result, _resolve_output_arg(args.output, i, variants, args.file_format))
            )

        if not args.wait:
            print("\nUse 'imageto3d get <task_id>' to check status later.")
            return 0

        # Wait for each task (sequential to keep output readable)
        failed = False
        for result, output in created:
            print(f"\nWaiting for task {result.id} (timeout: {args.timeout}s)...")
            try:
                final = client.wait_for_completion(
                    task_id=result.id,
                    timeout=args.timeout,
                    poll_interval=args.poll_interval,
                    progress_callback=_progress_printer,
                )
                print(f"  ✓ Task {result.id} completed!")
                print(f"  Output URL: {final.content.file_url}")
                if output:
                    print(f"  Downloading to {output}...")
                    download_file(final.content.file_url, output)
                    output = str(unwrap_model_archive(output, args.file_format))
                    print(f"  ✓ Downloaded: {output}")
            except TimeoutError as e:
                print(f"  ✗ {e}", file=sys.stderr)
                print(f"  Use 'imageto3d get {result.id}' to check status later")
                failed = True
            except RuntimeError as e:
                print(f"  ✗ {e}", file=sys.stderr)
                failed = True

        return 1 if failed else 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def get_command(args: argparse.Namespace) -> int:
    """Handle the 'get' command."""
    try:
        client = _make_client(args)
        result = client.get_task(args.task_id)

        if args.json:
            data = {
                "id": result.id,
                "status": result.status,
                "model": result.model,
                "created_at": result.created_at,
            }
            if result.status == "succeeded":
                data["output_url"] = getattr(result.content, "file_url", None)
            elif result.status in ("failed", "cancelled"):
                err = getattr(result, "error", None)
                data["error"] = getattr(err, "message", None) or (
                    str(err) if err else "unknown error"
                )
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"Task ID: {result.id}")
            print(f"Status: {result.status}")
            print(f"Model: {result.model}")
            print(f"Created: {result.created_at}")

        if result.status == "succeeded":
            output_url = getattr(result.content, "file_url", None)
            if not args.json and output_url:
                print(f"Output URL: {output_url}")
            if args.output and output_url:
                print(f"\nDownloading to {args.output}...")
                download_file(output_url, args.output)
                output_format = Path(args.output).suffix.lstrip(".").lower() or "glb"
                args.output = str(unwrap_model_archive(args.output, output_format))
                print(f"✓ Downloaded successfully to {args.output}!")
        elif result.status in ("failed", "cancelled"):
            err = getattr(result, "error", None)
            message = getattr(err, "message", None) or (str(err) if err else "unknown error")
            print(f"Error: {message}")

        return 1 if result.status in ("failed", "cancelled") else 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def list_command(args: argparse.Namespace) -> int:
    """Handle the 'list' command."""
    try:
        client = _make_client(args)
        result = client.list_tasks(
            page_num=args.page,
            page_size=args.size,
            status=args.status,
        )

        tasks = list(result.items or [])
        total = result.total

        if args.format == "json":
            payload = {
                "total": total,
                "page": args.page,
                "tasks": [
                    {
                        "id": t.id,
                        "status": t.status,
                        "created_at": t.created_at,
                        "output_url": (
                            getattr(t.content, "file_url", None)
                            if t.status == "succeeded" and getattr(t, "content", None)
                            else None
                        ),
                    }
                    for t in tasks
                ],
            }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
        elif args.format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["task_id", "status", "created_at", "output_url"])
            for t in tasks:
                writer.writerow(
                    [
                        t.id,
                        t.status,
                        t.created_at,
                        (
                            getattr(t.content, "file_url", None)
                            if t.status == "succeeded" and getattr(t, "content", None)
                            else ""
                        ),
                    ]
                )
            text = buf.getvalue()
        else:
            lines = [f"Total tasks: {total}", f"Page {args.page} (showing {len(tasks)} tasks)", ""]
            if not tasks:
                lines.append("No tasks found.")
            for t in tasks:
                lines.append(f"- Task ID: {t.id}")
                lines.append(f"  Status: {t.status}")
                lines.append(f"  Created: {t.created_at}")
                if t.status == "succeeded" and getattr(t, "content", None):
                    lines.append(f"  Output: {getattr(t.content, 'file_url', None)}")
                lines.append("")
            text = "\n".join(lines)

        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"✓ Written to {args.output}")
        else:
            print(text)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def delete_command(args: argparse.Namespace) -> int:
    """Handle the 'delete' command."""
    try:
        client = _make_client(args)
        client.delete_task(args.task_id)
        print(f"✓ Task {args.task_id} deleted successfully")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def batch_command(args: argparse.Namespace) -> int:
    """Handle the 'batch' command: convert a directory of images."""
    try:
        client = _make_client(args)

        exts = tuple(args.ext) if args.ext else (".jpg", ".jpeg", ".png", ".webp", ".bmp")
        files: List[Path] = []
        for item in args.images:
            p = Path(item)
            if p.is_dir():
                iterator = p.rglob("*") if args.recursive else p.glob("*")
                files.extend(f for f in iterator if f.is_file() and f.suffix.lower() in exts)
            elif p.is_file():
                files.append(p)
            else:
                print(f"skip missing path: {item}", file=sys.stderr)

        files = sorted(set(files))
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        todo: List[Tuple[Path, Path]] = []
        for f, out in _plan_batch_outputs(files, output_dir, args.file_format):
            if args.skip_existing and out.exists() and out.stat().st_size > 0:
                print(f"⏭  skip {f.name} (output already exists)")
                continue
            todo.append((f, out))

        if not todo:
            print("Nothing to do.")
            return 0

        print(f"Batch conversion: {len(todo)} image(s), concurrency={args.concurrency}")
        print(f"Output directory: {output_dir}")
        print("=" * 60)

        results: Dict[str, List[Tuple[Path, str]]] = {"ok": [], "fail": []}
        lock = threading.Lock()

        def worker(item: Tuple[Path, Path]) -> None:
            f, out = item
            processed_path: Optional[Path] = None
            try:
                source = str(f)
                if args.auto_process:
                    source, processed = auto_process_image(str(f))
                    if processed:
                        processed_path = Path(source)
                try:
                    validate_image(source)
                    image_source = encode_image_to_base64(source)
                finally:
                    if processed_path is not None and processed_path.exists():
                        processed_path.unlink(missing_ok=True)

                result = client.create_task(
                    image_urls=[image_source],
                    subdivision_level=args.subdivision_level,
                    file_format=args.file_format,
                    draft=args.draft,
                    timeout=args.request_timeout,
                )
                final = client.wait_for_completion(
                    task_id=result.id,
                    timeout=args.timeout,
                    poll_interval=args.poll_interval,
                )
                download_file(final.content.file_url, str(out))
                out = unwrap_model_archive(out, args.file_format)
                with lock:
                    results["ok"].append((f, str(out)))
                print(f"✓ {f.name} -> {out} ({result.id})")
            except Exception as e:
                with lock:
                    results["fail"].append((f, str(e)))
                print(f"✗ {f.name}: {e}", file=sys.stderr)

        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            list(executor.map(worker, todo))

        print("=" * 60)
        print(f"Done. Succeeded: {len(results['ok'])}, failed: {len(results['fail'])}")
        if results["fail"]:
            print("\nFailures:")
            for f, err in results["fail"]:
                print(f"  - {f.name}: {err}")
        return 0 if not results["fail"] else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def config_command(args: argparse.Namespace) -> int:
    """Handle the 'config' command."""
    from .config import (
        BOOLEAN_KEYS,
        CONFIG_FILE,
        load_config,
        resolve_model,
        save_config,
        update_config,
    )

    try:
        if args.config_action == "set-key":
            if not args.key or not args.key.strip():
                print("Error: API key must not be empty", file=sys.stderr)
                return 1
            update_config("api_key", args.key.strip())
            print(f"✓ API key saved to {CONFIG_FILE}")
            return 0

        if args.config_action == "unset-key":
            update_config("api_key", None)
            print(f"✓ API key removed from {CONFIG_FILE}")
            return 0

        if args.config_action == "set":
            if args.key_name not in ("subdivision_level", "file_format", "model", "auto_process", "draft"):
                print(
                    f"Error: unknown default '{args.key_name}'. "
                    f"Allowed: subdivision_level, file_format, model, auto_process, draft",
                    file=sys.stderr,
                )
                return 1

            value: Any = args.value
            if args.key_name == "subdivision_level" and value not in VALID_LEVELS:
                print(f"Error: subdivision_level must be one of {VALID_LEVELS}", file=sys.stderr)
                return 1
            if args.key_name == "file_format" and value not in VALID_FORMATS:
                print(f"Error: file_format must be one of {VALID_FORMATS}", file=sys.stderr)
                return 1
            if args.key_name == "model" and not str(value).strip():
                print("Error: model must not be empty", file=sys.stderr)
                return 1
            if args.key_name in BOOLEAN_KEYS:
                if str(value).lower() in ("1", "true", "yes", "on"):
                    value = True
                elif str(value).lower() in ("0", "false", "no", "off"):
                    value = False
                else:
                    print(f"Error: {args.key_name} must be true or false", file=sys.stderr)
                    return 1

            config = load_config()
            config.setdefault("defaults", {})[args.key_name] = value
            save_config(config)
            print(f"✓ default {args.key_name} = {value}")
            return 0

        if args.config_action == "unset":
            config = load_config()
            if "defaults" in config:
                config["defaults"].pop(args.key_name, None)
                if not config["defaults"]:
                    config.pop("defaults", None)
                save_config(config)
            print(f"✓ default '{args.key_name}' removed")
            return 0

        if args.config_action == "path":
            print(CONFIG_FILE)
            return 0

        # default: show current configuration
        config = load_config()
        print(f"Config file: {CONFIG_FILE}")
        api_key = config.get("api_key")
        if api_key:
            print(f"API key:    {mask_secret(api_key)} (stored)")
        else:
            print("API key:    not stored (using ARK_API_KEY/.env if set)")
        defaults = config.get("defaults") or {}
        print(f"Defaults:   {defaults or 'none'}")
        print(f"Model:      {resolve_model()}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def web_command(args: argparse.Namespace) -> int:
    """Handle the 'web' command."""
    try:
        from .web import run_server

        print(f"Starting web server on http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop")
        run_server(host=args.host, port=args.port, debug=args.debug)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# --------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imageto3d",
        description="Image to 3D conversion tool using Doubao-Seed3D-2.0",
    )
    parser.add_argument("--version", action="version", version=f"imageto3d {__version__}")
    parser.add_argument(
        "--api-key",
        help="API key (defaults to ARK_API_KEY env var, then 'imageto3d config')",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- create ----
    create_parser = subparsers.add_parser("create", help="Create a new 3D generation task")
    _add_api_key_arg(create_parser)
    _add_model_arg(create_parser)
    create_parser.add_argument(
        "--image-file",
        action="append",
        metavar="PATH",
        help="Local image file (repeatable, up to 4 for multi-view input)",
    )
    create_parser.add_argument(
        "--image-url",
        action="append",
        metavar="URL",
        help="Image URL (repeatable, up to 4 for multi-view input)",
    )
    create_parser.add_argument(
        "--subdivision-level",
        choices=VALID_LEVELS,
        default=None,
        help="Mesh quality (default: medium or configured default)",
    )
    create_parser.add_argument(
        "--file-format",
        choices=VALID_FORMATS,
        default=None,
        help="Output 3D file format (default: glb or configured default)",
    )
    create_parser.add_argument(
        "--draft",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Create a cheap fast draft",
    )
    create_parser.add_argument(
        "--draft-task-id",
        metavar="ID",
        help="Refine an existing draft task (instead of providing images)",
    )
    create_parser.add_argument("--seed", type=int, help="Fixed seed for reproducibility")
    create_parser.add_argument(
        "--variants",
        type=_positive_int,
        default=1,
        metavar="N",
        help="Create N variants with different seeds (default: 1)",
    )
    create_parser.add_argument(
        "--callback-url",
        metavar="URL",
        help="Webhook URL called when the task finishes",
    )
    create_parser.add_argument("--priority", type=int, help="Task queue priority")
    create_parser.add_argument(
        "--expires-after",
        type=int,
        metavar="SECONDS",
        help="Give up queued execution after N seconds",
    )
    create_parser.add_argument(
        "--request-timeout",
        type=float,
        default=120.0,
        help="HTTP request timeout in seconds (default: 120)",
    )
    create_parser.add_argument(
        "--auto-process",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Automatically resize/crop/recompress images that exceed API limits",
    )
    create_parser.add_argument("--wait", action="store_true", help="Wait for task completion")
    create_parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=300,
        help="Timeout in seconds when waiting (default: 300)",
    )
    create_parser.add_argument(
        "--poll-interval",
        type=_positive_int,
        default=5,
        help="Polling interval in seconds (default: 5)",
    )
    create_parser.add_argument(
        "--output",
        help="Download output file to this path (requires --wait)",
    )
    create_parser.set_defaults(func=create_command)

    # ---- get ----
    get_parser = subparsers.add_parser("get", help="Get task status and details")
    _add_api_key_arg(get_parser)
    get_parser.add_argument("task_id", help="Task ID to query")
    get_parser.add_argument("--output", help="Download output file to this path")
    get_parser.add_argument("--json", action="store_true", help="Print result as JSON")
    get_parser.set_defaults(func=get_command)

    # ---- list ----
    list_parser = subparsers.add_parser("list", help="List tasks")
    _add_api_key_arg(list_parser)
    list_parser.add_argument("--page", type=_positive_int, default=1, help="Page number (default: 1)")
    list_parser.add_argument("--size", type=_positive_int, default=10, help="Page size (default: 10)")
    list_parser.add_argument(
        "--status",
        choices=["queued", "running", "succeeded", "failed", "cancelled"],
        help="Filter by status",
    )
    list_parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    list_parser.add_argument("--output", help="Write the result to a file")
    list_parser.set_defaults(func=list_command)

    # ---- delete ----
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    _add_api_key_arg(delete_parser)
    delete_parser.add_argument("task_id", help="Task ID to delete")
    delete_parser.set_defaults(func=delete_command)

    # ---- batch ----
    batch_parser = subparsers.add_parser(
        "batch", help="Batch-convert images from files or directories"
    )
    _add_api_key_arg(batch_parser)
    _add_model_arg(batch_parser)
    batch_parser.add_argument(
        "images", nargs="+", metavar="PATH", help="Image files or directories to convert"
    )
    batch_parser.add_argument(
        "--ext",
        action="append",
        metavar=".EXT",
        help="Only scan these extensions in directories (default: jpg jpeg png webp bmp)",
    )
    batch_parser.add_argument("--recursive", action="store_true", help="Scan directories recursively")
    batch_parser.add_argument(
        "--output-dir", default="outputs", help="Output directory (default: outputs)"
    )
    batch_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip images whose non-empty output file already exists (resume support)",
    )
    batch_parser.add_argument(
        "--concurrency", type=_positive_int, default=2, help="Parallel tasks (default: 2)"
    )
    batch_parser.add_argument(
        "--subdivision-level", choices=VALID_LEVELS, default=None, help="Mesh quality"
    )
    batch_parser.add_argument("--file-format", choices=VALID_FORMATS, default=None, help="Output format")
    batch_parser.add_argument(
        "--draft",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate drafts (cheap)",
    )
    batch_parser.add_argument(
        "--auto-process",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Automatically resize/crop/recompress images that exceed API limits",
    )
    batch_parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=600,
        help="Per-task wait timeout in seconds (default: 600)",
    )
    batch_parser.add_argument(
        "--poll-interval",
        type=_positive_int,
        default=5,
        help="Polling interval in seconds (default: 5)",
    )
    batch_parser.add_argument(
        "--request-timeout",
        type=float,
        default=120.0,
        help="HTTP request timeout in seconds (default: 120)",
    )
    batch_parser.set_defaults(func=batch_command)

    # ---- config ----
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_action")

    set_key = config_sub.add_parser("set-key", help="Store the API key in the user config file")
    set_key.add_argument("key", help="API key to store")

    config_sub.add_parser("unset-key", help="Remove the stored API key")

    set_default = config_sub.add_parser("set", help="Set a default option")
    set_default.add_argument("key_name", help="subdivision_level | file_format | model | auto_process | draft")
    set_default.add_argument("value", help="Value to store")

    unset_default = config_sub.add_parser("unset", help="Remove a default option")
    unset_default.add_argument("key_name", help="Default option to remove")

    config_sub.add_parser("path", help="Print the config file path")
    config_parser.set_defaults(func=config_command)

    # ---- web ----
    web_parser = subparsers.add_parser("web", help="Start web interface")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    web_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode (NOT safe for public networks)",
    )
    web_parser.set_defaults(func=web_command)

    return parser


def main() -> int:
    """Main entry point for the CLI."""
    load_dotenv_file()

    parser = build_parser()
    args = parser.parse_args()

    if not getattr(args, "command", None):
        parser.print_help()
        return 1

    # Apply configured defaults. CLI flags always win: argparse supplies
    # ``None`` only when the user did not pass a --flag/--no-flag pair.
    if args.command in ("create", "batch"):
        defaults = get_defaults()
        if args.subdivision_level is None and "subdivision_level" in defaults:
            args.subdivision_level = defaults["subdivision_level"]
        if args.file_format is None and "file_format" in defaults:
            args.file_format = defaults["file_format"]
        if args.draft is None and "draft" in defaults:
            args.draft = str(defaults["draft"]).lower() in ("1", "true", "yes", "on")
        if args.auto_process is None and "auto_process" in defaults:
            args.auto_process = str(defaults["auto_process"]).lower() in ("1", "true", "yes", "on")
        args.subdivision_level = args.subdivision_level or "medium"
        args.file_format = args.file_format or "glb"
        args.draft = bool(args.draft)
        args.auto_process = bool(args.auto_process)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
