# DiffyUI - ComfyUI Extension for DWI Analysis

DiffyUI extends ComfyUI with custom nodes for diffusion-weighted imaging (DWI) analysis, creating an interactive web-based workflow system for neuroimaging. The system wraps FSL, MRtrix3, and ANTs tools as ComfyUI nodes and supports BIDS data organization.

## Features

- **Interactive Node-Based Workflows**: Build DWI processing pipelines visually in ComfyUI's web interface
- **BIDS Support**: Works with BIDS-formatted datasets (expects `anat/` and `dwi/` folders)
- **System Tools Integration**: Uses locally installed FSL, MRtrix3, and ANTs tools
- **Incremental Development**: Start with denoising, then add eddy correction, bias correction, tensor fitting, and tractography
- **Extensible**: Nodes can be modified and extended later by editing Python code

## Architecture

The system consists of:
- **ComfyUI Web Server**: Provides the interactive node-based interface
- **Custom Nodes**: Python nodes that wrap neuroimaging tools
- **BIDS Handler**: Utilities for reading/writing BIDS datasets
- **System Executor**: Wrapper for executing commands using system-installed tools

## Prerequisites

- Python 3.11 or higher
- ComfyUI (will be installed by setup script)
- **Neuroimaging tools installed on your system**:
  - FSL (with `bet`, `fslroi`, `eddy` commands available in PATH)
  - MRtrix3 (with `mrconvert`, `dwidenoise` commands available in PATH)
  - ANTs (with `N4BiasFieldCorrection` command available in PATH)
- BIDS-formatted dataset with `anat/` and `dwi/` folders
- Sufficient disk space for processing outputs

## Installation

1. **Clone or download this repository**:
   ```bash
   cd /path/to/DiffyUI
   ```

2. **Run the setup script**:
   ```bash
   ./setup_local.sh
   ```
   
   This will:
   - Clone ComfyUI repository (if not already present)
   - Install ComfyUI dependencies
   - Install DWI node dependencies
   - Create symlinks to custom nodes
   - Verify neuroimaging tools are available

3. **Start ComfyUI**:
   ```bash
   cd ComfyUI
   python main.py --listen 0.0.0.0 --port 8188
   ```
   Or use the DiffyUI startup script for a DWI-focused UI (no image/video generation nodes):
   ```bash
   ./run_diffyui.sh
   ```

4. **Access ComfyUI**:
   Open your browser and navigate to `http://localhost:8188`

5. **Verify custom nodes are loaded**:
   The DWI nodes should appear in the node menu under the "DWI" category.

### Running DiffyUI without image/video generation

To run DiffyUI with only DWI-related and essential nodes (no ComfyUI image/video generation):

- **Recommended:** Start with the provided script:
  ```bash
  ./run_diffyui.sh
  ```
  This runs ComfyUI with `--disable-api-nodes` and `--diffyui-only`: API nodes (Sora, Runway, etc.) are not loaded, built-in extras are limited to Preview as Text and string/utils, and core diffusion nodes (samplers, checkpoint/VAE/CLIP loaders, latent/conditioning) are removed. Load Image, Save Image, Preview Image, and basic image passthrough nodes are kept for NIfTI preview and workflows.

- **Manual:** From the `ComfyUI` directory:
  ```bash
  python main.py --listen 0.0.0.0 --port 8188 --disable-api-nodes --diffyui-only
  ```
  Use `--disable-api-nodes` alone if you only want to disable API nodes and keep the rest of the UI unchanged.

## Project Structure

