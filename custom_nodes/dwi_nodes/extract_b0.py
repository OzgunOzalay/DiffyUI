"""
Extract B0 Node - Extracts the first volume (B0) from 4D DWI data.
Uses FSL fslroi to extract the first volume in the 4th dimension.
"""

import os
import sys
from pathlib import Path

# Import utils using helper module
from ._import_utils import get_executor

print("[Extract B0] ===== MODULE LOADING =====")


class ExtractB0Node:
    """
    Extract B0 Node using FSL fslroi.
    Extracts the first volume (B0) from 4D DWI data.
    """
    
    def __init__(self):
        print("[Extract B0] Node instance created!")
    
    @classmethod
    def INPUT_TYPES(cls):
        print("[Extract B0] INPUT_TYPES called")
        return {
            "required": {
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "4D DWI file path (NIfTI format)"
                }),
            },
            "optional": {
                "volume_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 1000,
                    "tooltip": "Volume index to extract (0 = first volume, typically B0)"
                }),
                "num_volumes": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 100,
                    "tooltip": "Number of volumes to extract (default: 1)"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("b0_file",)
    FUNCTION = "extract_b0"
    CATEGORY = "DWI"
    DESCRIPTION = "Extract B0 volume (first volume) from 4D DWI data using FSL fslroi."
    
    @classmethod
    def IS_CHANGED(cls, dwi_file, **kwargs):
        """Force re-execution when inputs change."""
        import time
        return str(time.time())
    
    def extract_b0(
        self,
        dwi_file: str,
        volume_index: int = 0,
        num_volumes: int = 1
    ):
        """
        Extract B0 volume from 4D DWI data using FSL fslroi.
        
        Command: fslroi dwi.nii out_b0 <volume_index> <num_volumes>
        
        Args:
            dwi_file: Full path to 4D DWI NIfTI file
            volume_index: Volume index to extract (0 = first volume)
            num_volumes: Number of volumes to extract
            
        Returns:
            Tuple of (b0_file_path,)
        """
        print(f"[Extract B0] ===== FUNCTION CALLED =====")
        print(f"[Extract B0] dwi_file: {repr(dwi_file)}")
        print(f"[Extract B0] volume_index: {volume_index}, num_volumes: {num_volumes}")
        
        try:
            # Validate input file
            if not dwi_file or not isinstance(dwi_file, str) or not dwi_file.strip():
                error_msg = "DWI file path is required and cannot be empty"
                print(f"[Extract B0] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)
            
            input_dwi = Path(dwi_file.strip())
            if not input_dwi.exists():
                error_msg = f"DWI file not found: {dwi_file}"
                print(f"[Extract B0] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)
            
            if not input_dwi.is_file():
                error_msg = f"Path is not a file: {dwi_file}"
                print(f"[Extract B0] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)
            
            print(f"[Extract B0] Input DWI file: {input_dwi}")
            
            # Infer BIDS structure from input file path (same logic as Topup/Eddy nodes)
            path_parts = input_dwi.parts
            subject_id = None
            bids_root = None
            if "derivatives" in path_parts:
                deriv_idx = path_parts.index("derivatives")
                if deriv_idx > 0:
                    bids_root = Path(*path_parts[:deriv_idx])
                    for i in range(deriv_idx - 1, -1, -1):
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
                output_dir = input_dwi.parent / "B0"
            else:
                from ._import_utils import BIDSHandler
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[Extract B0] Output directory: {output_dir}")
            
            # Prepare output file name
            # Get the base name without .nii.gz or .nii extension
            input_name = input_dwi.name
            if input_name.endswith('.nii.gz'):
                input_stem = input_name[:-7]
            elif input_name.endswith('.nii'):
                input_stem = input_name[:-4]
            else:
                input_stem = input_dwi.stem
            
            # Create output filename
            if volume_index == 0 and num_volumes == 1:
                output_suffix = "_b0"
            else:
                output_suffix = f"_vol{volume_index}"
                if num_volumes > 1:
                    output_suffix += f"-{volume_index + num_volumes - 1}"
            
            b0_output = output_dir / f"{input_stem}{output_suffix}.nii.gz"
            
            # Get system executor for FSL
            executor = get_executor("fsl")
            
            print(f"[Extract B0] Input DWI: {input_dwi}")
            print(f"[Extract B0] Output B0: {b0_output}")
            
            # Run fslroi: fslroi input output tmin tsize
            # tmin = volume_index (0-based)
            # tsize = num_volumes
            fslroi_cmd = [
                "fslroi",
                str(input_dwi),
                str(b0_output),
                str(volume_index),  # tmin: start at this volume
                str(num_volumes)    # tsize: extract this many volumes
            ]
            
            print(f"[Extract B0] Running: {' '.join(fslroi_cmd)}")
            return_code, stdout, stderr = executor.execute(fslroi_cmd)
            
            if return_code != 0:
                error_msg = f"fslroi failed: {stderr}"
                print(f"[Extract B0] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)
            
            # Verify output exists
            import time
            time.sleep(0.5)  # Wait for file to be written
            
            if not b0_output.exists():
                error_msg = f"B0 output file not found: {b0_output}"
                print(f"[Extract B0] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)
            
            print(f"[Extract B0] B0 volume extracted successfully: {b0_output}")
            print(f"[Extract B0] ===== EXTRACTION COMPLETE =====")
            
            return (str(b0_output),)
        
        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            print(f"[Extract B0] {error_msg}")
            print(f"[Extract B0] Traceback: {traceback.format_exc()}")
            return (error_msg,)
