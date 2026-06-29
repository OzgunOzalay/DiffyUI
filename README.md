# DiffyUI — ComfyUI Extension for DWI Neuroimaging

DiffyUI wraps FSL, MRtrix3, and ANTs as ComfyUI nodes, letting you build and run diffusion-weighted imaging (DWI) analysis pipelines visually in a web interface. All input data must be in **BIDS format** — this is a hard requirement for reproducibility.

Web UI runs at **http://localhost:8188**.

## Quick Start

```bash
./setup_local.sh    # first-time setup
./run_diffyui.sh    # start server (DWI-only mode)
```

## Prerequisites

- Python 3.11+
- FSL (`bet`, `fslroi`, `eddy`, `dtifit`, `tbss_*` in PATH)
- MRtrix3 (`mrconvert`, `dwidenoise`, `dwifslpreproc`, `mrregister` in PATH)
- ANTs (`N4BiasFieldCorrection` in PATH)
- BIDS-formatted dataset

## Project Structure

```
DiffyUI/
├── setup_local.sh              # Installation script
├── run_diffyui.sh              # Start server in DWI-only mode
├── requirements.txt
├── config/
│   └── node_config.yml         # Default node parameters
├── custom_nodes/
│   ├── dwi_nodes/              # All DWI nodes (symlinked into ComfyUI)
│   │   ├── bids_subject_type.py    # BIDS_SUBJECT bundle type + builder
│   │   ├── bids_loader.py          # BIDS Project Loader (entry node)
│   │   ├── subject_batch_runner.py # Sequential batch runner
│   │   ├── workflow_packs.py       # DWIPreprocPack, DerivedFilePicker
│   │   ├── brain_mask.py           # FSL BET
│   │   ├── denoising.py            # MRtrix3 MP-PCA
│   │   ├── extract_b0.py           # b0 extraction
│   │   ├── topup_correction.py     # FSL topup
│   │   ├── eddy_correction.py      # FSL eddy / eddy_cuda
│   │   ├── bias_correction.py      # ANTs N4BiasFieldCorrection
│   │   ├── dtifit.py               # FSL dtifit (FA, MD, MO, L1-3, V1-3, S0)
│   │   ├── gibbs_unringing.py      # MRtrix3 mrdegibbs (Gibbs artefact removal)
│   │   ├── csd.py                  # Multi-tissue CSD: dwi2response + dwi2fod + mtnormalise
│   │   ├── eddy_qc.py              # FSL eddy_quad QC report (non-blocking)
│   │   ├── dki_fit.py              # DKI fitting via DIPY (MK, AK, RK, KFA, FA, MD, AD, RD)
│   │   ├── tractography.py         # MRtrix3 tckgen (FOD-based) + optional tcksift2
│   │   ├── nifti_preview.py        # 3-panel slice preview + FSLeyes button
│   │   ├── brain_3d_viewer.py      # 3D mesh extraction (OBJ/STL)
│   │   ├── nifti_stats.py          # fslstats / mrinfo text output
│   │   ├── tbss_fa_collector.py    # Collect FA maps for TBSS
│   │   ├── tbss_preproc.py         # tbss_1_preproc
│   │   ├── tbss_reg.py             # tbss_2_reg
│   │   ├── tbss_postreg.py         # tbss_3_postreg
│   │   ├── tbss_prestats.py        # tbss_4_prestats
│   │   ├── fba_prep.py             # FBA stage: copy inputs
│   │   ├── fba_subject1.py         # FBA: upsample + response
│   │   ├── fba_response_avg.py     # FBA: average response
│   │   ├── fba_subject2.py         # FBA: FOD + normalise
│   │   ├── fba_template_prep.py    # FBA: template prep
│   │   ├── fba_template_build.py   # FBA: population template
│   │   ├── fba_subject3a.py        # FBA: register + warp mask
│   │   ├── fba_template_mask.py    # FBA: template mask
│   │   ├── fba_subject3b.py        # FBA: fixels + FD + FC
│   │   ├── fba_logfc_fdc.py        # FBA: log FC + FDC
│   │   └── fba_group.py            # FBA: tractography + smooth
│   └── utils/
│       ├── bids_handler.py         # BIDS path resolution
│       ├── system_executor.py      # subprocess wrapper (FSL/MRtrix3/ANTs)
│       ├── file_manager.py         # File I/O helpers
│       └── cache_manager.py        # Node output caching
└── examples/
    └── workflow_dwi_preprocess.json  # Canonical preprocessing workflow
└── tests/
    └── test_nodes.py                 # Smoke tests (25 tests, no tools required)
```

## Data Flow

All pipelines follow this pattern:

