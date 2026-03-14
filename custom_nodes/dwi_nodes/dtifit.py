"""
FSL DTIFIT Node - Diffusion tensor fitting.
Fits a diffusion tensor model at each voxel using FSL dtifit.
Based on: https://fsl.fmrib.ox.ac.uk/fsl/docs/diffusion/dtifit.html
"""

import os
from pathlib import Path

from ._import_utils import BIDSHandler, get_executor

print("[DWI DTIfit] ===== MODULE LOADING =====")


class DTIfitNode:
    """
    FSL DTIFIT Node for diffusion tensor model fitting.
    Outputs: FA, MD, MO, L1/L2/L3, V1/V2/V3, S0, and optional SSE/tensor.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "Diffusion weighted data (4D NIfTI). Connect from Eddy → dwi_corrected or provide path."
                }),
                "mask_file": ("STRING", {
                    "default": "",
                    "tooltip": "Brain mask (3D NIfTI). Connect from Brain Mask → mask_file or provide path."
                }),
                "bvec_file": ("STRING", {
                    "default": "",
                    "tooltip": "Gradient directions file (bvecs). Connect from Eddy → bvec_corrected or provide path."
                }),
                "bval_file": ("STRING", {
                    "default": "",
                    "tooltip": "B-values file (bvals). Usually same as input (not rotated by eddy)."
                }),
            },
            "optional": {
                "output_basename": ("STRING", {
                    "default": "dti",
                    "tooltip": "Output basename (e.g. 'dti' produces dti_FA.nii.gz, dti_MD.nii.gz, etc.)"
                }),
                "weighted_ls": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Use weighted least squares (--wls) instead of standard linear regression"
                }),
                "save_tensor": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Save tensor elements as 4D file (--save_tensor): Dxx,Dxy,Dxz,Dyy,Dyz,Dzz"
                }),
                "output_sse": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Output sum of squared errors (--sse) for artifact detection"
                }),
                "confound_regressors": ("STRING", {
                    "default": "",
                    "tooltip": "Optional confound regressors file (--cni)"
                }),
                "gradnonlin_file": ("STRING", {
                    "default": "",
                    "tooltip": "Optional gradient nonlinearity tensor file (--gradnonlin)"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("fa_map", "md_map", "output_dir", "l1_map", "v1_map", "tensor_file", "all_outputs")
    FUNCTION = "run_dtifit"
    CATEGORY = "DWI"
    DESCRIPTION = "FSL dtifit: Fit diffusion tensor model at each voxel. Outputs FA, MD, L1/L2/L3, V1/V2/V3, MO, S0. Requires eddy-corrected DWI, mask, bvecs, bvals."
    
    def run_dtifit(self, dwi_file: str, mask_file: str, bvec_file: str, bval_file: str,
                   output_basename: str = "dti", weighted_ls: bool = False, save_tensor: bool = True,
                   output_sse: bool = False, confound_regressors: str = "", gradnonlin_file: str = ""):
        """
        Run FSL dtifit to fit diffusion tensor model.
        
        Args:
            dwi_file: Diffusion weighted data (4D NIfTI)
            mask_file: Brain mask (3D binary NIfTI)
            bvec_file: Gradient directions (bvecs)
            bval_file: B-values (bvals)
            output_basename: Output basename (default: dti)
            weighted_ls: Use weighted least squares
            save_tensor: Save tensor elements
            output_sse: Output sum of squared errors
            confound_regressors: Optional confound regressors file
            gradnonlin_file: Optional gradient nonlinearity tensor file
            
        Returns:
            Tuple of (fa_map, md_map, output_dir, l1_map, v1_map, tensor_file, all_outputs)
        """
        try:
            # Validate inputs
            dwi_path = Path(dwi_file.strip())
            mask_path = Path(mask_file.strip())
            bvec_path = Path(bvec_file.strip())
            bval_path = Path(bval_file.strip())
            
            if not dwi_path.exists():
                return (f"Error: DWI file not found: {dwi_file}",) * 7
            if not mask_path.exists():
                return (f"Error: Mask file not found: {mask_file}",) * 7
            if not bvec_path.exists():
                return (f"Error: Bvec file not found: {bvec_file}",) * 7
            if not bval_path.exists():
                return (f"Error: Bval file not found: {bval_file}",) * 7
            
            print(f"[DWI DTIfit] DWI input: {dwi_path}")
            print(f"[DWI DTIfit] Mask: {mask_path}")
            print(f"[DWI DTIfit] Bvecs: {bvec_path}")
            print(f"[DWI DTIfit] Bvals: {bval_path}")
            
            # Determine output directory (same as other nodes: infer from DWI path or use derivatives)
            path_parts = dwi_path.parts
            subject_id = None
            bids_root = None
            if "derivatives" in path_parts:
                deriv_idx = path_parts.index("derivatives")
                if deriv_idx > 0:
                    bids_root = Path(*path_parts[:deriv_idx])
                    for i in range(len(path_parts) - 1, -1, -1):
                        if path_parts[i].startswith("sub-"):
                            subject_id = path_parts[i]
                            break
            else:
                for i, part in enumerate(path_parts):
                    if part.startswith("sub-"):
                        subject_id = part
                        if i > 0:
                            bids_root = Path(*path_parts[:i])
                        break
            
            if not subject_id or not bids_root:
                output_dir = dwi_path.parent / "DTI"
            else:
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi" / "DTI"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[DWI DTIfit] Output directory: {output_dir}")
            
            # Full output path with basename
            output_prefix = output_dir / output_basename
            print(f"[DWI DTIfit] Output basename: {output_prefix}")
            
            # Build dtifit command
            dtifit_cmd = [
                "dtifit",
                f"--data={dwi_path}",
                f"--mask={mask_path}",
                f"--bvecs={bvec_path}",
                f"--bvals={bval_path}",
                f"--out={output_prefix}",
            ]
            
            # Optional flags
            if weighted_ls:
                dtifit_cmd.append("--wls")
                print("[DWI DTIfit] Using weighted least squares (--wls)")
            
            if save_tensor:
                dtifit_cmd.append("--save_tensor")
                print("[DWI DTIfit] Saving tensor elements (--save_tensor)")
            
            if output_sse:
                dtifit_cmd.append("--sse")
                print("[DWI DTIfit] Outputting sum of squared errors (--sse)")
            
            if confound_regressors and Path(confound_regressors.strip()).exists():
                dtifit_cmd.append(f"--cni={confound_regressors.strip()}")
                print(f"[DWI DTIfit] Using confound regressors: {confound_regressors.strip()}")
            
            if gradnonlin_file and Path(gradnonlin_file.strip()).exists():
                dtifit_cmd.append(f"--gradnonlin={gradnonlin_file.strip()}")
                print(f"[DWI DTIfit] Using gradient nonlinearity file: {gradnonlin_file.strip()}")
            
            print(f"[DWI DTIfit] Running: {' '.join(dtifit_cmd)}")
            
            # Execute dtifit
            executor = get_executor("fsl")
            return_code, stdout, stderr = executor.execute(
                dtifit_cmd,
                working_dir=str(output_dir),
            )
            
            if return_code != 0:
                error_msg = f"dtifit failed (exit code {return_code}): {stderr}"
                if stdout:
                    error_msg += f"\nStdout: {stdout}"
                print(f"[DWI DTIfit] ERROR: {error_msg}")
                return (f"Error: {error_msg}",) * 7
            
            print(f"[DWI DTIfit] dtifit completed successfully")
            
            # Output files (FSL dtifit standard naming)
            fa_map = str(output_prefix) + "_FA.nii.gz"
            md_map = str(output_prefix) + "_MD.nii.gz"
            mo_map = str(output_prefix) + "_MO.nii.gz"
            s0_map = str(output_prefix) + "_S0.nii.gz"
            l1_map = str(output_prefix) + "_L1.nii.gz"
            l2_map = str(output_prefix) + "_L2.nii.gz"
            l3_map = str(output_prefix) + "_L3.nii.gz"
            v1_map = str(output_prefix) + "_V1.nii.gz"
            v2_map = str(output_prefix) + "_V2.nii.gz"
            v3_map = str(output_prefix) + "_V3.nii.gz"
            tensor_file = str(output_prefix) + "_tensor.nii.gz" if save_tensor else ""
            sse_file = str(output_prefix) + "_sse.nii.gz" if output_sse else ""
            
            # Verify key outputs exist
            if not Path(fa_map).exists():
                error_msg = f"dtifit completed but FA output not found: {fa_map}"
                print(f"[DWI DTIfit] ERROR: {error_msg}")
                return (f"Error: {error_msg}",) * 7
            
            print(f"[DWI DTIfit] FA map: {fa_map}")
            print(f"[DWI DTIfit] MD map: {md_map}")
            print(f"[DWI DTIfit] L1 (AD) map: {l1_map}")
            print(f"[DWI DTIfit] V1 (primary eigenvector): {v1_map}")
            if tensor_file and Path(tensor_file).exists():
                print(f"[DWI DTIfit] Tensor: {tensor_file}")
            
            # Summary of all outputs for downstream nodes
            all_outputs = (
                f"FA: {fa_map}\n"
                f"MD: {md_map}\n"
                f"MO: {mo_map}\n"
                f"S0: {s0_map}\n"
                f"L1: {l1_map}\n"
                f"L2: {l2_map}\n"
                f"L3: {l3_map}\n"
                f"V1: {v1_map}\n"
                f"V2: {v2_map}\n"
                f"V3: {v3_map}"
            )
            if tensor_file:
                all_outputs += f"\nTensor: {tensor_file}"
            if sse_file:
                all_outputs += f"\nSSE: {sse_file}"
            
            return (fa_map, md_map, str(output_dir), l1_map, v1_map, tensor_file, all_outputs)
        
        except Exception as e:
            error_msg = f"Exception in DTIfit node: {str(e)}"
            print(f"[DWI DTIfit] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return (f"Error: {error_msg}",) * 7
