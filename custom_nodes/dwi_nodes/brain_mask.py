"""
DWI Brain Mask Extraction Node
Extracts b0 volume from DWI data and creates brain mask using FSL BET.
"""

import os
import sys
from pathlib import Path

# Import utils using helper module
from ._import_utils import get_executor, CacheManager


class DWIBrainMaskNode:
    """
    DWI Brain Mask Extraction Node using FSL BET.
    Extracts the first volume (b0) from DWI data and creates a brain mask.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "DWI file path (full path to NIfTI file)"
                }),
            },
            "optional": {
                "fractional_intensity": ("FLOAT", {
                    "default": 0.2,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "Fractional intensity threshold (0-1). Smaller values give larger brain outline estimates. Default: 0.2 (recommended for DWI)"
                }),
                "vertical_gradient": ("FLOAT", {
                    "default": 0.0,
                    "min": -1.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "Vertical gradient in fractional intensity threshold (-1 to 1). Positive values give larger brain outline at bottom, negative at top. Default: 0.0"
                }),
                "radius": ("INT", {
                    "default": 45,
                    "min": 1,
                    "max": 200,
                    "tooltip": "Head radius (mm). Used to estimate brain size. Default: 45"
                }),
                "center_of_gravity": ("STRING", {
                    "default": "",
                    "tooltip": "Center of gravity (x y z) in voxels. Leave empty for auto-detection. Format: 'x y z'"
                }),
                "robust": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Robust brain center estimation (not available in FSL 6.0.4, kept for compatibility)"
                }),
                "reduce_bias": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Bias field and neck cleanup (use -B option in BET)"
                }),
                "output_brain": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Output extracted brain image in addition to mask"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("brain_mask", "extracted_brain")
    FUNCTION = "extract_mask"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = "Extract brain mask from DWI data using FSL BET. Extracts b0 volume and creates binary brain mask."

    @classmethod
    def IS_CHANGED(cls, dwi_file="", fractional_intensity=0.2, vertical_gradient=0.0,
                   radius=45, center_of_gravity="", robust=True, reduce_bias=False,
                   output_brain=False, **kwargs):
        """Re-run only when inputs actually change."""
        try:
            from ._import_utils import CacheManager
            params = CacheManager.build_params_for_hash(
                kwargs={
                    "dwi_file": dwi_file, "fractional_intensity": fractional_intensity,
                    "vertical_gradient": vertical_gradient, "radius": radius,
                    "center_of_gravity": center_of_gravity, "robust": robust,
                    "reduce_bias": reduce_bias, "output_brain": output_brain,
                },
                file_keys=["dwi_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def extract_mask(
        self,
        dwi_file: str,
        fractional_intensity: float = 0.5,
        vertical_gradient: float = 0.0,
        radius: int = 45,
        center_of_gravity: str = "",
        robust: bool = True,
        reduce_bias: bool = False,
        output_brain: bool = False
    ):
        """
        Extract brain mask from DWI data using FSL BET.
        
        Process:
        1. Extract first volume (b0) from DWI file using fslroi
        2. Run BET on b0 image to create brain mask
        
        Args:
            dwi_file: Full path to DWI NIfTI file
            fractional_intensity: Fractional intensity threshold (0-1)
            vertical_gradient: Vertical gradient in fractional intensity threshold
            radius: Head radius (mm)
            center_of_gravity: Center of gravity (x y z) in voxels, empty for auto
            robust: Robust brain center estimation
            reduce_bias: Bias field and neck cleanup
            output_brain: Output extracted brain image
            
        Returns:
            Tuple of (brain_mask_path, extracted_brain_path)
        """
        try:
            # Validate input file
            input_dwi = Path(dwi_file)
            if not input_dwi.exists():
                raise ValueError(f"DWI file not found: {dwi_file}")
            
            if not input_dwi.is_file():
                raise ValueError(f"Path is not a file: {dwi_file}")

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={
                    "dwi_file": dwi_file, "fractional_intensity": fractional_intensity,
                    "vertical_gradient": vertical_gradient, "radius": radius,
                    "center_of_gravity": center_of_gravity, "robust": robust,
                    "reduce_bias": reduce_bias, "output_brain": output_brain,
                },
                file_keys=["dwi_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            print(f"[DWI Brain Mask] Input DWI file: {input_dwi}")
            
            # Infer BIDS structure from input file path for output location
            from ._import_utils import BIDSHandler
            bids_root, subject_id = BIDSHandler.infer_bids_paths(input_dwi)
            if not subject_id or not bids_root:
                output_dir = input_dwi.parent / "Mask"
            else:
                from ._import_utils import BIDSHandler
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[DWI Brain Mask] Output directory: {output_dir}")
            
            # Prepare output file names
            # Output files will be written directly to the derivatives folder
            input_stem = input_dwi.stem.replace(".nii", "").replace(".gz", "")
            
            # Output locations in derivatives folder
            b0_output = output_dir / f"{input_stem}_b0.nii.gz"
            mask_output = output_dir / f"{input_stem}_brain_mask.nii.gz"
            brain_output = output_dir / f"{input_stem}_brain.nii.gz" if output_brain else None

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(mask_output), str(brain_output) if brain_output else ""]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "DWIBrainMask", _param_hash, _expected)
            if _is_hit:
                print("[DWI Brain Mask] Cache hit — skipping.")
                return tuple(_cached)

            # Get system executor for FSL
            executor = get_executor("fsl")
            
            print(f"[DWI Brain Mask] Input DWI: {input_dwi}")
            print(f"[DWI Brain Mask] Output directory: {output_dir}")
            
            # Step 1: Extract first volume (b0) using fslroi — skip if already on disk
            # (ExtractB0 node writes to the same derivatives/dwi path, so avoid running twice)
            if b0_output.exists():
                print(f"[DWI Brain Mask] b0 already exists, reusing: {b0_output}")
            else:
                print(f"[DWI Brain Mask] Extracting b0 volume...")
                fslroi_cmd = [
                    "fslroi",
                    str(input_dwi),
                    str(b0_output),
                    "0",  # tmin: start at volume 0
                    "1"   # tsize: extract 1 volume
                ]
                return_code, stdout, stderr = executor.execute(fslroi_cmd)
                if return_code != 0:
                    raise RuntimeError(f"fslroi failed: {stderr}")
                import time
                time.sleep(0.5)
                if not b0_output.exists():
                    raise RuntimeError(f"b0 extraction failed: output file not found: {b0_output}")
                print(f"[DWI Brain Mask] b0 volume extracted: {b0_output}")
            
            # Step 2: Run BET on b0 image
            # BET creates: <output>.nii.gz (brain) and <output>_mask.nii.gz (mask)
            bet_output_base = output_dir / f"{input_stem}_brain"
            
            print(f"[DWI Brain Mask] Running BET on b0 image...")
            print(f"[DWI Brain Mask] BET input: {b0_output}")
            print(f"[DWI Brain Mask] BET output base: {bet_output_base}")
            
            # Build BET command matching user's script: bet input output -m -f 0.2
            # Use 'bet' instead of 'bet2' to match user's script (they're typically aliases)
            bet_cmd = [
                "bet",
                str(b0_output),
                str(bet_output_base),
                "-m",  # Generate binary brain mask
                "-f", str(fractional_intensity)
            ]
            
            # Add optional parameters only if they differ from defaults
            if vertical_gradient != 0.0:
                bet_cmd.extend(["-g", str(vertical_gradient)])
            
            if radius != 45:  # Only add if not default
                bet_cmd.extend(["-r", str(radius)])
            
            if center_of_gravity and center_of_gravity.strip():
                # Parse center of gravity (x y z)
                try:
                    cog_parts = center_of_gravity.strip().split()
                    if len(cog_parts) == 3:
                        bet_cmd.extend(["-c", cog_parts[0], cog_parts[1], cog_parts[2]])
                    else:
                        print(f"Warning: Invalid center of gravity format: {center_of_gravity}. Using auto-detection.")
                except Exception as e:
                    print(f"Warning: Could not parse center of gravity: {e}. Using auto-detection.")
            
            # Note: -R flag for robust brain center estimation is not available in FSL 6.0.4
            # The robust parameter is kept for API compatibility but not used
            # if robust:
            #     bet_cmd.append("-R")  # Not supported in FSL 6.0.4
            
            if reduce_bias:
                bet_cmd.append("-B")  # Bias field and neck cleanup
            
            return_code, stdout, stderr = executor.execute(bet_cmd)
            if return_code != 0:
                raise RuntimeError(f"BET failed: {stderr}")
            
            # BET with -m flag creates: <output>_mask.nii.gz
            # Find the actual mask file
            import time
            time.sleep(0.5)
            
            # BET creates mask as <output>_mask.nii.gz
            bet_output_path = Path(bet_output_base)
            actual_mask = bet_output_path.parent / f"{bet_output_path.name}_mask.nii.gz"
            
            if not actual_mask.exists():
                # Try one more time after additional wait
                time.sleep(0.5)
                if not actual_mask.exists():
                    raise RuntimeError(f"BET mask not found. Expected at: {actual_mask}")
            
            # Copy mask to expected location if different
            if actual_mask != mask_output:
                import shutil
                shutil.copy2(actual_mask, mask_output)
                print(f"[DWI Brain Mask] Mask copied to: {mask_output}")
            else:
                print(f"[DWI Brain Mask] Mask created at: {mask_output}")
            
            # Handle brain image if requested
            extracted_brain_path = ""
            if output_brain:
                brain_file = bet_output_path.parent / f"{bet_output_path.name}.nii.gz"
                if brain_file.exists():
                    if brain_file != brain_output:
                        import shutil
                        shutil.copy2(brain_file, brain_output)
                    extracted_brain_path = str(brain_output)
                    print(f"[DWI Brain Mask] Brain image saved: {brain_output}")
            
            print(f"[DWI Brain Mask] Brain mask created: {mask_output}")

            # ── Block 3: update cache ──
            _result_paths = [str(mask_output), extracted_brain_path]
            CacheManager.update_cache(_cache_path, "DWIBrainMask", _param_hash, _params, _result_paths)

            # Return paths
            return (str(mask_output), extracted_brain_path)
        
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"[DWI Brain Mask] {error_msg}")
            return (error_msg, "")