```
DiffyUI/
├── setup_local.sh              # Local installation script
├── run_diffyui.sh              # Start ComfyUI in DWI-only mode (no image/video gen nodes)
├── requirements.txt            # Python dependencies
├── custom_nodes/               # ComfyUI custom nodes directory
│   ├── dwi_nodes/              # DWI processing nodes
│   │   ├── bids_loader.py          # BIDS dataset loader
│   │   ├── subject_selector.py     # Subject selection by ID
│   │   ├── subject_bucket.py       # Subject data container / pass-through validator
│   │   ├── subject_iterator.py     # Manual index-based subject iterator
│   │   ├── subject_batch_runner.py # Automatic sequential batch processing
│   │   ├── brain_mask.py           # Brain mask extraction (FSL BET)
│   │   ├── denoising.py            # Denoising node (MRtrix3)
│   │   ├── eddy_correction.py      # Eddy correction (FSL)
│   │   ├── bias_correction.py      # Bias correction (ANTs)
│   │   ├── tensor_fitting.py       # Tensor fitting (legacy)
│   │   ├── dtifit.py               # DTI fitting (FSL dtifit - comprehensive)
│   │   ├── tractography.py         # Tractography
│   │   ├── tbss_fa_collector.py    # Collect FA maps for TBSS
│   │   ├── tbss_preproc.py         # TBSS step 1: preprocess FA
│   │   ├── tbss_reg.py             # TBSS step 2: nonlinear registration
│   │   ├── tbss_postreg.py         # TBSS step 3: apply warps, mean FA
│   │   ├── tbss_prestats.py        # TBSS step 4: threshold skeleton, project FA
│   │   ├── nifti_preview.py        # NIfTI preview + FSLeyes button + skeleton overlay
│   │   └── web/
│   │       └── nifti_preview.js    # Frontend: Open in FSLeyes button
│   └── utils/                  # Utility modules
│       ├── bids_handler.py     # BIDS format handling
│       ├── system_executor.py  # FSL/MRtrix3/ANTs command executor
│       ├── file_manager.py     # File I/O utilities
│       └── cache_manager.py    # Node output caching
└── examples/                   # Example workflow files
```

## Custom Nodes

### BIDS Loader
Loads BIDS-formatted datasets and provides access to DWI and anatomical files.

### Subject Selector & Subject Bucket
Organize and select individual subjects for processing.

### Subject Batch Runner
Automatically processes all subjects sequentially without manual intervention. Maintains state in `~/.diffyui/batch_state.json` and re-queues the workflow via the ComfyUI HTTP API after each subject completes. State auto-resets when the subject list changes. Toggle `reset_batch` to restart from subject 0.

### DWI Brain Mask
Extracts brain mask from DWI data using FSL BET on the b0 volume.

### DWI Denoise
Denoise DWI data using MRtrix3's MP-PCA denoising algorithm.

### DWI Eddy Correction
Correct for eddy currents and motion using FSL eddy.

### DWI Bias Correction
Correct bias field using ANTs N4BiasFieldCorrection.

### DWI Tensor Fitting
Fit diffusion tensor model (DTI) to DWI data using FSL or MRtrix3.

### DTIfit (FSL)
Comprehensive FSL dtifit wrapper with all standard outputs (FA, MD, MO, L1/L2/L3, V1/V2/V3, S0). Supports weighted least squares, tensor saving, SSE output, and gradient nonlinearity correction.

### DWI Tractography
Perform fiber tracking (tractography) using MRtrix3 or FSL.

### NIfTI Preview
Preview NIfTI files with 3-panel views (axial, coronal, sagittal). Includes an **Open in FSLeyes** button that launches FSLeyes with the current file after the node has executed. When the filename contains `skeleton`, the preview automatically renders a green overlay on the skull-stripped MNI152 T1 1mm brain template (`MNI152_T1_1mm_brain.nii.gz` from `$FSLDIR/data/standard/`).

### Brain 3D Viewer
Converts a brain NIfTI (e.g. from DWI Brain Mask) into a 3D mesh (OBJ or STL) using marching cubes and writes it to `output/3d/` and to `input/3d/brain_mesh_preview.{obj|stl}`. **Connect its `mesh_path` output to "Preview 3D & Animation" (3d category)** so the node runs and the mesh is shown. Use **"Queue Prompt"** (main run button) to run the full workflow; if you use "Run this node" on another branch only, the 3D branch will not run. If you use "Load 3D & Animation" instead, refresh the page after running once so the dropdown lists `3d/brain_mesh_preview.obj`.

