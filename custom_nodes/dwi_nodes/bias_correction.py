"""
DWI Bias Correction Node - Third node in the pipeline.
Uses ANTs N4BiasFieldCorrection for bias field correction.
"""

import os
import sys
from pathlib import Path

# Import utils using helper module
from ._import_utils import BIDSHandler, get_executor, FileManager, CacheManager


class DWIBiasCorrectionNode:
    """
    DWI Bias Correction Node using ANTs N4BiasFieldCorrection.
    This is the THIRD node in the DWI processing pipeline.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bids_dataset": ("STRING", {
                    "default": "",
                    "tooltip": "BIDS dataset root (optional; inferred from input path if empty)"
                }),
                "subject_id": ("STRING", {
                    "default": "",
                    "tooltip": "Subject ID (optional; inferred from input path if empty)"
                }),
                "input_file": ("STRING", {
                    "default": "",
                    "tooltip": "Input DWI or T1 file path"
                }),
            },
            "optional": {
                "shrink_factor": ("INT", {
                    "default": 4,
                    "min": 1,
                    "max": 8,
                    "tooltip": "Shrink factor for multi-resolution approach"
                }),
                "convergence": ("STRING", {
                    "default": "[50x50x50x50,0.0000001]",
                    "tooltip": "Convergence parameters [iterations,threshold]"
                }),
                "spline_distance": ("INT", {
                    "default": 200,
                    "min": 50,
                    "max": 400,
                    "tooltip": "Distance between spline control points"
                }),
                "mask_file": ("STRING", {
                    "default": "",
                    "tooltip": "Optional mask file"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("bias_corrected", "bias_field")
    FUNCTION = "bias_correct"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = "Bias field correction using ANTs N4BiasFieldCorrection"

    @classmethod
    def IS_CHANGED(cls, bids_dataset, subject_id, input_file,
                   shrink_factor=4, convergence="[50x50x50x50,0.0000001]",
                   spline_distance=200, mask_file=""):
        """Re-run only when inputs actually change."""
        try:
            from ._import_utils import CacheManager
            params = CacheManager.build_params_for_hash(
                kwargs={
                    "bids_dataset": bids_dataset, "subject_id": subject_id,
                    "input_file": input_file, "shrink_factor": shrink_factor,
                    "convergence": convergence, "spline_distance": spline_distance,
                    "mask_file": mask_file,
                },
                file_keys=["input_file", "mask_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def bias_correct(self, bids_dataset, subject_id, input_file,
                     shrink_factor=4, convergence="[50x50x50x50,0.0000001]",
                     spline_distance=200, mask_file=""):
        """
        Perform bias field correction.
        
        Args:
            bids_dataset: Path to BIDS dataset
            subject_id: Subject ID
            input_file: Input file path
            shrink_factor: Shrink factor
            convergence: Convergence parameters
            spline_distance: Spline distance
            mask_file: Optional mask file
            
        Returns:
            Tuple of (bias_corrected_path, bias_field_path)
        """
        try:
            input_path = Path(input_file)
            if not input_path.exists():
                raise ValueError(f"Input file not found: {input_file}")

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={
                    "bids_dataset": bids_dataset, "subject_id": subject_id,
                    "input_file": input_file, "shrink_factor": shrink_factor,
                    "convergence": convergence, "spline_distance": spline_distance,
                    "mask_file": mask_file,
                },
                file_keys=["input_file", "mask_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            # BIDS output path: use bids_dataset/subject_id if both provided, else infer from path (same as Eddy/Topup)
            if bids_dataset and str(bids_dataset).strip() and subject_id and str(subject_id).strip():
                bids = BIDSHandler(str(bids_dataset).strip())
                derivatives_path = bids.get_derivatives_path(str(subject_id).strip(), "diffyui")
                output_dir = derivatives_path / "dwi" if "dwi" in str(input_path) else derivatives_path / "anat"
            else:
                inf_bids_root, inf_subject_id = BIDSHandler.infer_bids_paths(input_path)
                if inf_subject_id and inf_bids_root:
                    bids = BIDSHandler(str(inf_bids_root))
                    derivatives_path = bids.get_derivatives_path(inf_subject_id, "diffyui")
                    output_dir = derivatives_path / "dwi" if "dwi" in str(input_path) else derivatives_path / "anat"
                else:
                    bids = BIDSHandler(str(input_path.parent))
                    output_dir = input_path.parent / "BiasCorrected"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare output files
            input_stem = input_path.stem.replace(".nii", "")
            corrected_output = output_dir / f"{input_stem}_bias_corrected.nii.gz"
            bias_field_output = output_dir / f"{input_stem}_bias_field.nii.gz"

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(corrected_output), str(bias_field_output)]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "DWIBiasCorrection", _param_hash, _expected)
            if _is_hit:
                print("[DWI Bias Correction] Cache hit — skipping.")
                return tuple(_cached)

            # Get system executor for ANTs
            executor = get_executor("ants")
            
            # Prepare N4BiasFieldCorrection command
            # Use bracket notation for -o to output both corrected image and bias field
            n4_cmd = [
                "N4BiasFieldCorrection",
                "-d", "3",  # 3D image
                "-i", str(input_path),
                "-o", f"[{corrected_output},{bias_field_output}]",
                "-s", str(shrink_factor),
                "-c", convergence,
                "-b", f"[{spline_distance}]"
            ]
            
            if mask_file and Path(mask_file).exists():
                n4_cmd.extend(["-x", str(mask_file)])
            
            return_code, stdout, stderr = executor.execute(n4_cmd)
            
            if return_code != 0:
                raise RuntimeError(f"N4BiasFieldCorrection failed: {stderr}")

            # Write metadata
            metadata = {
                "ProcessingStep": "bias_correction",
                "Tool": "ANTs N4BiasFieldCorrection",
                "ShrinkFactor": shrink_factor,
                "Convergence": convergence,
                "SplineDistance": spline_distance
            }
            bids.write_derivative_file(corrected_output, input_path, metadata)

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "DWIBiasCorrection", _param_hash, _params, _expected)

            return (str(corrected_output), str(bias_field_output))
        
        except Exception as e:
            return (f"Error: {str(e)}", "")
