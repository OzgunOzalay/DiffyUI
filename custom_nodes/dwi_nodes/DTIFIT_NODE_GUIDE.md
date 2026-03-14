# DTIfit Node - FSL Diffusion Tensor Fitting

## Overview
The DTIfit node wraps FSL's `dtifit` command for fitting a diffusion tensor model at each voxel. This is a core DTI analysis tool that produces standard DTI metrics.

**Reference:** [FSL DTIFIT Documentation](https://fsl.fmrib.ox.ac.uk/fsl/docs/diffusion/dtifit.html)

## Inputs

### Required
| Input | Type | Description | Typical Source |
|-------|------|-------------|----------------|
| `dwi_file` | STRING | 4D diffusion-weighted NIfTI | Eddy Correction → `dwi_corrected` |
| `mask_file` | STRING | 3D binary brain mask | Brain Mask → `mask_file` |
| `bvec_file` | STRING | Gradient directions (bvecs) | Eddy Correction → `bvec_corrected` |
| `bval_file` | STRING | B-values (bvals) | Usually same as input (not rotated) |

### Optional
| Parameter | Type | Default | FSL Flag | Description |
|-----------|------|---------|----------|-------------|
| `output_basename` | STRING | "dti" | `--out` | Output basename (e.g. `dti` → `dti_FA.nii.gz`) |
| `weighted_ls` | BOOLEAN | False | `--wls` | Use weighted least squares instead of standard linear regression |
| `save_tensor` | BOOLEAN | True | `--save_tensor` | Save tensor elements as 4D file (Dxx,Dxy,Dxz,Dyy,Dyz,Dzz) |
| `output_sse` | BOOLEAN | False | `--sse` | Output sum of squared errors (useful for artifact detection) |
| `confound_regressors` | STRING | "" | `--cni` | Optional confound regressors file |
| `gradnonlin_file` | STRING | "" | `--gradnonlin` | Gradient nonlinearity tensor file (for scanner corrections) |

## Outputs

### Return Values
| Output | Description | Filename Pattern |
|--------|-------------|------------------|
| `fa_map` | Fractional anisotropy (0=isotropic, 1=stick-like) | `{basename}_FA.nii.gz` |
| `md_map` | Mean diffusivity | `{basename}_MD.nii.gz` |
| `output_dir` | Directory containing all outputs | `derivatives/diffyui/{subject}/dwi/DTI/` |
| `l1_map` | 1st eigenvalue (axial diffusivity) | `{basename}_L1.nii.gz` |
| `v1_map` | 1st eigenvector (primary diffusion direction) | `{basename}_V1.nii.gz` |
| `tensor_file` | Tensor elements (if `save_tensor=True`) | `{basename}_tensor.nii.gz` |
| `all_outputs` | Text summary of all output paths | Newline-separated list |

### All Generated Files
FSL dtifit always produces these standard outputs:

**Eigenvalues:**
- `{basename}_L1.nii.gz` - 1st eigenvalue (largest, axial diffusivity)
- `{basename}_L2.nii.gz` - 2nd eigenvalue
- `{basename}_L3.nii.gz` - 3rd eigenvalue (smallest, perpendicular diffusivity)

**Eigenvectors:**
- `{basename}_V1.nii.gz` - 1st eigenvector (3D, primary diffusion direction)
- `{basename}_V2.nii.gz` - 2nd eigenvector
- `{basename}_V3.nii.gz` - 3rd eigenvector

**Scalar Metrics:**
- `{basename}_FA.nii.gz` - Fractional anisotropy
- `{basename}_MD.nii.gz` - Mean diffusivity
- `{basename}_MO.nii.gz` - Mode of anisotropy (-1=oblate, 0=isotropic, 1=prolate)
- `{basename}_S0.nii.gz` - Raw T2 signal (no diffusion weighting)

**Optional:**
- `{basename}_tensor.nii.gz` - 4D tensor (if `save_tensor=True`): Dxx, Dxy, Dxz, Dyy, Dyz, Dzz
- `{basename}_sse.nii.gz` - Sum of squared errors (if `output_sse=True`)

## Typical Workflow

```
BIDS Loader → Subject Selector
                ↓
Extract B0 → Brain Mask
                ↓
Topup Correction → Eddy Correction → DTIfit → TBSS / Tractography
                                        ↓
                                    NIfTI Preview (FA map)
```

### Example Connection
```
Eddy Correction:
  - dwi_corrected → DTIfit.dwi_file
  - bvec_corrected → DTIfit.bvec_file
  - bval_file → DTIfit.bval_file

Brain Mask:
  - mask_file → DTIfit.mask_file

DTIfit:
  - fa_map → NIfTI Preview (visualize)
  - fa_map → TBSS FA Collector (group analysis)
  - v1_map → Tractography (fiber orientation)
```

## Notes

### Preprocessing Requirements
- **Eddy/topup correction required**: DTI fitting assumes data is already corrected for eddy currents and distortions
- **Brain mask recommended**: Improves fitting speed and quality (excludes non-brain voxels)
- **Rotated bvecs**: Use eddy-corrected bvecs (output from Eddy node) to account for head motion

### Output Location
Follows BIDS derivatives structure:
```
bids_dataset/
└── derivatives/
    └── diffyui/
        └── sub-XX/
            └── dwi/
                └── DTI/
                    ├── dti_FA.nii.gz
                    ├── dti_MD.nii.gz
                    ├── dti_L1.nii.gz
                    ├── dti_V1.nii.gz
                    └── ... (all other outputs)
```

### Performance
- **Speed**: ~10-30 seconds per subject (single-shell, ~60 volumes)
- **Multi-shell**: Works with multi-shell data (uses all shells for fitting)
- **Kurtosis**: For kurtosis fitting, use command-line dtifit with `--kurt` flag (not yet in node UI)

### Common Issues
- **"No slices"**: Check mask is valid binary mask (0s and 1s only)
- **"Too few directions"**: Need at least 6 unique gradient directions for DTI fitting
- **Poor FA quality**: Ensure data is eddy-corrected and bvecs are rotated

## Advanced: Weighted Least Squares
Set `weighted_ls=True` to use weighted fitting:
- Reduces bias from noise floor in low-SNR voxels
- Slightly slower than standard least squares
- Recommended for low-SNR data or high b-values (>2000 s/mm²)

## Advanced: Gradient Nonlinearity Correction
If you have a gradient nonlinearity tensor file from your scanner:
1. Obtain the tensor file from scanner manufacturer or compute with FSL tools
2. Connect to `gradnonlin_file` input
3. DTIfit will account for b-value and gradient orientation variability due to gradient distortions

## See Also
- **FSL Documentation:** https://fsl.fmrib.ox.ac.uk/fsl/docs/diffusion/dtifit.html
- **TBSS nodes:** Use FA output for tract-based spatial statistics
- **Tractography nodes:** Use V1 output for seed-based fiber tracking
- **Original Tensor Fitting node:** `DWITensorFitting` (older node, supports MRtrix3)
