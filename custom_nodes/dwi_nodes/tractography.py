"""
DWI Tractography Node - Fifth node in the pipeline.
Uses MRtrix3 tckgen or FSL probtrackx2 for fiber tracking.
"""

import os
import sys
from pathlib import Path

# Import utils using helper module
from ._import_utils import BIDSHandler, get_executor, FileManager


class DWITractographyNode:
    """
    DWI Tractography Node for fiber tracking.
    This is the FIFTH node in the DWI processing pipeline.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bids_dataset": ("STRING", {
                    "default": "",
                    "tooltip": "BIDS dataset root (optional; inferred from dwi path if empty)"
                }),
                "subject_id": ("STRING", {
                    "default": "",
                    "tooltip": "Subject ID (optional; inferred from dwi path if empty)"
                }),
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "Input DWI file"
                }),
                "seed_mask": ("STRING", {
                    "default": "",
                    "tooltip": "Seed mask for tractography"
                }),
            },
            "optional": {
                "tool": (["MRtrix3", "FSL"], {
                    "default": "MRtrix3",
                    "tooltip": "Tool to use for tractography"
                }),
                "algorithm": (["deterministic", "probabilistic"], {
                    "default": "probabilistic",
                    "tooltip": "Tractography algorithm"
                }),
                "num_streamlines": ("INT", {
                    "default": 10000000,
                    "min": 1000,
                    "max": 100000000,
                    "tooltip": "Number of streamlines"
                }),
                "step_size": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.1,
                    "max": 2.0,
                    "tooltip": "Step size in mm"
                }),
                "max_length": ("FLOAT", {
                    "default": 200.0,
                    "min": 50.0,
                    "max": 500.0,
                    "tooltip": "Maximum streamline length in mm"
                }),
                "min_length": ("FLOAT", {
                    "default": 10.0,
                    "min": 0.0,
                    "max": 100.0,
                    "tooltip": "Minimum streamline length in mm"
                }),
                "waypoint_mask": ("STRING", {
                    "default": "",
                    "tooltip": "Optional waypoint mask"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tractography_file", "connectivity_matrix")
    FUNCTION = "track"
    CATEGORY = "DWI"
    DESCRIPTION = "Perform tractography (fiber tracking)"
    
    def track(self, bids_dataset, subject_id, dwi_file, seed_mask,
              tool="MRtrix3", algorithm="probabilistic",
              num_streamlines=10000000, step_size=0.5, max_length=200.0,
              min_length=10.0, waypoint_mask=""):
        """
        Perform tractography.
        
        Args:
            bids_dataset: Path to BIDS dataset
            subject_id: Subject ID
            dwi_file: Input DWI file
            seed_mask: Seed mask file
            tool: Tool to use
            algorithm: Algorithm type
            num_streamlines: Number of streamlines
            step_size: Step size
            max_length: Maximum length
            min_length: Minimum length
            waypoint_mask: Optional waypoint mask
            
        Returns:
            Tuple of (tractography_file_path, connectivity_matrix_path)
        """
        try:
            input_dwi = Path(dwi_file)
            seed = Path(seed_mask)
            if not input_dwi.exists():
                raise ValueError(f"Input DWI file not found: {dwi_file}")
            if not seed.exists():
                raise ValueError(f"Seed mask not found: {seed_mask}")

            # BIDS output path: use bids_dataset/subject_id if both provided, else infer from path (same as Eddy/Topup)
            if bids_dataset and str(bids_dataset).strip() and subject_id and str(subject_id).strip():
                bids = BIDSHandler(str(bids_dataset).strip())
                derivatives_path = bids.get_derivatives_path(str(subject_id).strip(), "diffyui")
                output_dir = derivatives_path / "dwi"
            else:
                inf_bids_root, inf_subject_id = BIDSHandler.infer_bids_paths(input_dwi)
                if inf_subject_id and inf_bids_root:
                    bids = BIDSHandler(str(inf_bids_root))
                    derivatives_path = bids.get_derivatives_path(inf_subject_id, "diffyui")
                    output_dir = derivatives_path / "dwi"
                else:
                    bids = BIDSHandler(str(input_dwi.parent))
                    output_dir = input_dwi.parent / "Tractography"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare output files
            input_stem = input_dwi.stem.replace(".nii", "")
            tractography_output = output_dir / f"{input_stem}_tractography.tck"
            connectivity_output = output_dir / f"{input_stem}_connectivity.csv"
            
            if tool == "MRtrix3":
                return self._track_mrtrix(bids, input_dwi, seed, tractography_output,
                                         algorithm, num_streamlines, step_size,
                                         max_length, min_length, waypoint_mask)
            else:  # FSL
                return self._track_fsl(bids, input_dwi, seed, tractography_output,
                                      algorithm, num_streamlines, step_size,
                                      max_length, min_length, waypoint_mask)
        
        except Exception as e:
            return (f"Error: {str(e)}", "")
    
    def _track_mrtrix(self, bids, input_dwi, seed, output_file, algorithm,
                     num_streamlines, step_size, max_length, min_length, waypoint_mask):
        """Perform tractography using MRtrix3."""
        executor = get_executor("mrtrix")
        
        # Convert to MIF if needed
        input_mif = input_dwi.with_suffix(".mif")
        if not input_mif.exists():
            convert_cmd = ["mrconvert", str(input_dwi), str(input_mif)]
            return_code, stdout, stderr = executor.execute(convert_cmd)
            if return_code != 0:
                raise RuntimeError(f"Failed to convert to MIF: {stderr}")
        
        # Convert seed mask
        seed_mif = seed.with_suffix(".mif")
        if not seed_mif.exists():
            convert_cmd = ["mrconvert", str(seed), str(seed_mif)]
            executor.execute(convert_cmd)
        
        # Estimate response function and fiber orientation distribution
        # This is simplified - full pipeline would include these steps
        response_file = input_mif.parent / "response.txt"
        fod_file = input_mif.parent / "fod.mif"
        
        # For now, use simplified tckgen command
        tckgen_cmd = [
            "tckgen",
            "-algorithm", algorithm,
            "-select", str(num_streamlines),
            "-step", str(step_size),
            "-maxlength", str(max_length),
            "-minlength", str(min_length),
            "-seed_image", str(seed_mif),
            str(input_mif),
            str(output_file.with_suffix(".tck"))
        ]
        
        if waypoint_mask and Path(waypoint_mask).exists():
            waypoint_mif = Path(waypoint_mask).with_suffix(".mif")
            if not waypoint_mif.exists():
                convert_cmd = ["mrconvert", str(waypoint_mask), str(waypoint_mif)]
                executor.execute(convert_cmd)
            tckgen_cmd.extend(["-include", str(waypoint_mif)])
        
        return_code, stdout, stderr = executor.execute(tckgen_cmd)
        
        if return_code != 0:
            raise RuntimeError(f"tckgen failed: {stderr}")
        
        # Compute connectivity matrix (simplified)
        connectivity_file = output_file.parent / f"{output_file.stem}_connectivity.csv"
        # This would require additional steps with tck2connectome
        
        return (str(output_file.with_suffix(".tck")), str(connectivity_file))
    
    def _track_fsl(self, bids, input_dwi, seed, output_file, algorithm,
                   num_streamlines, step_size, max_length, min_length, waypoint_mask):
        """Perform tractography using FSL probtrackx2."""
        executor = get_executor("fsl")
        
        # FSL probtrackx2 requires specific directory structure
        output_dir = output_file.parent / "probtrackx"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        probtrackx_cmd = [
            "probtrackx2",
            "-x", str(seed),
            "-s", "merged_thalamic_MNI152_2mm_brain_mask.nii.gz",  # Would need proper files
            "-m", "mask.nii.gz",  # Would need mask
            "--dir", str(output_dir),
            "--nsamples", str(num_streamlines),
            "--step", str(step_size),
            "--steplength", str(step_size),
            "--distthresh", "0.0",
            "--sampvox", "0.0",
            "--randfib", "1",
            "--fibthresh", "0.01",
            "--meshspace", "first"
        ]
        
        # This is a placeholder - full implementation requires proper setup
        return_code, stdout, stderr = executor.execute(probtrackx_cmd)
        
        if return_code != 0:
            raise RuntimeError(f"probtrackx2 failed: {stderr}")
        
        return (str(output_file), str(output_file.parent / "connectivity.csv"))
