#!/bin/bash
# Start ComfyUI for DiffyUI (DWI-only mode: no image/video generation nodes)
# Uses --disable-api-nodes and, if supported, --diffyui-only for a minimal node set.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate venv from DiffyUI root (preferred), or from inside ComfyUI
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -f "$SCRIPT_DIR/ComfyUI/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/ComfyUI/venv/bin/activate"
fi

cd "$SCRIPT_DIR/ComfyUI"
exec python main.py --listen 0.0.0.0 --port 8188 --disable-api-nodes --diffyui-only "$@"
