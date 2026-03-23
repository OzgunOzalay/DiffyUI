"""
DWI Denoising Node - First node in the pipeline.
Uses MRtrix3 dwidenoise for MP-PCA denoising.
"""

import os
import sys
from pathlib import Path

print("[DWI Denoise] ===== MODULE LOADING =====")

# Import utils using helper module
from ._import_utils import BIDSHandler, get_executor, FileManager, CacheManager

print("[DWI Denoise] Module imports successful")


class DWIDenoiseNode:
    """
    DWI Denoising Node using MRtrix3 dwidenoise.
    This is the FIRST node in the DWI processing pipeline.
    """
    
    def __init__(self):
        print("[DWI Denoise] Node instance created!")
    
    @classmethod
    def INPUT_TYPES(cls):
        try:
            print(f"[DWI Denoise] INPUT_TYPES called")
            result = {
                "required": {
                    "dwi_file": ("STRING", {
                        "default": "",
                        "tooltip": "DWI file path (full path to NIfTI file)"
                    }),
                },
                "optional": {
                    "mask_file": ("STRING", {
                        "default": "",
                        "tooltip": "Optional binary brain mask image. Only process voxels within mask."
                    }),
                    "extent": ("INT", {
                        "default": 0,
                        "min": 0,
                        "max": 15,
                        "tooltip": "Patch size of denoising filter (e.g., 5 for 5x5x5). Set to 0 for auto-selection"
                    }),
                    "output_noise_map": ("BOOLEAN", {
                        "default": True,
                        "tooltip": "Output noise map (estimated noise level 'sigma' in the data)"
                    }),
                    "rank_cutoff": ("INT", {
                        "default": 0,
                        "min": 0,
                        "tooltip": "Selected signal rank of the output denoised image. Set to 0 for auto"
                    }),
                    "datatype": (["auto", "float32", "float64"], {
                        "default": "auto",
                        "tooltip": "Datatype for eigenvalue decomposition"
                    }),
                    "estimator": (["Exp2", "Exp1"], {
                        "default": "Exp2",
                        "tooltip": "Noise level estimator: Exp2 (improved) or Exp1 (original)"
                    }),
                    "nthreads": ("INT", {
                        "default": 10,
                        "min": 0,
                        "max": 32,
                        "tooltip": "Number of threads (0 = use 10)"
                    }),
                    "force_overwrite": ("BOOLEAN", {
                        "default": False,
                        "tooltip": "Force overwrite of output files"
                    }),
                    "quiet": ("BOOLEAN", {
                        "default": False,
                        "tooltip": "Suppress information messages"
                    }),
                }
            }
            print(f"[DWI Denoise] INPUT_TYPES returning successfully")
            return result
        except Exception as e:
            print(f"[DWI Denoise] ERROR in INPUT_TYPES: {e}")
            import traceback
            print(f"[DWI Denoise] Traceback: {traceback.format_exc()}")
            # Return minimal valid structure on error
            return {
                "required": {
                    "dwi_file": ("STRING", {"default": ""}),
                },
                "optional": {}
            }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("denoised_dwi", "noise_map")
    FUNCTION = "denoise"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = "Denoise DWI data using MRtrix3 dwidenoise (Marchenko-Pastur PCA). Must be performed as the first step of the image processing pipeline."
    
    @classmethod
    def IS_CHANGED(cls, dwi_file, mask_file="", extent=0, output_noise_map=True,
                   rank_cutoff=0, datatype="auto", estimator="Exp2", nthreads=10,
                   force_overwrite=False, quiet=False):
        """Re-run only when inputs actually change (excludes force_overwrite/quiet)."""
        try:
            from ._import_utils import CacheManager
            params = CacheManager.build_params_for_hash(
                kwargs={
                    "dwi_file": dwi_file, "mask_file": mask_file, "extent": extent,
                    "output_noise_map": output_noise_map, "rank_cutoff": rank_cutoff,
                    "datatype": datatype, "estimator": estimator, "nthreads": nthreads,
                },
                file_keys=["dwi_file", "mask_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")
    
    def denoise(self, dwi_file,
                mask_file="", extent=0, output_noise_map=True, rank_cutoff=0,
                datatype="auto", estimator="Exp2", nthreads=10, force_overwrite=False,
                quiet=False):
        """
        Denoise DWI data using MRtrix3 dwidenoise (Marchenko-Pastur PCA).
        
        Important: This must be performed as the first step of the image processing 
        pipeline. The routine will fail if interpolation or smoothing has been 
        applied to the data prior to denoising.
        
        Args:
            dwi_file: Full path to DWI NIfTI file
            mask_file: Optional binary brain mask image (full path or relative to input file)
            extent: Patch size (0 = auto-select, e.g., 5 for 5x5x5)
            output_noise_map: Whether to output noise map
            rank_cutoff: Signal rank cutoff (0 = auto-select)
            datatype: Datatype for eigenvalue decomposition (auto/float32/float64)
            estimator: Noise level estimator (Exp2/Exp1)
            nthreads: Number of threads (0 = auto)
            force_overwrite: Force overwrite of output files
            quiet: Suppress information messages
            
        Returns:
            Tuple of (denoised_dwi_path, noise_map_path)
        """
        print(f"[DWI Denoise] ===== FUNCTION CALLED =====")
        print(f"[DWI Denoise] dwi_file: {repr(dwi_file)}")
        print(f"[DWI Denoise] mask_file: {repr(mask_file)}")
        print(f"[DWI Denoise] Input types: dwi_file={type(dwi_file)}, mask_file={type(mask_file)}")
        try:
            # Validate input file - handle empty strings and None
            if not dwi_file or not isinstance(dwi_file, str) or not dwi_file.strip():
                error_msg = "DWI file path is required and cannot be empty"
                print(f"[DWI Denoise] ERROR: {error_msg}")
                return (error_msg, "")
            
            input_dwi = Path(dwi_file.strip())
            if not input_dwi.exists():
                error_msg = f"DWI file not found: {dwi_file}"
                print(f"[DWI Denoise] ERROR: {error_msg}")
                return (error_msg, "")
            
            if not input_dwi.is_file():
                error_msg = f"Path is not a file: {dwi_file}"
                print(f"[DWI Denoise] ERROR: {error_msg}")
                return (error_msg, "")

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={
                    "dwi_file": dwi_file, "mask_file": mask_file, "extent": extent,
                    "output_noise_map": output_noise_map, "rank_cutoff": rank_cutoff,
                    "datatype": datatype, "estimator": estimator, "nthreads": nthreads,
                },
                file_keys=["dwi_file", "mask_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            # Infer BIDS structure from input file path
            bids_root, subject_id = BIDSHandler.infer_bids_paths(input_dwi)
            if not subject_id or not bids_root:
                output_dir = input_dwi.parent / "Denoised"
            else:
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare output file names
            input_stem = input_dwi.stem.replace(".nii", "")
            denoised_output = output_dir / f"{input_stem}_denoised.nii.gz"
            noise_map_output = output_dir / f"{input_stem}_noise.nii.gz" if output_noise_map else None

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(denoised_output), str(noise_map_output) if noise_map_output else ""]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "DWIDenoise", _param_hash, _expected)
            if _is_hit:
                print("[DWI Denoise] Cache hit — skipping.")
                return tuple(_cached)

            # Convert to MIF format for MRtrix3 (if not already)
            # Handle .nii.gz files correctly - replace both .nii and .gz with .mif
            if input_dwi.suffix == ".gz" and input_dwi.stem.endswith(".nii"):
                # For .nii.gz files, remove both .nii and .gz
                input_mif = input_dwi.parent / f"{input_dwi.stem[:-4]}.mif"
            else:
                input_mif = input_dwi.with_suffix(".mif")
            
            # For denoised output, create MIF version in same directory
            denoised_mif = output_dir / f"{input_stem}_denoised.mif"
            
            print(f"[DWI Denoise] Input DWI: {input_dwi}")
            print(f"[DWI Denoise] Output directory: {output_dir}")
            print(f"[DWI Denoise] Denoised output: {denoised_output}")
            
            # Get system executor for MRtrix3
            executor = get_executor("mrtrix")
            
            # Convert NIfTI to MIF if needed (MRtrix3 prefers MIF)
            print(f"[DWI Denoise] Converting NIfTI to MIF: {input_dwi} -> {input_mif}")
            convert_cmd = ["mrconvert", str(input_dwi), str(input_mif), "-force"]
            return_code, stdout, stderr = executor.execute(convert_cmd)
            if return_code != 0:
                raise RuntimeError(f"Failed to convert to MIF: {stderr}")
            print(f"[DWI Denoise] Conversion complete")
            
            # Build dwidenoise command
            denoise_cmd = [
                "dwidenoise",
                str(input_mif),
                str(denoised_mif)
            ]
            
            # Handle mask file if provided
            if mask_file and isinstance(mask_file, str) and mask_file.strip():
                mask_file = mask_file.strip()
                mask_path = None
                # Try to find mask - could be absolute path or relative to input file
                mask_candidates = [
                    Path(mask_file),  # Absolute or relative to current dir
                    input_dwi.parent / mask_file,  # Relative to input file
                ]
                
                # If we found subject_id, try in anat folder
                if subject_id and bids_root:
                    anat_search = bids_root / subject_id / "anat"
                    if anat_search.exists():
                        # Try exact filename match
                        mask_candidates.append(anat_search / mask_file)
                        # Try common mask patterns
                        for mask_pattern in ["*mask*.nii.gz", "*brainmask*.nii.gz", "*mask*.nii"]:
                            mask_candidates.extend(list(anat_search.glob(mask_pattern)))
                
                # Find first existing mask
                for candidate in mask_candidates:
                    if candidate.exists() and candidate.is_file():
                        mask_path = candidate
                        break
                
                if mask_path:
                    # Convert mask to MIF if needed (MRtrix3 works with both, but MIF is preferred)
                    if mask_path.suffix != ".mif":
                        # Get the base name without .nii.gz or .nii extension
                        mask_name = mask_path.name
                        if mask_name.endswith('.nii.gz'):
                            mask_stem = mask_name[:-7]  # Remove .nii.gz
                        elif mask_name.endswith('.nii'):
                            mask_stem = mask_name[:-4]  # Remove .nii
                        else:
                            mask_stem = mask_path.stem
                        
                        # Convert mask to MIF (use temp location in output dir)
                        mask_mif = output_dir / f"{mask_stem}_mask.mif"
                        print(f"[DWI Denoise] Converting mask to MIF: {mask_path} -> {mask_mif}")
                        convert_mask_cmd = ["mrconvert", str(mask_path), str(mask_mif), "-force"]
                        return_code, stdout, stderr = executor.execute(convert_mask_cmd)
                        if return_code != 0:
                            raise RuntimeError(f"Failed to convert mask to MIF: {stderr}")
                    else:
                        mask_mif = mask_path
                    denoise_cmd.extend(["-mask", str(mask_mif)])
                    print(f"[DWI Denoise] Using mask: {mask_path}")
                else:
                    # Mask file specified but not found - warn but continue
                    print(f"[DWI Denoise] Warning: Mask file not found: {mask_file}. Continuing without mask.")
            
            # Add extent (only if specified, 0 means auto-select)
            if extent > 0:
                denoise_cmd.extend(["-extent", str(extent)])
            
            # Add noise map output
            if output_noise_map and noise_map_output:
                # Create MIF path for noise map (replace .nii.gz with .mif)
                noise_map_mif = output_dir / f"{input_stem}_noise.mif"
                denoise_cmd.extend(["-noise", str(noise_map_mif)])
                print(f"[DWI Denoise] Noise map will be saved to: {noise_map_mif}")
            
            # Add rank cutoff (only if specified)
            if rank_cutoff > 0:
                denoise_cmd.extend(["-rank", str(rank_cutoff)])
            
            # Add datatype (only if not auto)
            if datatype != "auto":
                denoise_cmd.extend(["-datatype", datatype])
            
            # Add estimator
            denoise_cmd.extend(["-estimator", estimator])
            
            # Threads: 0 or unset -> use 10 (ComfyUI may not apply INT default in UI)
            if nthreads <= 0:
                nthreads = 10
            denoise_cmd.extend(["-nthreads", str(nthreads)])
            
            # Always use -force for dwidenoise to handle re-runs
            denoise_cmd.append("-force")
            
            if quiet:
                denoise_cmd.append("-quiet")
            
            print(f"[DWI Denoise] Running dwidenoise...")
            print(f"[DWI Denoise] Command: {' '.join(denoise_cmd)}")
            return_code, stdout, stderr = executor.execute(denoise_cmd)
            
            if return_code != 0:
                print(f"[DWI Denoise] ERROR: dwidenoise failed")
                print(f"[DWI Denoise] stderr: {stderr}")
                print(f"[DWI Denoise] stdout: {stdout}")
                raise RuntimeError(f"dwidenoise failed: {stderr}")
            
            print(f"[DWI Denoise] Denoising complete")
            
            # Check if denoised MIF was created
            if not denoised_mif.exists():
                raise RuntimeError(f"Denoised output file not found: {denoised_mif}")
            
            # Convert back to NIfTI
            print(f"[DWI Denoise] Converting denoised MIF back to NIfTI: {denoised_mif} -> {denoised_output}")
            convert_back_cmd = ["mrconvert", str(denoised_mif), str(denoised_output), "-force"]
            return_code, stdout, stderr = executor.execute(convert_back_cmd)
            
            if return_code != 0:
                print(f"[DWI Denoise] ERROR: Failed to convert back to NIfTI")
                print(f"[DWI Denoise] stderr: {stderr}")
                raise RuntimeError(f"Failed to convert back to NIfTI: {stderr}")
            
            if not denoised_output.exists():
                raise RuntimeError(f"Denoised NIfTI file not found: {denoised_output}")
            
            print(f"[DWI Denoise] Denoised DWI saved to: {denoised_output}")
            
            # Convert noise map if requested
            noise_map_path = ""
            if output_noise_map and noise_map_output:
                noise_map_mif = output_dir / f"{input_stem}_noise.mif"
                if noise_map_mif.exists():
                    print(f"[DWI Denoise] Converting noise map to NIfTI: {noise_map_mif} -> {noise_map_output}")
                    convert_noise_cmd = ["mrconvert", str(noise_map_mif), str(noise_map_output), "-force"]
                    return_code, stdout, stderr = executor.execute(convert_noise_cmd)
                    if return_code == 0:
                        noise_map_path = str(noise_map_output)
                        print(f"[DWI Denoise] Noise map saved to: {noise_map_output}")
                    else:
                        print(f"[DWI Denoise] Warning: Failed to convert noise map: {stderr}")
                else:
                    print(f"[DWI Denoise] Warning: Noise map MIF file not found: {noise_map_mif}")
            
            # Write metadata (if BIDS structure detected)
            if subject_id and bids_root:
                try:
                    bids = BIDSHandler(str(bids_root))
                    metadata = {
                        "ProcessingStep": "denoising",
                        "Method": "Marchenko-Pastur PCA",
                        "Tool": "MRtrix3 dwidenoise",
                        "Extent": extent if extent > 0 else "auto",
                        "RankCutoff": rank_cutoff if rank_cutoff > 0 else "auto",
                        "Datatype": datatype,
                        "Estimator": estimator,
                        "NThreads": nthreads if nthreads > 0 else "auto",
                        "MaskUsed": bool(mask_file and mask_path and mask_path.exists())
                    }
                    bids.write_derivative_file(denoised_output, input_dwi, metadata)
                except Exception as e:
                    print(f"Warning: Could not write BIDS metadata: {e}")
            
            print(f"[DWI Denoise] Processing complete!")
            print(f"[DWI Denoise] Denoised DWI: {denoised_output}")
            if noise_map_path:
                print(f"[DWI Denoise] Noise map: {noise_map_path}")

            # ── Block 3: update cache ──
            _result_paths = [str(denoised_output), noise_map_path]
            CacheManager.update_cache(_cache_path, "DWIDenoise", _param_hash, _params, _result_paths)

            return (str(denoised_output), noise_map_path)
        
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"[DWI Denoise] {error_msg}")
            import traceback
            print(f"[DWI Denoise] Traceback: {traceback.format_exc()}")
            return (error_msg, "")