```
BIDSProjectLoader
    │  bids_dataset, subject_list
    ▼
SubjectBatchRunner ──────────────────────────── auto re-queues per subject
    │  BIDS_SUBJECT (one subject bundle per run)
    ▼
DWIPreprocPack                    DerivedFilePicker (for derived outputs)
    │  subject_id, dwi_ap/pa,         │  subject_id, file_path
    │  bvec/bval, t1w                 │
    ▼                                 ▼
BrainMask → Denoise → GibbsUnringing → ExtractB0     TBSSFACollector → TBSS 1-4
    → Topup → Eddy → EddyQC               or FBA chain
    → BiasCorrection
    → DTIfit (single-shell: FA, MD, L1-3, V1-3…)
    → CSD → DWITractography (multi-shell)
    → DKIFit (multi-shell: MK, AK, RK, KFA…)
```

Outputs are written to `<bids_root>/<subject_id>/derivatives/diffyui/`.
This path is produced by `bids_handler.get_derivatives_path(subject_id, "diffyui")`.

## Node Reference

### Entry Nodes

**BIDS Project Loader** (`BIDSLoader`)
Scans a BIDS dataset root. Shows project name, subject count, sessions, and per-subject completion status.
Outputs: `bids_dataset` (STRING), `subject_list` (STRING, comma-separated).

**Subject Batch Runner** (`SubjectBatchRunner`)
Processes subjects one at a time. On each run it emits a `BIDS_SUBJECT` bundle for the current subject, saves state to `~/.diffyui/batch_state.json`, and re-queues the workflow for the next subject automatically — before downstream nodes run, so a failure in one subject doesn't stop the batch.

Key options:
- `completion_check` — glob relative to `<subject>/derivatives/diffyui/`; matching subjects are skipped (e.g. `dwi/DTI/*_FA.nii.gz`)
- `skip_completed` — toggle skip on/off
- `reset_batch` — toggle to restart from subject 0

Outputs: `subject` (BIDS_SUBJECT), `subject_id`, `current_index`, `total_subjects`, `batch_report`.

### Workflow Pack Nodes

**DWI Preproc Pack** (`DWIPreprocPack`)
Unpacks a `BIDS_SUBJECT` into the individual file paths the preprocessing pipeline needs.
Outputs: `subject_id`, `dwi_ap`, `bvec_ap`, `bval_ap`, `dwi_pa`, `bvec_pa`, `bval_pa`, `t1w`.
PA phase outputs are empty strings when no reverse-phase data exists.

**Derived File Picker** (`DerivedFilePicker`)
Picks a processed file from `<subject>/derivatives/diffyui/` using a glob pattern. Use this to feed downstream workflows that need outputs from a previous pipeline stage.
Input: `subject` (BIDS_SUBJECT), `file_pattern` (glob, e.g. `dwi/DTI/*_FA.nii.gz` or `dwi/CSD/wm_fod_norm.mif`).
Outputs: `subject_id`, `file_path`.

### Preprocessing Nodes (DWI/Preprocessing)

| Node | Tool | Key outputs |
|---|---|---|
| DWI Brain Mask | FSL BET | `brain_mask`, `extracted_brain` |
| DWI Denoise | MRtrix3 dwidenoise | `denoised_dwi`, `noise_map` |
| Gibbs Unringing | MRtrix3 mrdegibbs | `degibbs_dwi` |
| Extract B0 | MRtrix3 / fslroi | `b0_image` |
| DWI Topup Correction | FSL topup | `fieldmap`, `corrected_b0` |
| DWI Eddy Correction | FSL eddy / eddy_cuda | `dwi_corrected`, `bvec_corrected` |
| Eddy QC | FSL eddy_quad | `qc_report_dir` |
| DWI Bias Correction | ANTs N4 | `corrected_dwi` |
| DTIfit (FSL) | FSL dtifit | `fa_map`, `md_map`, `mo_map`, `l1/l2/l3`, `v1/v2/v3`, `s0`, `fa_directory` |
| CSD (Multi-Tissue) | MRtrix3 dwi2response + dwi2fod + mtnormalise | `wm_fod`, `gm_fod`, `csf_fod`, response txt files |
| DKI Fit (DIPY) | DIPY DiffusionKurtosisModel | `mk_map`, `ak_map`, `rk_map`, `kfa_map`, `fa_map`, `md_map`, `ad_map`, `rd_map` |

Eddy correction automatically uses `eddy_cuda` (GPU) when available, falling back to `eddy_cpu`. Before launching eddy_cuda, the node unloads ComfyUI models from GPU memory to avoid CUDA contention.

**CSD** and **DKI Fit** require multi-shell data (≥2 non-zero b-value shells). Both return a clear error string if given single-shell data.

**Gibbs Unringing** must run after denoising and before any interpolation (topup/eddy).

**Eddy QC** is non-blocking — `eddy_quad` failures produce an error string and never abort the batch.

### Tractography (DWI)

**DWI Tractography** (`DWITractography`)
Whole-brain fiber tracking using MRtrix3 `tckgen`. Takes the WM FOD image from the **CSD** node as input — not raw DWI. Algorithms: iFOD2 (default), SD_STREAM, Tensor_Det, Tensor_Prob. Optional SIFT2 streamline-weight estimation via `tcksift2`.
Inputs: `fod_file` (WM FOD from CSD), `mask_file` (brain mask).
Outputs: `tractogram_file` (.tck), `sift2_weights` (.txt, empty if SIFT2 disabled).

