# DTIfit Node Implementation Summary

## What Was Created

A new comprehensive FSL DTIfit node (`dtifit.py`) that fully implements the FSL `dtifit` command-line interface as a ComfyUI node.

## Files Created/Modified

### New Files
1. **`custom_nodes/dwi_nodes/dtifit.py`** - Main node implementation
2. **`custom_nodes/dwi_nodes/DTIFIT_NODE_GUIDE.md`** - Comprehensive user guide

### Modified Files
1. **`custom_nodes/dwi_nodes/__init__.py`** - Registered new node
2. **`README.md`** - Added DTIfit node documentation

## Node Specifications

### Node Name
- **Class**: `DTIfitNode`
- **Display Name**: "DTIfit (FSL)"
- **Category**: DWI

### Inputs

**Required:**
- `dwi_file` - 4D diffusion-weighted NIfTI
- `mask_file` - 3D binary brain mask
- `bvec_file` - Gradient directions (bvecs)
- `bval_file` - B-values (bvals)

**Optional:**
- `output_basename` - Output basename (default: "dti")
- `weighted_ls` - Use weighted least squares (FSL `--wls`)
- `save_tensor` - Save tensor elements (FSL `--save_tensor`)
- `output_sse` - Output sum of squared errors (FSL `--sse`)
- `confound_regressors` - Confound regressors file (FSL `--cni`)
- `gradnonlin_file` - Gradient nonlinearity tensor (FSL `--gradnonlin`)

### Outputs

**Return Values:**
1. `fa_map` - Fractional anisotropy map path
2. `md_map` - Mean diffusivity map path
3. `output_dir` - Output directory path
4. `l1_map` - L1 eigenvalue (axial diffusivity) path
5. `v1_map` - V1 eigenvector (primary direction) path
6. `tensor_file` - Tensor elements file path (if enabled)
7. `all_outputs` - Text summary of all outputs

**All Generated Files:**
- `{basename}_FA.nii.gz` - Fractional anisotropy
- `{basename}_MD.nii.gz` - Mean diffusivity
- `{basename}_MO.nii.gz` - Mode of anisotropy
- `{basename}_S0.nii.gz` - Raw T2 signal
- `{basename}_L1.nii.gz` - 1st eigenvalue (axial diffusivity)
- `{basename}_L2.nii.gz` - 2nd eigenvalue
- `{basename}_L3.nii.gz` - 3rd eigenvalue
- `{basename}_V1.nii.gz` - 1st eigenvector (primary direction)
- `{basename}_V2.nii.gz` - 2nd eigenvector
- `{basename}_V3.nii.gz` - 3rd eigenvector
- `{basename}_tensor.nii.gz` - Tensor elements (optional)
- `{basename}_sse.nii.gz` - Sum of squared errors (optional)

## Features

### BIDS Compliance
- Follows DiffyUI's BIDS derivatives structure
- Outputs to: `derivatives/diffyui/{subject}/dwi/DTI/`
- Infers subject ID and BIDS root from input paths

### Compatibility
- Designed to connect directly with existing DiffyUI nodes:
  - **Upstream**: Eddy Correction (dwi_corrected, bvec_corrected, bval_file)
  - **Upstream**: Brain Mask (mask_file)
  - **Downstream**: TBSS FA Collector (fa_map)
  - **Downstream**: Tractography (v1_map for fiber orientation)
  - **Downstream**: NIfTI Preview (any map for visualization)

### FSL Documentation Compliance
- Implements all command-line options from: https://fsl.fmrib.ox.ac.uk/fsl/docs/diffusion/dtifit.html
- Uses FSL standard naming conventions for outputs
- Supports weighted least squares, tensor saving, SSE output
- Supports gradient nonlinearity correction

## Typical Workflow

```
BIDS Loader → Subject Selector
                ↓
Extract B0 → Brain Mask
                ↓
Topup Correction → Eddy Correction → DTIfit
                                        ↓
                                     ┌──┴──┐
                                     ↓     ↓
                                  TBSS  Tractography
                                     ↓
                              NIfTI Preview
```

## Usage Example

1. Connect Eddy Correction outputs:
   - `dwi_corrected` → DTIfit.`dwi_file`
   - `bvec_corrected` → DTIfit.`bvec_file`
   - `bval_file` → DTIfit.`bval_file`

2. Connect Brain Mask output:
   - `mask_file` → DTIfit.`mask_file`

3. Configure DTIfit:
   - Set `output_basename` (default: "dti")
   - Enable `save_tensor` if needed for advanced analysis
   - Enable `output_sse` for quality control

4. Connect DTIfit outputs:
   - `fa_map` → NIfTI Preview (visualize FA)
   - `fa_map` → TBSS FA Collector (group analysis)
   - `v1_map` → Tractography (fiber directions)

## Differences from Existing `DWITensorFitting` Node

| Feature | Old `DWITensorFitting` | New `DTIfit` |
|---------|------------------------|--------------|
| FSL implementation | Basic dtifit | Full dtifit with all options |
| Outputs | FA, MD, AD, RD, tensor | FA, MD, MO, S0, L1/L2/L3, V1/V2/V3, tensor, SSE |
| Weighted LS | No | Yes (`--wls`) |
| SSE output | No | Yes (`--sse`) |
| Gradient nonlinearity | No | Yes (`--gradnonlin`) |
| Confound regressors | No | Yes (`--cni`) |
| MRtrix3 support | Yes (dwi2tensor) | No (FSL only) |
| Documentation | Minimal | Comprehensive (DTIFIT_NODE_GUIDE.md) |

**Recommendation:** Use new `DTIfit` node for standard FSL-based DTI analysis. Keep old `DWITensorFitting` for MRtrix3 workflows.

## Testing

To test the node:
1. Refresh ComfyUI
2. Look for "DTIfit (FSL)" in the node menu under DWI category
3. Connect eddy-corrected DWI and brain mask
4. Run workflow
5. Check console for `[DWI DTIfit]` messages
6. Verify outputs in `derivatives/diffyui/{subject}/dwi/DTI/`

## Documentation

- **User Guide**: `custom_nodes/dwi_nodes/DTIFIT_NODE_GUIDE.md`
- **FSL Reference**: https://fsl.fmrib.ox.ac.uk/fsl/docs/diffusion/dtifit.html
- **README**: Updated with DTIfit node description

## Status

✅ Node implemented  
✅ Registered in `__init__.py`  
✅ User guide created  
✅ README updated  
✅ No linter errors  
✅ Ready for testing
