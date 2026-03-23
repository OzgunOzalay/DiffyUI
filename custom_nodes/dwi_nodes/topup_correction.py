"""
DWI Topup Correction Node - Corrects susceptibility-induced distortions.
Uses FSL topup and applytopup to correct for EPI distortions using AP/PA B0 pairs.
"""

import os
import sys
import json
from pathlib import Path

# Import utils using helper module
from ._import_utils import get_executor, BIDSHandler, CacheManager

print("[DWI Topup] ===== MODULE LOADING =====")


class DWITopupCorrectionNode:
    """
    DWI Topup Correction Node using FSL topup and applytopup.
    Corrects susceptibility-induced distortions using AP/PA B0 pairs.
    """
    
    def __init__(self):
        print("[DWI Topup] Node instance created!")
    
    @classmethod
    def INPUT_TYPES(cls):
        print("[DWI Topup] INPUT_TYPES called")
        return {
            "required": {
                "ap_b0_file": ("STRING", {
                    "default": "",
                    "tooltip": "AP phase encoded B0 file path"
                }),
                "pa_b0_file": ("STRING", {
                    "default": "",
                    "tooltip": "PA phase encoded B0 file path"
                }),
                "ap_dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "AP phase encoded full DWI file to correct"
                }),
            },
            "optional": {
                "topup_config": ("STRING", {
                    "default": "",
                    "tooltip": "Path to b02b0.cnf config file (empty = auto-detect from FSL)"
                }),
                "num_threads": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 64,
                    "tooltip": "Number of threads for topup (0 = use 10)"
                }),
                "apply_method": (["jac", "lsr"], {
                    "default": "jac",
                    "tooltip": "Method for applytopup: jac (Jacobian modulation) or lsr (least squares resampling)"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("corrected_dwi", "topup_field", "acqp_file")
    FUNCTION = "topup_correct"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = "Correct susceptibility-induced distortions using FSL topup with AP/PA B0 pairs."
    
    @classmethod
    def IS_CHANGED(cls, ap_b0_file, pa_b0_file, ap_dwi_file,
                   topup_config="", num_threads=10, apply_method="jac"):
        """Re-run only when inputs actually change (matches internal cache params)."""
        try:
            from ._import_utils import CacheManager
            params = CacheManager.build_params_for_hash(
                kwargs={
                    "ap_b0_file": ap_b0_file, "pa_b0_file": pa_b0_file,
                    "ap_dwi_file": ap_dwi_file, "num_threads": num_threads,
                    "apply_method": apply_method,
                },
                file_keys=["ap_b0_file", "pa_b0_file", "ap_dwi_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")
    
    def _read_total_readout_time(self, nifti_file: Path) -> float:
        """
        Read TotalReadoutTime from JSON sidecar file.
        
        Args:
            nifti_file: Path to NIfTI file
            
        Returns:
            Total Readout Time value, or default 0.0959097 if not found
        """
        # Find JSON sidecar (BIDS convention)
        json_path = nifti_file.with_suffix('').with_suffix('.json')
        
        if json_path.exists():
            try:
                with open(json_path, 'r') as f:
                    json_data = json.load(f)
                
                # Try different possible field names
                total_readout_time = json_data.get("TotalReadoutTime") or \
                                   json_data.get("Total Readout Time") or \
                                   json_data.get("total_readout_time")
                
                if total_readout_time is not None:
                    print(f"[DWI Topup] Found TotalReadoutTime in {json_path.name}: {total_readout_time}")
                    return float(total_readout_time)
                else:
                    print(f"[DWI Topup] Warning: TotalReadoutTime not found in {json_path.name}, using default")
            except Exception as e:
                print(f"[DWI Topup] Warning: Could not read JSON {json_path}: {e}, using default")
        else:
            print(f"[DWI Topup] Warning: JSON sidecar not found: {json_path}, using default")
        
        # Default value
        default_value = 0.0959097
        print(f"[DWI Topup] Using default TotalReadoutTime: {default_value}")
        return default_value
    
    def _find_topup_config(self, user_config: str = "") -> Path:
        """
        Find b02b0.cnf config file.
        
        Args:
            user_config: User-provided config path (optional)
            
        Returns:
            Path to config file
            
        Raises:
            FileNotFoundError: If config file cannot be found
        """
        # If user provided a path, use it
        if user_config and user_config.strip():
            config_path = Path(user_config.strip())
            if config_path.exists():
                print(f"[DWI Topup] Using user-provided config: {config_path}")
                return config_path
            else:
                print(f"[DWI Topup] Warning: User-provided config not found: {config_path}")
        
        # Try FSLDIR environment variable
        fsl_dir = os.environ.get("FSLDIR", "/usr/share/fsl")
        config_path = Path(fsl_dir) / "etc" / "flirtsch" / "b02b0.cnf"
        if config_path.exists():
            print(f"[DWI Topup] Found config in FSLDIR: {config_path}")
            return config_path
        
        # Try common system locations
        common_paths = [
            Path("/usr/share/fsl/etc/flirtsch/b02b0.cnf"),
            Path("/opt/fsl/etc/flirtsch/b02b0.cnf"),
            Path("/usr/local/fsl/etc/flirtsch/b02b0.cnf"),
        ]
        
        for config_path in common_paths:
            if config_path.exists():
                print(f"[DWI Topup] Found config in system location: {config_path}")
                return config_path
        
        raise FileNotFoundError(
            f"b02b0.cnf config file not found. "
            f"Tried: {fsl_dir}/etc/flirtsch/b02b0.cnf and common system locations. "
            f"Please provide path via topup_config parameter."
        )
    
    def topup_correct(
        self,
        ap_b0_file: str,
        pa_b0_file: str,
        ap_dwi_file: str,
        topup_config: str = "",
        num_threads: int = 10,
        apply_method: str = "jac"
    ):
        """
        Perform Topup correction for susceptibility-induced distortions.
        
        Process:
        1. Read TotalReadoutTime from JSON sidecars
        2. Merge AP and PA B0 images
        3. Create acquisition parameters file
        4. Run topup to calculate inhomogeneity field
        5. Run applytopup to apply correction to AP DWI
        
        Args:
            ap_b0_file: AP phase encoded B0 file path
            pa_b0_file: PA phase encoded B0 file path
            ap_dwi_file: AP phase encoded full DWI file to correct
            topup_config: Path to b02b0.cnf config file (empty = auto-detect)
            num_threads: Number of threads for topup (0 = auto-detect)
            apply_method: Method for applytopup (jac or lsr)
            
        Returns:
            Tuple of (corrected_dwi_path, topup_field_path)
        """
        print(f"[DWI Topup] ===== FUNCTION CALLED =====")
        print(f"[DWI Topup] AP B0: {repr(ap_b0_file)}")
        print(f"[DWI Topup] PA B0: {repr(pa_b0_file)}")
        print(f"[DWI Topup] AP DWI: {repr(ap_dwi_file)}")
        
        try:
            # Validate input files
            ap_b0_path = Path(ap_b0_file.strip()) if ap_b0_file else None
            pa_b0_path = Path(pa_b0_file.strip()) if pa_b0_file else None
            ap_dwi_path = Path(ap_dwi_file.strip()) if ap_dwi_file else None
            
            for name, path in [("AP B0", ap_b0_path), ("PA B0", pa_b0_path), ("AP DWI", ap_dwi_path)]:
                if not path or not path.exists():
                    error_msg = f"{name} file not found: {path}"
                    print(f"[DWI Topup] ERROR: {error_msg}")
                    return (f"Error: {error_msg}", "", "")
                if not path.is_file():
                    error_msg = f"{name} path is not a file: {path}"
                    print(f"[DWI Topup] ERROR: {error_msg}")
                    return (f"Error: {error_msg}", "", "")

            print(f"[DWI Topup] All input files validated")

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={
                    "ap_b0_file": ap_b0_file, "pa_b0_file": pa_b0_file,
                    "ap_dwi_file": ap_dwi_file, "num_threads": num_threads,
                    "apply_method": apply_method,
                },
                file_keys=["ap_b0_file", "pa_b0_file", "ap_dwi_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)
            
            # Infer BIDS structure from input file path for output location
            bids_root, subject_id = BIDSHandler.infer_bids_paths(ap_dwi_path)
            if not subject_id or not bids_root:
                # Fallback: use parent directory structure
                output_dir = ap_dwi_path.parent / "Topup"
            else:
                # Use BIDS derivatives structure
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi" / "Topup"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[DWI Topup] Output directory: {output_dir}")

            # ── Block 2: pre-compute output paths and check cache ──
            _ap_dwi_name = ap_dwi_path.name
            if _ap_dwi_name.endswith('.nii.gz'):
                _merged_base = _ap_dwi_name[:-7].replace('_dir-AP', '_dir-AP-PA')
            elif _ap_dwi_name.endswith('.nii'):
                _merged_base = _ap_dwi_name[:-4].replace('_dir-AP', '_dir-AP-PA')
            else:
                _merged_base = ap_dwi_path.stem.replace('_dir-AP', '_dir-AP-PA')
            _topup_prefix = output_dir / f"{_merged_base}_Topup"
            _topup_field_pre = _topup_prefix.parent / f"{_topup_prefix.name}_fieldcoef.nii.gz"
            _ap_dwi_stem = ap_dwi_path.stem.replace(".nii", "")
            _corrected_dwi_pre = output_dir / f"{_ap_dwi_stem}_topup.nii.gz"
            _acq_params_pre = output_dir / "acq_params.txt"
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(_corrected_dwi_pre), str(_topup_field_pre), str(_acq_params_pre)]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "DWITopupCorrection", _param_hash, _expected)
            if _is_hit:
                print("[DWI Topup] Cache hit — skipping.")
                return tuple(_cached)

            # Get system executor for FSL
            executor = get_executor("fsl")
            
            # Step 1: Read Total Readout Time from JSON files
            # Use the original DWI files to find JSON, not the B0 files
            print(f"[DWI Topup] Reading TotalReadoutTime from JSON files...")
            # Use the AP DWI file directly (it's passed as a parameter)
            # For PA, try to find the original PA DWI file by replacing AP with PA in the path
            ap_dwi_for_json = ap_dwi_path
            
            # Try to find PA DWI file from AP DWI path
            pa_dwi_for_json = pa_b0_path  # Default to B0 file if we can't find original
            if "dir-AP" in str(ap_dwi_path):
                # Try to find original PA DWI file
                pa_dwi_candidate = Path(str(ap_dwi_path).replace("dir-AP", "dir-PA"))
                if not pa_dwi_candidate.exists() and ap_dwi_path.suffix == ".gz":
                    # Try without .gz
                    pa_dwi_candidate = Path(str(ap_dwi_path)[:-3].replace("dir-AP", "dir-PA"))
                if pa_dwi_candidate.exists():
                    pa_dwi_for_json = pa_dwi_candidate
                    print(f"[DWI Topup] Found original PA DWI file for JSON: {pa_dwi_for_json}")
            
            total_readout_time_ap = self._read_total_readout_time(ap_dwi_for_json)
            total_readout_time_pa = self._read_total_readout_time(pa_dwi_for_json)
            
            # Use the average if they differ (should be the same, but handle differences)
            if abs(total_readout_time_ap - total_readout_time_pa) > 0.0001:
                print(f"[DWI Topup] Warning: TotalReadoutTime differs between AP ({total_readout_time_ap}) and PA ({total_readout_time_pa})")
                print(f"[DWI Topup] Using AP value: {total_readout_time_ap}")
            total_readout_time = total_readout_time_ap
            
            # Step 2: Merge AP and PA B0 images
            print(f"[DWI Topup] Merging AP and PA B0 images...")
            # Get base name from AP DWI file
            ap_dwi_name = ap_dwi_path.name
            if ap_dwi_name.endswith('.nii.gz'):
                merged_base = ap_dwi_name[:-7].replace('_dir-AP', '_dir-AP-PA')
            elif ap_dwi_name.endswith('.nii'):
                merged_base = ap_dwi_name[:-4].replace('_dir-AP', '_dir-AP-PA')
            else:
                merged_base = ap_dwi_path.stem.replace('_dir-AP', '_dir-AP-PA')
            
            merged_b0 = output_dir / f"{merged_base}_b0.nii.gz"
            
            fslmerge_cmd = [
                "fslmerge",
                "-t",  # Merge along time dimension
                str(merged_b0),
                str(ap_b0_path),
                str(pa_b0_path)
            ]
            
            print(f"[DWI Topup] Running: {' '.join(fslmerge_cmd)}")
            return_code, stdout, stderr = executor.execute(fslmerge_cmd)
            if return_code != 0:
                error_msg = f"fslmerge failed: {stderr}"
                print(f"[DWI Topup] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "", "")
            
            import time
            time.sleep(0.5)  # Wait for file to be written
            
            if not merged_b0.exists():
                error_msg = f"Merged B0 file not found: {merged_b0}"
                print(f"[DWI Topup] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "", "")
            
            print(f"[DWI Topup] Merged B0 created: {merged_b0}")
            
            # Step 3: Create acquisition parameters file
            print(f"[DWI Topup] Creating acquisition parameters file...")
            acq_params_file = output_dir / "acq_params.txt"
            
            # Format: phase_encoding_x phase_encoding_y phase_encoding_z total_readout_time
            # AP: 0 1 0 <total_readout_time> (phase encoding in Y direction, positive)
            # PA: 0 -1 0 <total_readout_time> (phase encoding in Y direction, negative)
            with open(acq_params_file, 'w') as f:
                f.write(f"0 1 0 {total_readout_time}\n")   # AP
                f.write(f"0 -1 0 {total_readout_time}\n")  # PA
            
            print(f"[DWI Topup] Acquisition parameters file created: {acq_params_file}")
            print(f"[DWI Topup] AP: 0 1 0 {total_readout_time}")
            print(f"[DWI Topup] PA: 0 -1 0 {total_readout_time}")
            
            # Step 4: Find topup config file
            print(f"[DWI Topup] Finding topup config file...")
            try:
                config_path = self._find_topup_config(topup_config)
                print(f"[DWI Topup] Using config: {config_path}")
            except FileNotFoundError as e:
                error_msg = str(e)
                print(f"[DWI Topup] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "", "")
            
            # Step 5: Run topup
            print(f"[DWI Topup] Running topup to calculate inhomogeneity field...")
            topup_output_prefix = output_dir / f"{merged_base}_Topup"
            
            # Default threads when 0 (ComfyUI may not apply INT default in UI)
            if num_threads == 0:
                num_threads = 10
                print(f"[DWI Topup] Using default {num_threads} threads (0 or unset)")
            
            topup_cmd = [
                "topup",
                f"--imain={str(merged_b0)}",
                f"--datain={str(acq_params_file)}",
                f"--config={str(config_path)}",
                f"--out={str(topup_output_prefix)}",
                f"--nthr={str(num_threads)}"
            ]
            
            print(f"[DWI Topup] Running: {' '.join(topup_cmd)}")
            return_code, stdout, stderr = executor.execute(topup_cmd)
            if return_code != 0:
                error_msg = f"topup failed: {stderr}"
                print(f"[DWI Topup] ERROR: {error_msg}")
                print(f"[DWI Topup] stdout: {stdout}")
                return (f"Error: {error_msg}", "", "")
            
            # Wait for topup output files
            time.sleep(1.0)
            
            # Topup creates: <prefix>_fieldcoef.nii.gz and <prefix>_movpar.txt
            topup_field = topup_output_prefix.parent / f"{topup_output_prefix.name}_fieldcoef.nii.gz"
            if not topup_field.exists():
                error_msg = f"Topup field file not found: {topup_field}"
                print(f"[DWI Topup] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "", "")
            
            print(f"[DWI Topup] Topup completed successfully")
            print(f"[DWI Topup] Field file: {topup_field}")
            
            # Step 6: Run applytopup
            print(f"[DWI Topup] Applying topup correction to AP DWI scan...")
            
            # Prepare output filename
            ap_dwi_stem = ap_dwi_path.stem.replace(".nii", "")
            corrected_dwi = output_dir / f"{ap_dwi_stem}_topup.nii.gz"
            
            applytopup_cmd = [
                "applytopup",
                f"--imain={str(ap_dwi_path)}",
                "--inindex=1",  # First volume in merged file corresponds to AP
                f"--datain={str(acq_params_file)}",
                f"--topup={str(topup_output_prefix)}",
                f"--method={apply_method}",
                f"--out={str(corrected_dwi)}"
            ]
            
            print(f"[DWI Topup] Running: {' '.join(applytopup_cmd)}")
            return_code, stdout, stderr = executor.execute(applytopup_cmd)
            if return_code != 0:
                error_msg = f"applytopup failed: {stderr}"
                print(f"[DWI Topup] ERROR: {error_msg}")
                print(f"[DWI Topup] stdout: {stdout}")
                return (f"Error: {error_msg}", "", "")
            
            time.sleep(0.5)
            
            if not corrected_dwi.exists():
                error_msg = f"Corrected DWI file not found: {corrected_dwi}"
                print(f"[DWI Topup] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "", "")
            
            print(f"[DWI Topup] Topup correction completed successfully!")
            print(f"[DWI Topup] Corrected DWI: {corrected_dwi}")
            print(f"[DWI Topup] Topup field: {topup_field}")
            print(f"[DWI Topup] ===== CORRECTION COMPLETE =====")

            # ── Block 3: update cache ──
            _result_paths = [str(corrected_dwi), str(topup_field), str(acq_params_file)]
            CacheManager.update_cache(_cache_path, "DWITopupCorrection", _param_hash, _params, _result_paths)

            return (str(corrected_dwi), str(topup_field), str(acq_params_file))
        
        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            print(f"[DWI Topup] {error_msg}")
            print(f"[DWI Topup] Traceback: {traceback.format_exc()}")
            return (error_msg, "", "")
