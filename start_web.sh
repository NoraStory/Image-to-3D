#!/usr/bin/env bash
# Start the Image to 3D web server (Linux / macOS)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "Virtual environment not found. Run: uv venv && uv pip install -e ." >&2
    exit 1
fi

# Load .env without overriding already-set environment variables.
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
    set +a
fi

cd "$SCRIPT_DIR"
echo "Starting Image to 3D Web Server..."
echo "Visit http://127.0.0.1:5000 in your browser"
echo ""
exec python -m imageto3d.web
