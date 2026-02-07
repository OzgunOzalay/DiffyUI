"""
DWI Tensor Fitting Node - Fourth node in the pipeline.
Uses FSL dtifit or MRtrix3 dwi2tensor for DTI estimation.
"""

import os
import sys
from pathlib import Path

# Import utils using helper module
from ._import_utils import BIDSHandler, get_executor, FileManager


class DWITensorFittingNode:
    """
    DWI Tensor Fitting Node for DTI estimation.
    This is the FOURTH node in the DWI processing pipeline.
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
                    "tooltip": "Input corrected DWI file"
                }),
            },
            "optional": {
                "tool": (["FSL", "MRtrix3"], {
                    "default": "FSL",
                    "tooltip": "Tool to use for tensor fitting"
                }),
                "mask_file": ("STRING", {
                    "default": "",
                    "tooltip": "Optional brain mask file"
                }),
                "mask_threshold": ("FLOAT", {
                    "default": 0.3,
                    "min": 0.0,
                    "max": 1.0,
                    "tooltip": "Mask threshold for FSL"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("fa_map", "md_map", "ad_map", "rd_map", "tensor")
    FUNCTION = "fit_tensor"
    CATEGORY = "DWI"
    DESCRIPTION = "Fit diffusion tensor model (DTI) to DWI data"
    
    def fit_tensor(self, bids_dataset, subject_id, dwi_file,
                   tool="FSL", mask_file="", mask_threshold=0.3):
        """
        Fit diffusion tensor model.
        
        Args:
            bids_dataset: Path to BIDS dataset
            subject_id: Subject ID
            dwi_file: Input DWI file
            tool: Tool to use (FSL or MRtrix3)
            mask_file: Optional mask file
            mask_threshold: Mask threshold
            
        Returns:
            Tuple of (fa_map, md_map, ad_map, rd_map, tensor)
        """
        try:
            input_dwi = Path(dwi_file)
            if not input_dwi.exists():
                raise ValueError(f"Input DWI file not found: {dwi_file}")

            # BIDS output path: use bids_dataset/subject_id if both provided, else infer from path (same as Eddy/Topup)
            if bids_dataset and str(bids_dataset).strip() and subject_id and str(subject_id).strip():
                bids = BIDSHandler(str(bids_dataset).strip())
                derivatives_path = bids.get_derivatives_path(str(subject_id).strip(), "diffyui")
                output_dir = derivatives_path / "dwi"
            else:
                path_parts = input_dwi.parts
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
                    output_dir = derivatives_path / "dwi"
                else:
                    bids = BIDSHandler(str(input_dwi.parent))
                    output_dir = input_dwi.parent / "Tensor"
            output_dir.mkdir(parents=True, exist_ok=True)

            input_stem = input_dwi.stem.replace(".nii", "")
            base_output = output_dir / input_stem
            
            if tool == "FSL":
                return self._fit_tensor_fsl(bids, input_dwi, base_output, mask_file, mask_threshold)
            else:  # MRtrix3
                return self._fit_tensor_mrtrix(bids, input_dwi, base_output, mask_file)
        
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            return (error_msg, error_msg, error_msg, error_msg, error_msg)
    
    def _fit_tensor_fsl(self, bids, input_dwi, base_output, mask_file, mask_threshold):
        """Fit tensor using FSL dtifit."""
        executor = get_executor("fsl")
        
        # Get b-values and b-vectors
        bvals, bvecs = bids.read_gradient_table(input_dwi)
        
        # Write bvals and bvecs to files
        bval_file = base_output.parent / f"{base_output.name}_bvals.txt"
        bvec_file = base_output.parent / f"{base_output.name}_bvecs.txt"
        
        with open(bval_file, 'w') as f:
            f.write(' '.join(map(str, bvals)))
        
        with open(bvec_file, 'w') as f:
            for i in range(3):
                f.write(' '.join(map(str, [v[i] for v in bvecs])) + '\n')
        
        # Prepare dtifit command
        dtifit_cmd = [
            "dtifit",
            "-k", str(input_dwi),
            "-o", str(base_output),
            "-b", str(bval_file),
            "-r", str(bvec_file),
            "-m", mask_file if mask_file and Path(mask_file).exists() else "",
            "--sse"
        ]
        
        if mask_file and Path(mask_file).exists():
            dtifit_cmd.extend(["-m", mask_file])
        
        return_code, stdout, stderr = executor.execute(dtifit_cmd)
        
        if return_code != 0:
            raise RuntimeError(f"dtifit failed: {stderr}")
        
        # Output files from dtifit
        fa_map = str(base_output) + "_FA.nii.gz"
        md_map = str(base_output) + "_MD.nii.gz"
        ad_map = str(base_output) + "_L1.nii.gz"  # AD is L1
        rd_map = str(base_output) + "_RD.nii.gz"
        tensor = str(base_output) + "_tensor.nii.gz"
        
        return (fa_map, md_map, ad_map, rd_map, tensor)
    
    def _fit_tensor_mrtrix(self, bids, input_dwi, base_output, mask_file):
        """Fit tensor using MRtrix3 dwi2tensor."""
        executor = get_executor("mrtrix")
        
        # Convert to MIF if needed
        input_mif = input_dwi.with_suffix(".mif")
        if not input_mif.exists():
            convert_cmd = ["mrconvert", str(input_dwi), str(input_mif)]
            return_code, stdout, stderr = executor.execute(convert_cmd)
            if return_code != 0:
                raise RuntimeError(f"Failed to convert to MIF: {stderr}")
        
        # Fit tensor
        tensor_mif = base_output.parent / f"{base_output.name}_tensor.mif"
        dwi2tensor_cmd = [
            "dwi2tensor",
            str(input_mif),
            str(tensor_mif)
        ]
        
        if mask_file and Path(mask_file).exists():
            mask_mif = Path(mask_file).with_suffix(".mif")
            if not mask_mif.exists():
                convert_mask_cmd = ["mrconvert", str(mask_file), str(mask_mif)]
                executor.execute(convert_mask_cmd)
            dwi2tensor_cmd.extend(["-mask", str(mask_mif)])
        
        return_code, stdout, stderr = executor.execute(dwi2tensor_cmd)
        
        if return_code != 0:
            raise RuntimeError(f"dwi2tensor failed: {stderr}")
        
        # Compute tensor-derived maps
        fa_mif = base_output.parent / f"{base_output.name}_FA.mif"
        md_mif = base_output.parent / f"{base_output.name}_MD.mif"
        ad_mif = base_output.parent / f"{base_output.name}_AD.mif"
        rd_mif = base_output.parent / f"{base_output.name}_RD.mif"
        
        # Compute FA
        tensor2metric_cmd = ["tensor2metric", "-fa", str(fa_mif), str(tensor_mif)]
        executor.execute(tensor2metric_cmd)
        
        # Compute MD
        tensor2metric_cmd = ["tensor2metric", "-adc", str(md_mif), str(tensor_mif)]
        executor.execute(tensor2metric_cmd)
        
        # Compute AD (L1)
        tensor2metric_cmd = ["tensor2metric", "-ad", str(ad_mif), str(tensor_mif)]
        executor.execute(tensor2metric_cmd)
        
        # Compute RD
        tensor2metric_cmd = ["tensor2metric", "-rd", str(rd_mif), str(tensor_mif)]
        executor.execute(tensor2metric_cmd)
        
        # Convert to NIfTI
        fa_map = str(fa_mif.with_suffix(".nii.gz"))
        md_map = str(md_mif.with_suffix(".nii.gz"))
        ad_map = str(ad_mif.with_suffix(".nii.gz"))
        rd_map = str(rd_mif.with_suffix(".nii.gz"))
        tensor = str(tensor_mif.with_suffix(".nii.gz"))
        
        for mif_file, nii_file in [(fa_mif, fa_map), (md_mif, md_map), 
                                   (ad_mif, ad_map), (rd_mif, rd_map), 
                                   (tensor_mif, tensor)]:
            convert_cmd = ["mrconvert", str(mif_file), nii_file]
            executor.execute(convert_cmd)
        
        return (fa_map, md_map, ad_map, rd_map, tensor)
