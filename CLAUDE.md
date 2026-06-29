# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

DiffyUI is a ComfyUI extension for diffusion-weighted imaging (DWI) neuroimaging analysis. It wraps FSL, MRtrix3, and ANTs command-line tools as ComfyUI nodes, enabling visual, node-based construction of DWI pipelines. **All input data must be in BIDS format** — this is a hard project requirement for reproducibility.

Web UI: `http://localhost:8188`

## Commands

### Installation
```bash
./setup_local.sh
```
Clones ComfyUI, installs Python dependencies, creates `ComfyUI/custom_nodes → <project>/custom_nodes` symlink, verifies neuroimaging tools on PATH.

### Running
```bash
./run_diffyui.sh        # Recommended: DWI-only mode (--diffyui-only --disable-api-nodes)
cd ComfyUI && python main.py --listen 0.0.0.0 --port 8188  # Full ComfyUI
```

### Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Symlink Layout
`ComfyUI/custom_nodes` is a symlink to `<project>/custom_nodes/`. All DWI node code lives in `custom_nodes/dwi_nodes/` and shared utilities in `custom_nodes/utils/`.

### Node Registration
`custom_nodes/dwi_nodes/__init__.py` is the single registration point — it maps `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` for ComfyUI to discover all nodes. When adding a new node, import the class here and add entries to both dicts.

### Data Flow
```
BIDSProjectLoader (bids_dataset + subject_list)
    ↓
SubjectBatchRunner  [emits BIDS_SUBJECT per run, re-queues automatically]
    ↓
DWIPreprocPack  [unpacks BIDS_SUBJECT → individual file paths]
    ↓
BrainMask → Denoise → GibbsUnringing → ExtractB0 → Topup → Eddy → EddyQC
    → BiasCorrection → DTIfit (single-shell) / CSD → Tractography (multi-shell)
                     → DKIFit (multi-shell)
    ↓
<subject_id>/derivatives/diffyui/
```

For derived outputs (TBSS FA maps, FBA FODs etc.), use `DerivedFilePicker` which picks a file from `<subject_id>/derivatives/diffyui/` by glob pattern.

**Output path convention:** All writer nodes use `bids_handler.get_derivatives_path(subject_id, "diffyui")` → `<bids_root>/<subject_id>/derivatives/diffyui/`. This places derivatives inside each subject's folder (not at `<bids_root>/derivatives/`). Readers (`_is_done`, `_check_completion`, `build_bids_subject`) all use the same convention.

### BIDS_SUBJECT Type
`BIDS_SUBJECT` (`custom_nodes/dwi_nodes/bids_subject_type.py`) is a custom ComfyUI type — a Python dict built by `build_bids_subject()` that carries all BIDS paths for one subject:
```python
{
    "bids_root": str, "subject_id": str, "session_id": str|None,
    "sessions": list[str],
    "files": {"dwi_ap": str, "bvec_ap": str, "bval_ap": str,
              "dwi_pa": str, "bvec_pa": str, "bval_pa": str, "t1w": str},
    "derivatives_root": str,
}
```
Pack nodes (`DWIPreprocPack`, `DerivedFilePicker`) receive this and output individual STRING file paths to the processing nodes.

### Key Utilities
- **`utils/system_executor.py`** — runs FSL/MRtrix3/ANTs commands via subprocess, sets required env vars (`FSLDIR`, `FSLOUTPUTTYPE`, `OMP_NUM_THREADS`), detects and uses `eddy_cuda` for GPU acceleration.
- **`utils/bids_handler.py`** — scans BIDS datasets, resolves subject/session paths.
- **`utils/file_manager.py`** — file I/O and path management helpers.
- **`dwi_nodes/_import_utils.py`** — handles Python imports across the symlinked directory boundary; use its helpers when importing from `utils/` within node files.

