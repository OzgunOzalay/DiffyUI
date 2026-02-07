"""
DWI Bias Correction Node - Third node in the pipeline.
Uses ANTs N4BiasFieldCorrection for bias field correction.
"""

import os
import sys
from pathlib import Path

# Import utils using helper module
from ._import_utils import BIDSHandler, get_executor, FileManager


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
    DESCRIPTION = "Bias field correction using ANTs N4BiasFieldCorrection"
    
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

            # BIDS output path: use bids_dataset/subject_id if both provided, else infer from path (same as Eddy/Topup)
            if bids_dataset and str(bids_dataset).strip() and subject_id and str(subject_id).strip():
                bids = BIDSHandler(str(bids_dataset).strip())
                derivatives_path = bids.get_derivatives_path(str(subject_id).strip(), "diffyui")
                output_dir = derivatives_path / "dwi" if "dwi" in str(input_path) else derivatives_path / "anat"
            else:
                path_parts = input_path.parts
                inf_subject_id = None
                inf_bids_root = None
                if "derivatives" in path_parts:
                    deriv_idx = path_parts.index("derivatives")
                    if deriv_idx > 0:
                        inf_bids_root = Path(*path_parts[:deriv_idx])
                        for i in range(deriv_idx - 1, -1, -1):
                            if path_parts[i].startswith("sub-"):
                                inf_subject_id = path_parts[i]
                                break
                else:
                    for i, part in enumerate(path_parts):
                        if part.startswith("sub-"):
                            inf_subject_id = part
                            if i > 0:
                                inf_bids_root = Path(*path_parts[:i])
                            break
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
            
            # Get system executor for ANTs
            executor = get_executor("ants")
            
            # Prepare N4BiasFieldCorrection command
            n4_cmd = [
                "N4BiasFieldCorrection",
                "-d", "3",  # 3D image
                "-i", str(input_path),
                "-o", str(corrected_output),
                "-s", str(shrink_factor),
                "-c", convergence,
                "-b", f"[{spline_distance}]"
            ]
            
            if mask_file and Path(mask_file).exists():
                n4_cmd.extend(["-x", str(mask_file)])
            
            return_code, stdout, stderr = executor.execute(n4_cmd)
            
            if return_code != 0:
                raise RuntimeError(f"N4BiasFieldCorrection failed: {stderr}")
            
            # Extract bias field (N4 outputs both corrected image and bias field)
            # The bias field is typically saved with a suffix
            bias_field_path = corrected_output.parent / f"{input_stem}_bias_field.nii.gz"
            
            # Write metadata
            metadata = {
                "ProcessingStep": "bias_correction",
                "Tool": "ANTs N4BiasFieldCorrection",
                "ShrinkFactor": shrink_factor,
                "Convergence": convergence,
                "SplineDistance": spline_distance
            }
            bids.write_derivative_file(corrected_output, input_path, metadata)
            
            return (str(corrected_output), str(bias_field_path))
        
        except Exception as e:
            return (f"Error: {str(e)}", "")