### QC / Visualisation (DWI)

**NIfTI Preview** — 3-panel PNG (axial/coronal/sagittal). Shows preview inline. Includes an **Open in FSLeyes** button. When the filename contains `skeleton`, renders a green overlay on the MNI152 brain template.

**Brain 3D Mesh** — Extracts a 3D mesh (OBJ or STL) via marching cubes. Connect `mesh_path` to ComfyUI's "Preview 3D & Animation" node to view.

**NIfTI Stats** — Runs `fslstats` or `mrinfo` and outputs structured key-value text. Useful for QC checks or feeding text to downstream logic.

### TBSS Pipeline (DWI/TBSS)

TBSS works at the project level (all subjects at once), not per-subject:

```
TBSSFACollector → TBSS1Preproc → TBSS2Reg → TBSS3Postreg → TBSS4Prestats
```

Feed `bids_dataset` and `subject_list` from `BIDSProjectLoader` directly into `TBSSFACollector`. Use `DerivedFilePicker` to supply FA maps if running after the DTI preprocessing batch.

### FBA Pipeline (DWI/FBA)

11 nodes implement fixel-based analysis — run per-subject first, then group-level:

**Per-subject:** `FBAPrep → FBASubject1 → FBAResponseAvg → FBASubject2 → FBASubject3a → FBASubject3b → FBALogFCFDC`

**Group-level:** `FBATemplatePrep → FBATemplateBuild → FBATemplateMask → FBAGroup`

## BIDS_SUBJECT Type

`BIDS_SUBJECT` is DiffyUI's internal bundle type — a Python dict carrying all BIDS paths for one subject:

```python
{
    "bids_root":        "/path/to/dataset",
    "subject_id":       "sub-001",
    "session_id":       "ses-01",    # or None
    "sessions":         ["ses-01"],  # all sessions found
    "files": {
        "dwi_ap":  "...", "bvec_ap": "...", "bval_ap": "...",
        "dwi_pa":  "...", "bvec_pa": "...", "bval_pa": "...",
        "t1w":     "...",
    },
    "derivatives_root": "/path/to/dataset/sub-001/derivatives/diffyui",
}
```

It is built automatically by `SubjectBatchRunner` and flows through pack nodes to unpack into individual file paths for the processing nodes.

## BIDS Dataset Structure

```
bids_dataset/
├── dataset_description.json
├── sub-001/
│   ├── anat/
│   │   └── sub-001_T1w.nii.gz
│   └── dwi/
│       ├── sub-001_dir-AP_dwi.nii.gz
│       ├── sub-001_dir-AP_dwi.bval
│       ├── sub-001_dir-AP_dwi.bvec
│       ├── sub-001_dir-PA_dwi.nii.gz
│       ├── sub-001_dir-PA_dwi.bval
│       └── sub-001_dir-PA_dwi.bvec
└── sub-002/
    └── ...
```

Sessions (`sub-001/ses-01/dwi/`) are detected automatically.

Outputs are written to `bids_dataset/<subject_id>/derivatives/diffyui/`.

## Adding a New Node

1. Create `custom_nodes/dwi_nodes/my_node.py` — define `INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES`, `FUNCTION`, `CATEGORY`.
2. Accept `BIDS_SUBJECT` input if the node needs per-subject files; use `DerivedFilePicker` logic to look up derived outputs.
3. Use `system_executor.py` for all external tool calls.
4. Write outputs under `<subject_id>/derivatives/diffyui/` via `bids_handler.get_derivatives_path(subject_id, "diffyui")`.
5. Register the class in `custom_nodes/dwi_nodes/__init__.py` (both `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`).
6. Restart the server.

## Troubleshooting

**Tools not found** — verify PATH: `which bet fslroi mrconvert dwidenoise N4BiasFieldCorrection`

**Nodes not appearing** — check the server startup log (`/tmp/diffyui_*.log`) for import errors; ensure `ComfyUI/custom_nodes` symlink points to `<project>/custom_nodes`.

**Batch stops after one subject** — check `~/.diffyui/batch_state.json`; toggle `reset_batch` to True then False to restart; ensure `auto_queue` is True.

**Eddy runs slowly** — expected after initial GPU compute; eddy becomes I/O-bound during file writing. Use SSD/NVMe storage for derivatives.

## Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — node-based workflow engine
- [FSL](https://fsl.fmrib.ox.ac.uk/) — BET, eddy, dtifit, TBSS
- [MRtrix3](https://www.mrtrix.org/) — dwidenoise, tckgen, fixel-based analysis
- [ANTs](https://stnava.github.io/ANTs/) — N4BiasFieldCorrection
- [BIDS](https://bids.neuroimaging.io/) — data organisation standard
