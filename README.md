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

4. **Access ComfyUI**:
   Open your browser and navigate to `http://localhost:8188`

5. **Verify custom nodes are loaded**:
   The DWI nodes should appear in the node menu under the "DWI" category.

## Project Structure

```
DiffyUI/
├── setup_local.sh              # Local installation script
├── requirements.txt            # Python dependencies
├── custom_nodes/               # ComfyUI custom nodes directory
│   ├── dwi_nodes/              # DWI processing nodes
│   │   ├── bids_loader.py     # BIDS dataset loader
│   │   ├── subject_selector.py # Subject selection
│   │   ├── subject_bucket.py   # Subject data container
│   │   ├── subject_iterator.py # Batch processing iterator
│   │   ├── brain_mask.py       # Brain mask extraction (FSL BET)
│   │   ├── denoising.py        # Denoising node (MRtrix3)
│   │   ├── eddy_correction.py  # Eddy correction (FSL)
│   │   ├── bias_correction.py  # Bias correction (ANTs)
│   │   ├── tensor_fitting.py   # Tensor fitting
│   │   ├── tractography.py     # Tractography
│   │   └── nifti_preview.py    # NIfTI file preview
│   └── utils/                  # Utility modules
│       ├── bids_handler.py     # BIDS format handling
│       ├── docker_executor.py  # System command executor (renamed from docker_executor)
│       ├── file_manager.py     # File I/O utilities
│       └── visualization.py    # QC visualization helpers
└── examples/                   # Example workflow files
```

## Custom Nodes

### BIDS Loader
Loads BIDS-formatted datasets and provides access to DWI and anatomical files.

### Subject Selector & Subject Bucket
Organize and select individual subjects for processing.

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

### DWI Tractography
Perform fiber tracking (tractography) using MRtrix3 or FSL.

### NIfTI Preview
Preview NIfTI files with 3-panel views (axial, coronal, sagittal).

### Brain 3D Viewer
Converts a brain NIfTI (e.g. from DWI Brain Mask) into a 3D mesh (OBJ or STL) using marching cubes and writes it to `output/3d/` and to `input/3d/brain_mesh_preview.{obj|stl}`. **Connect its `mesh_path` output to "Preview 3D & Animation" (3d category)** so the node runs and the mesh is shown. Use **"Queue Prompt"** (main run button) to run the full workflow; if you use "Run this node" on another branch only, the 3D branch will not run. If you use "Load 3D & Animation" instead, refresh the page after running once so the dropdown lists `3d/brain_mesh_preview.obj`.

**If the mesh opens in Meshlab but not in the ComfyUI interface:** the in-browser 3D viewer may support OBJ more reliably than STL. Use **output format "obj"** (default) for the Preview 3D panel. The files are valid either way; you can still open the STL in Meshlab from `ComfyUI/input/brain_mesh_preview.stl` or `output/3d/`.

**Preview 3D node looks empty but the mesh appears in the Assets tab:** Yes, it’s weird — the node that’s supposed to show the 3D preview doesn’t show it inline, while the same result appears in the Assets/Preview tab. The backend sends the same data (the `model_file` path) in both cases; the ComfyUI frontend is what decides where to render the 3D viewer. Right now it appears to draw the 3D view in the Assets area but not inside the Preview 3D & Animation node box. So this is a **frontend/UX limitation**, not an issue with our node or path. Workaround: use the **Assets** (or Preview) tab and open the 3D asset there (e.g. zoom in) to view the brain. A proper fix would be in the ComfyUI client so that the Preview 3D node’s inline widget shows the same 3D view.

**Brain orientation looks tilted:** NIfTI uses RAS (Z = superior); most 3D UIs use **Y-up**. Use the node option **viewer_up: "Y-up (ComfyUI / standard 3D)"** (default) so the brain is exported right-way-up. You can also try the viewer’s **Up Direction** (e.g. Y, Z, or Original) if you keep **viewer_up: "RAS (no change)"**.

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
