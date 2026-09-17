"""Configuration management: .env loading, user config file, key/model resolution."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR = Path.home() / ".imageto3d"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Keys allowed in the "defaults" section of the config file.
# ``api_key`` is handled as a top-level entry, not as a default.
DEFAULT_KEYS = ("subdivision_level", "file_format", "model", "auto_process", "draft")

DEFAULT_MODEL = "doubao-seed3d-2-0-260328"

BOOLEAN_KEYS = ("auto_process", "draft")


def load_dotenv_file() -> None:
    """
    Load .env files into os.environ (values already present in the
    environment are never overridden).

    Looks in the project root first, then in the current working directory,
    so it works regardless of where the command is run from.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency declared in pyproject
        return

    project_env = Path(__file__).resolve().parent.parent / ".env"
    if project_env.exists():
        load_dotenv(project_env)
    load_dotenv(Path.cwd() / ".env")


def load_config() -> Dict[str, Any]:
    """Load the user config file. Returns {} when missing or corrupt."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Atomically write the user config file with owner-only permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(tmp_file, 0o600)
    except OSError:
        pass  # Windows and some filesystems do not support chmod
    tmp_file.replace(CONFIG_FILE)


def update_config(key: str, value: Any) -> None:
    """Set (or remove, when value is None) a top-level config entry."""
    config = load_config()
    if value is None:
        config.pop(key, None)
    else:
        config[key] = value
    save_config(config)


def resolve_api_key(explicit: Optional[str] = None) -> str:
    """
    Resolve the API key with priority:
    explicit argument > ARK_API_KEY env var > ~/.imageto3d/config.json.

    Raises:
        ValueError: If no key can be found.
    """
    load_dotenv_file()
    key = explicit or os.environ.get("ARK_API_KEY")
    if key:
        return key

    key = load_config().get("api_key")
    if key:
        return str(key)

    raise ValueError(
        "API key is required. Set ARK_API_KEY, run 'imageto3d config set-key <key>', "
        "or pass --api-key."
    )


def resolve_model(explicit: Optional[str] = None) -> str:
    """
    Resolve the model name with priority:
    explicit argument > IMAGETO3D_MODEL env var > config defaults > built-in default.
    """
    load_dotenv_file()
    model = explicit or os.environ.get("IMAGETO3D_MODEL")
    if model:
        return model
    model = load_config().get("defaults", {}).get("model")
    return str(model) if model else DEFAULT_MODEL


def get_defaults() -> Dict[str, Any]:
    """Return the validated 'defaults' section of the config file."""
    defaults = load_config().get("defaults")
    if not isinstance(defaults, dict):
        return {}
    return {k: v for k, v in defaults.items() if k in DEFAULT_KEYS}


def mask_secret(secret: str, visible: int = 6) -> str:
    """Mask a secret for safe display."""
    secret = str(secret)
    if len(secret) <= 12:
        return "***"
    return f"{secret[:visible]}...{secret[-4:]}"
