# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

DiffyUI is a ComfyUI extension for diffusion-weighted imaging (DWI) neuroimaging analysis. It wraps FSL, MRtrix3, and ANTs command-line tools as ComfyUI nodes, enabling visual, node-based construction of DWI preprocessing pipelines with a web UI at `http://localhost:8188`.

## Commands

### Installation
```bash
./setup_local.sh
```
Clones ComfyUI, installs Python dependencies, symlinks custom nodes, and verifies that neuroimaging tools (`bet`, `fslroi`, `mrconvert`, `dwidenoise`, `N4BiasFieldCorrection`) are on PATH.

### Running
```bash
./run_diffyui.sh        # Recommended: loads only DWI nodes (--diffyui-only --disable-api-nodes)
cd ComfyUI && python main.py --listen 0.0.0.0 --port 8188  # Full ComfyUI
```

### Dependencies
```bash
pip install -r requirements.txt   # DWI node dependencies only
```

## Architecture

### Symlink Layout
`custom_nodes/` in the repo root is symlinked into `ComfyUI/custom_nodes/`. All DWI node code lives in `custom_nodes/dwi_nodes/` and shared utilities in `custom_nodes/utils/`.

### Node Registration
`custom_nodes/dwi_nodes/__init__.py` is the single registration point — it maps `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` for ComfyUI to discover all nodes. When adding a new node, import the class here and add entries to both dicts.

### Key Utilities
- **`utils/system_executor.py`** — runs FSL/MRtrix3/ANTs commands via subprocess, sets required env vars (`FSLDIR`, `FSLOUTPUTTYPE`, `OMP_NUM_THREADS`), handles GPU detection for `eddy_cuda`.
- **`utils/bids_handler.py`** — scans BIDS datasets, resolves subject/session paths, enforces output to `derivatives/diffyui/`.
- **`utils/file_manager.py`** — file I/O and path management helpers used across nodes.
- **`dwi_nodes/_import_utils.py`** — handles Python imports across the symlinked directory boundary; use its helpers when importing from `utils/` within node files.

### Data Flow
```
BIDSLoader → SubjectSelector/Bucket → [preprocessing chain] → derivatives/diffyui/
```
Preprocessing order: BrainMask → Denoise → ExtractB0 → TopupCorrection → EddyCorrection → BiasCorrection → TensorFitting/DTIfit → Tractography.

### Node Structure Convention
Every node class must define:
- `INPUT_TYPES()` — class method returning input schema
- `RETURN_TYPES` / `RETURN_NAMES` — tuple of output type strings
- A primary method (named in `FUNCTION`) that performs the work and returns a tuple matching `RETURN_TYPES`
- `CATEGORY` — set to `"DiffyUI/..."` for grouping in the UI

### Adding a New Node
1. Create `custom_nodes/dwi_nodes/my_node.py` following the convention above.
2. Use `system_executor.py` for any external tool calls.
3. Save outputs under `derivatives/diffyui/<subject>/` via `bids_handler.py`.
4. Register in `custom_nodes/dwi_nodes/__init__.py`.

### Configuration
`config/node_config.yml` holds default parameters for denoising, eddy, bias correction, tensor fitting, and tractography. Nodes read this at runtime for their defaults.

### TBSS Pipeline
Five dedicated nodes (`tbss_*.py`) implement FSL's TBSS workflow: `TBSS1Preproc → TBSS2Reg → TBSS3Postreg → TBSS4Prestats`, plus `TBSSFACollector` for gathering FA maps across subjects.

### Example Workflows
`examples/*.json` are ComfyUI workflow files (JSON) that can be loaded directly in the UI to see complete pipeline configurations.
