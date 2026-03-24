"""
FSL DTIFIT Node - Diffusion tensor fitting.
Fits a diffusion tensor model at each voxel using FSL dtifit.
Based on: https://fsl.fmrib.ox.ac.uk/fsl/docs/diffusion/dtifit.html
"""

import os
from pathlib import Path

from ._import_utils import BIDSHandler, get_executor, CacheManager

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
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("fa_map", "v1_map", "md_map", "mo_map", "s0_map", "l1_map", "l2_map", "l3_map", "v2_map", "v3_map", "fa_directory")
    FUNCTION = "run_dtifit"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = "FSL dtifit: Fit diffusion tensor model at each voxel. Outputs FA, V1-V3, MD, MO, S0, L1-L3. Requires eddy-corrected DWI, mask, bvecs, bvals."

    @classmethod
    def IS_CHANGED(cls, dwi_file="", mask_file="", bvec_file="", bval_file="",
                   output_basename="dti", weighted_ls=False, save_tensor=True,
                   output_sse=False, confound_regressors="", gradnonlin_file="", **kwargs):
        """Re-run only when inputs actually change."""
        try:
            from ._import_utils import CacheManager
            params = CacheManager.build_params_for_hash(
                kwargs={
                    "dwi_file": dwi_file, "mask_file": mask_file,
                    "bvec_file": bvec_file, "bval_file": bval_file,
                    "output_basename": output_basename, "weighted_ls": weighted_ls,
                    "save_tensor": save_tensor, "output_sse": output_sse,
                },
                file_keys=["dwi_file", "mask_file", "bvec_file", "bval_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def run_dtifit(self, dwi_file: str, mask_file: str, bvec_file: str, bval_file: str,
                   output_basename: str = "dti", weighted_ls: bool = False, save_tensor: bool = True,
                   output_sse: bool = False, confound_regressors: str = "", gradnonlin_file: str = ""):
        """
        Run FSL dtifit to fit diffusion tensor model.

        Returns:
            Tuple of (fa_map, v1_map, md_map, mo_map, s0_map, l1_map, l2_map, l3_map, v2_map, v3_map, fa_directory)
        """
        _N = 11  # number of return values
        try:
            # Validate inputs
            dwi_path = Path(dwi_file.strip())
            mask_path = Path(mask_file.strip())
            bvec_path = Path(bvec_file.strip())
            bval_path = Path(bval_file.strip())

            if not dwi_path.exists():
                return (f"Error: DWI file not found: {dwi_file}",) * _N
            if not mask_path.exists():
                return (f"Error: Mask file not found: {mask_file}",) * _N
            if not bvec_path.exists():
                return (f"Error: Bvec file not found: {bvec_file}",) * _N
            if not bval_path.exists():
                return (f"Error: Bval file not found: {bval_file}",) * _N

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={
                    "dwi_file": dwi_file, "mask_file": mask_file,
                    "bvec_file": bvec_file, "bval_file": bval_file,
                    "output_basename": output_basename, "weighted_ls": weighted_ls,
                    "save_tensor": save_tensor, "output_sse": output_sse,
                },
                file_keys=["dwi_file", "mask_file", "bvec_file", "bval_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            print(f"[DWI DTIfit] DWI input: {dwi_path}")
            print(f"[DWI DTIfit] Mask: {mask_path}")
            print(f"[DWI DTIfit] Bvecs: {bvec_path}")
            print(f"[DWI DTIfit] Bvals: {bval_path}")

            # Determine output directory using centralized BIDS path inference
            bids_root, subject_id = BIDSHandler.infer_bids_paths(dwi_path)
            if not subject_id or not bids_root:
                output_dir = dwi_path.parent / "DTI"
            else:
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi" / "DTI"

            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[DWI DTIfit] Output directory: {output_dir}")

            output_prefix = output_dir / output_basename

            # Pre-compute all standard output paths
            def _p(suffix): return str(output_prefix) + suffix

            fa_map  = _p("_FA.nii.gz")
            v1_map  = _p("_V1.nii.gz")
            md_map  = _p("_MD.nii.gz")
            mo_map  = _p("_MO.nii.gz")
            s0_map  = _p("_S0.nii.gz")
            l1_map  = _p("_L1.nii.gz")
            l2_map  = _p("_L2.nii.gz")
            l3_map  = _p("_L3.nii.gz")
            v2_map  = _p("_V2.nii.gz")
            v3_map  = _p("_V3.nii.gz")

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected_cache = [fa_map, v1_map, md_map, mo_map, s0_map,
                               l1_map, l2_map, l3_map, v2_map, v3_map,
                               str(output_dir)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "DTIfit", _param_hash, _expected_cache,
                files_to_check=[fa_map, v1_map, md_map],
            )
            if _is_hit:
                print("[DWI DTIfit] Cache hit — skipping.")
                return tuple(_cached)

            # Build dtifit command
            dtifit_cmd = [
                "dtifit",
                f"--data={dwi_path}",
                f"--mask={mask_path}",
                f"--bvecs={bvec_path}",
                f"--bvals={bval_path}",
                f"--out={output_prefix}",
            ]

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
            if gradnonlin_file and Path(gradnonlin_file.strip()).exists():
                dtifit_cmd.append(f"--gradnonlin={gradnonlin_file.strip()}")

            print(f"[DWI DTIfit] Running: {' '.join(dtifit_cmd)}")

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
                return (f"Error: {error_msg}",) * _N

            print(f"[DWI DTIfit] dtifit completed successfully")

            if not Path(fa_map).exists():
                error_msg = f"dtifit completed but FA output not found: {fa_map}"
                print(f"[DWI DTIfit] ERROR: {error_msg}")
                return (f"Error: {error_msg}",) * _N

            print(f"[DWI DTIfit] FA: {fa_map}")
            print(f"[DWI DTIfit] V1: {v1_map}")
            print(f"[DWI DTIfit] MD: {md_map}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "DTIfit", _param_hash, _params, _expected_cache)

            return (fa_map, v1_map, md_map, mo_map, s0_map, l1_map, l2_map, l3_map, v2_map, v3_map, str(output_dir))

        except Exception as e:
            error_msg = f"Exception in DTIfit node: {str(e)}"
            print(f"[DWI DTIfit] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return (f"Error: {error_msg}",) * _N