### Node Structure Convention
Every node class must define:
- `INPUT_TYPES()` — class method returning input schema
- `RETURN_TYPES` / `RETURN_NAMES` — tuple of output type strings
- A primary method (named in `FUNCTION`) that performs the work and returns a tuple matching `RETURN_TYPES`
- `CATEGORY` — use `"DiffyUI/Batch"`, `"DiffyUI/Packs"`, `"DWI"`, `"DWI/Preprocessing"`, `"DWI/TBSS"`, or `"DWI/FBA"`

### Adding a New Node
1. Create `custom_nodes/dwi_nodes/my_node.py` following the convention above.
2. Accept `BIDS_SUBJECT` as input (via a pack node) rather than raw STRING file paths where possible — this keeps the BIDS-first contract intact.
3. Use `system_executor.py` for any external tool calls.
4. Save outputs under `<subject_id>/derivatives/diffyui/` via `bids_handler.get_derivatives_path(subject_id, "diffyui")`.
5. Register in `custom_nodes/dwi_nodes/__init__.py` (wrap import in try/except for nodes with optional heavy deps like DIPY).

### Node Inventory (40 nodes)

**Entry / Batch:** BIDSLoader, SubjectBatchRunner

**Workflow Packs:** DWIPreprocPack, DerivedFilePicker

**Preprocessing:** DWIBrainMask, DWIDenoise, GibbsUnringing, ExtractB0, DWITopupCorrection,
DWIEddyCorrection, EddyQC, DWIBiasCorrection, DTIfit, CSD (multi-tissue), DKIFit

**Tractography:** DWITractography (takes WM FOD from CSD; MRtrix3 tckgen + optional tcksift2)

**QC / Visualisation:** NIfTIPreview, Brain3DViewer (display name: Brain 3D Mesh), NIfTIStats

**TBSS:** TBSSFACollector, TBSS1Preproc, TBSS2Reg, TBSS3Postreg, TBSS4Prestats

**FBA:** FBAPrep, FBASubject1, FBAResponseAvg, FBASubject2, FBATemplatePrep, FBATemplateBuild, FBASubject3a, FBATemplateMask, FBASubject3b, FBALogFCFDC, FBAGroup

**Multi-shell requirements:** CSD and DKIFit both require ≥2 non-zero b-value shells and will
return an error string (not raise) if the data is single-shell.

### Configuration
`config/node_config.yml` holds default parameters for denoising, eddy, bias correction, and tensor fitting. Nodes read this at runtime for their defaults.

### Example Workflows
`examples/workflow_dwi_preprocess.json` — canonical BIDS → Batch → DWIPreprocPack → BrainMask → Denoise → Preview workflow. Load directly in the UI.

## Key Design Decisions

- **BIDS-only inputs** — no ad-hoc file path entry at the top level; enforces reproducibility.
- **Batch runner re-queues before downstream** — this means a failure in subject N's pipeline doesn't prevent subject N+1 from starting; failure recording is via the `completion_check` glob at batch end.
- **Separate pack nodes** (not a mode dropdown) — ComfyUI `RETURN_TYPES` are fixed at class definition time and cannot change dynamically based on a widget value.
- **Docker deferred** — `system_executor.py` is the execution layer; no Docker abstraction yet.
- **No Ollama/local-LLM nodes** — DeepSeek QC node was removed; it was experimental and not used daily.
- **CSD is the gateway to tractography** — `DWITractography` now requires a WM FOD from `CSD`, not raw DWI. This enforces the correct pipeline order.
- **dwidenoise / mrdegibbs accept NIfTI directly** (MRtrix3 3.x) — no NIfTI→MIF round-trips in `denoising.py` or `gibbs_unringing.py`.
- **EddyQC is non-blocking** — `eddy_quad` failures return an error string; they never stop the batch.
- **DKI uses DIPY (lazy import)** — `dki_fit.py` imports DIPY inside `run_dki()` so the node loads even if DIPY is not installed; missing DIPY returns a clear error string.
- **Smoke tests** — `tests/test_nodes.py` covers import + `INPUT_TYPES()` + `IS_CHANGED()` + error-string behaviour for all 4 new nodes; run with `python -m pytest tests/ -v`.