**If the mesh opens in Meshlab but not in the ComfyUI interface:** the in-browser 3D viewer may support OBJ more reliably than STL. Use **output format "obj"** (default) for the Preview 3D panel. The files are valid either way; you can still open the STL in Meshlab from `ComfyUI/input/brain_mesh_preview.stl` or `output/3d/`.

**Preview 3D node looks empty but the mesh appears in the Assets tab:** Yes, it’s weird — the node that’s supposed to show the 3D preview doesn’t show it inline, while the same result appears in the Assets/Preview tab. The backend sends the same data (the `model_file` path) in both cases; the ComfyUI frontend is what decides where to render the 3D viewer. Right now it appears to draw the 3D view in the Assets area but not inside the Preview 3D & Animation node box. So this is a **frontend/UX limitation**, not an issue with our node or path. Workaround: use the **Assets** (or Preview) tab and open the 3D asset there (e.g. zoom in) to view the brain. A proper fix would be in the ComfyUI client so that the Preview 3D node’s inline widget shows the same 3D view.

**Brain orientation looks tilted:** NIfTI uses RAS (Z = superior); most 3D UIs use **Y-up**. Use the node option **viewer_up: "Y-up (ComfyUI / standard 3D)"** (default) so the brain is exported right-way-up. You can also try the viewer’s **Up Direction** (e.g. Y, Z, or Original) if you keep **viewer_up: "RAS (no change)"**.

### TBSS Pipeline
Five nodes implement FSL's Tract-Based Spatial Statistics workflow:

| Node | FSL command | Key outputs |
|---|---|---|
| TBSS FA Collector | — | `fa_directory` (symlinks FA maps) |
| TBSS 1 Preproc | `tbss_1_preproc` | `project_dir` |
| TBSS 2 Reg | `tbss_2_reg` | `project_dir` |
| TBSS 3 Postreg | `tbss_3_postreg` | `project_dir`, `mean_fa_path`, `mean_fa_skeleton_path` |
| TBSS 4 Prestats | `tbss_4_prestats` | `project_dir`, `all_fa_skeletonised_path`, `mean_fa_skeleton_path` |

Connect them in sequence: FA Collector → TBSS 1 → TBSS 2 → TBSS 3 → TBSS 4. All nodes cache their outputs and detect upstream errors to avoid cascading failures. TBSS 2 Reg handles partial re-runs gracefully (detects completed warp files and skips re-registration).

### NIfTI Stats
Runs **fslstats** (FSL) or **mrinfo** (MRtrix) on an input NIfTI image and outputs **structured text** with common metrics and stats (e.g. mean, std, min, max, volume, dimensions). The output is LLM-friendly (markdown-style key-value) and can be connected to **Preview as Text** (utils category) to view, or fed to an LLM downstream. Input: **image** (path to .nii or .nii.gz). Optional: **tool** (fslstats or mrinfo).

## Usage

### Basic Workflow

1. **Start ComfyUI**:
   ```bash
   cd ComfyUI
   python main.py --listen 0.0.0.0 --port 8188
   ```

2. **Open ComfyUI**: Navigate to `http://localhost:8188`

3. **Load a workflow**: Use the example workflows in the `examples/` directory, or build your own

4. **Configure nodes**:
   - Use BIDS Loader to select your dataset
   - Connect Subject Selector to get individual subject files
   - Add processing nodes (Brain Mask, Denoise, etc.)
   - Configure node parameters as needed

5. **Run the workflow**: Click "Queue Prompt" to execute

### Example: Brain Mask Extraction

1. Add a "BIDS Loader" node and set the dataset path
2. Add a "Subject Selector" node connected to BIDS Loader
3. Add a "Subject Bucket" node connected to Subject Selector
4. Add a "DWI Brain Mask" node connected to Subject Bucket's AP phase DWI output
5. Add a "NIfTI Preview" node to preview the mask
6. Run the workflow

