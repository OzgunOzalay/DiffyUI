#!/bin/bash
# Local setup script for ComfyUI with DWI analysis nodes

set -e

echo "=== Setting up ComfyUI locally ==="

# Check if ComfyUI directory exists
if [ ! -d "ComfyUI" ]; then
    echo "Cloning ComfyUI repository..."
    git clone https://github.com/comfyanonymous/ComfyUI.git
    echo "Removing ComfyUI .git (single project repo — no nested repos)..."
    rm -rf ComfyUI/.git
else
    echo "ComfyUI directory already exists, skipping clone..."
fi

# Supplement ComfyUI with modules excluded from git tracking but required at runtime.
# These are core ComfyUI Python modules (no large model files) needed to boot the server.
SUPPLEMENT_DIRS=(
    "comfy/text_encoders"
    "comfy/ldm/models"
    "comfy/sd1_tokenizer"
)
MISSING=()
for d in "${SUPPLEMENT_DIRS[@]}"; do
    [ ! -d "ComfyUI/$d" ] && MISSING+=("$d")
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Fetching missing ComfyUI core modules from upstream (sparse clone)..."
    TMPDIR_COMFY=$(mktemp -d)
    git clone --depth=1 --filter=blob:none --sparse \
        https://github.com/comfyanonymous/ComfyUI.git "$TMPDIR_COMFY"
    (cd "$TMPDIR_COMFY" && git sparse-checkout set "${MISSING[@]}")
    for d in "${MISSING[@]}"; do
        DEST="ComfyUI/$(dirname "$d")"
        mkdir -p "$DEST"
        cp -r "$TMPDIR_COMFY/$d" "$DEST/"
        echo "  ✓ Fetched $d"
    done
    rm -rf "$TMPDIR_COMFY"
    echo "Core modules restored."
fi

cd ComfyUI

# Use venv if present (create one if you want: python -m venv venv)
if [ -f "venv/bin/activate" ]; then
    echo "Activating ComfyUI venv..."
    source venv/bin/activate
fi

# Install ComfyUI requirements
echo "Installing ComfyUI requirements..."
pip install -r requirements.txt

# Install additional dependencies for DWI nodes (including Brain 3D Viewer)
echo "Installing DWI node dependencies..."
pip install "nibabel>=5.0.0" "numpy>=1.24.0" "pybids>=0.16.0" matplotlib Pillow "scikit-image>=0.19.0"

# Create symlink to custom nodes
cd ..
mkdir -p ComfyUI/custom_nodes
if [ ! -L "ComfyUI/custom_nodes/dwi_nodes" ] || [ "$(readlink ComfyUI/custom_nodes/dwi_nodes)" != "$(pwd)/custom_nodes/dwi_nodes" ]; then
    echo "Creating symlink to custom nodes..."
    ln -sf "$(pwd)/custom_nodes/dwi_nodes" ComfyUI/custom_nodes/dwi_nodes
    ln -sf "$(pwd)/custom_nodes/utils" ComfyUI/custom_nodes/utils
fi

# Verify neuroimaging tools are available
echo ""
echo "=== Verifying neuroimaging tools ==="
echo "Checking FSL..."
if command -v bet &> /dev/null && command -v fslroi &> /dev/null; then
    echo "✓ FSL is available"
else
    echo "✗ FSL not found in PATH"
fi

echo "Checking MRtrix3..."
if command -v mrconvert &> /dev/null && command -v dwidenoise &> /dev/null; then
    echo "✓ MRtrix3 is available"
else
    echo "✗ MRtrix3 not found in PATH"
fi

echo "Checking ANTs..."
if command -v N4BiasFieldCorrection &> /dev/null; then
    echo "✓ ANTs is available"
else
    echo "✗ ANTs not found in PATH"
fi

echo ""
echo "=== Setup complete! ==="
echo "To start ComfyUI, run:"
echo "  cd ComfyUI && source venv/bin/activate && python main.py --listen 0.0.0.0 --port 8188"
echo "(Omit 'source venv/bin/activate' if you don't use a venv.)"
echo ""
echo "Then open http://localhost:8188 in your browser"