## Data Organization

The system expects BIDS-formatted datasets with the following structure:

```
bids_dataset/
├── sub-01/
│   ├── anat/
│   │   └── sub-01_T1w.nii.gz
│   └── dwi/
│       ├── sub-01_dir-AP_dwi.nii.gz
│       ├── sub-01_dir-AP_dwi.bval
│       ├── sub-01_dir-AP_dwi.bvec
│       ├── sub-01_dir-PA_dwi.nii.gz
│       ├── sub-01_dir-PA_dwi.bval
│       └── sub-01_dir-PA_dwi.bvec
└── sub-02/
    └── ...
```

Outputs are written to the `derivatives/diffyui/` directory within the BIDS dataset.

## Modifying Nodes

Nodes can be extended and modified by editing the Python files in `custom_nodes/dwi_nodes/`. After making changes:

1. Restart ComfyUI
2. The changes will be reflected in the web interface

You can:
- Add new input parameters
- Modify output types
- Change processing logic
- Add validation or error handling

## Troubleshooting

### Tools not found
- Verify tools are installed: `which bet fslroi mrconvert dwidenoise N4BiasFieldCorrection`
- Ensure tools are in your system PATH
- For FSL, ensure FSLDIR environment variable is set if needed

### Nodes not appearing
- Verify custom_nodes directory symlinks are correct
- Check ComfyUI logs for import errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`

### Processing errors
- Check ComfyUI console output for error messages
- Verify input files exist and are in correct format
- Check BIDS structure is valid
- Ensure file permissions allow reading/writing

### Eddy correction performance
- **GPU acceleration**: The Eddy correction node automatically uses `eddy_cuda` (GPU) when available, falling back to `eddy_cpu` if not found.
- **GPU memory management**: Before running `eddy_cuda`, the node automatically frees GPU memory by unloading ComfyUI models. This prevents GPU contention between ComfyUI's PyTorch backend and FSL's CUDA processes.
- **Performance optimizations**: The node enables FSL eddy performance flags for CUDA:
  - `--dont_sep_offs_move`: Faster processing with minimal quality impact
  - `--nvoxhp=1000`: Reduced hyperparameter voxels (faster, good for most data)
  - `--dont_peas`: Skips post-eddy alignment for single-shell data
  - Multi-threaded I/O: Sets `OMP_NUM_THREADS=4` for faster file operations
- **Normal behavior**: After initial GPU compute, eddy becomes I/O bound (disk reading/writing). You'll see GPU usage drop to <10% and single CPU core active - this is normal FSL behavior during the I/O phase.
- **Further optimization**: For fastest performance, consider:
  - Using SSD/NVMe storage for output directory
  - Using tmpfs/RAM disk: `sudo mount -t tmpfs -o size=50G tmpfs /path/to/tmpdir` (adjust size based on RAM)
  - Ensuring no other disk-intensive processes are running
- **Check binary used**: The node logs which eddy binary it selected. Look for `[DWI Eddy] Using eddy binary:` in the console.

### FSL environment issues
- The executor automatically sets up FSL environment variables
- If issues persist, ensure FSLDIR is set: `export FSLDIR=/usr/share/fsl`

## Development

### Adding New Nodes

1. Create a new Python file in `custom_nodes/dwi_nodes/`
2. Follow the pattern from existing nodes
3. Register in `custom_nodes/dwi_nodes/__init__.py`
4. Restart ComfyUI

### Testing

Test nodes incrementally:
1. Start with BIDS Loader and Subject Selector
2. Test with a small dataset
3. Verify outputs
4. Move to processing nodes

## License

[Specify your license here]

## Contributing

[Contributing guidelines if applicable]

## Support

[Support information]

## Acknowledgments

- ComfyUI for the excellent node-based framework
- FSL, MRtrix3, and ANTs teams for the neuroimaging tools
- BIDS community for data organization standards
