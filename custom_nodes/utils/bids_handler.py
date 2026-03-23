"""
BIDS format handler utilities for reading/writing BIDS datasets.
Handles BIDS structure with anat/ and dwi/ folders.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import nibabel as nib


class BIDSHandler:
    """Handler for BIDS-formatted datasets with anat/ and dwi/ folders."""
    
    def __init__(self, bids_root: str):
        """
        Initialize BIDS handler.
        
        Args:
            bids_root: Path to root of BIDS dataset
        """
        self.bids_root = Path(bids_root)
        if not self.bids_root.exists():
            raise ValueError(f"BIDS root directory does not exist: {bids_root}")
    
    def validate_structure(self) -> bool:
        """Validate that at least one subject folder exists."""
        # Check if we have at least one subject folder
        subjects = self.get_all_subjects()
        return len(subjects) > 0
    
    def get_all_subjects(self) -> List[str]:
        """
        Get all subject IDs from the BIDS dataset.
        
        Returns:
            List of subject IDs (e.g., ["sub-01", "sub-02", ...])
        """
        subjects = []
        
        # BIDS structure: bids_root/sub-XX/anat/ and bids_root/sub-XX/dwi/
        # Check if subjects are directly in bids_root
        for item in self.bids_root.iterdir():
            if item.is_dir() and item.name.startswith("sub-"):
                # Verify it has anat/ or dwi/ subfolder
                if (item / "anat").exists() or (item / "dwi").exists():
                    subjects.append(item.name)
        
        return sorted(subjects)
    
    def get_subject_dwi_files(self, subject_id: str) -> List[Path]:
        """
        Get DWI files for a subject.
        
        Args:
            subject_id: Subject ID (e.g., "sub-01")
            
        Returns:
            List of DWI file paths
        """
        search_dir = self.bids_root / subject_id / "dwi"
        
        if not search_dir.exists():
            return []
        
        # Find all .nii.gz and .nii files (excluding sbref)
        dwi_files = []
        for ext in [".nii.gz", ".nii", ".mif"]:
            files = list(search_dir.glob(f"*_dwi{ext}"))
            dwi_files.extend(files)
        
        return sorted(dwi_files)
    
    def get_subject_dwi_all_files(self, subject_id: str) -> Dict[str, List[Path]]:
        """
        Get all DWI-related files for a subject (dwi.nii, dwi.json, dwi.bval, dwi.bvec, sbref.nii, sbref.json).
        
        Args:
            subject_id: Subject ID (e.g., "sub-01")
            
        Returns:
            Dictionary with keys: 'dwi_nii', 'dwi_json', 'dwi_bval', 'dwi_bvec', 'sbref_nii', 'sbref_json'
        """
        search_dir = self.bids_root / subject_id / "dwi"
        
        if not search_dir.exists():
            return {
                'dwi_nii': [],
                'dwi_json': [],
                'dwi_bval': [],
                'dwi_bvec': [],
                'sbref_nii': [],
                'sbref_json': []
            }
        
        result = {
            'dwi_nii': [],
            'dwi_json': [],
            'dwi_bval': [],
            'dwi_bvec': [],
            'sbref_nii': [],
            'sbref_json': []
        }
        
        # Find all DWI NIfTI files
        for ext in [".nii.gz", ".nii"]:
            result['dwi_nii'].extend(search_dir.glob(f"*_dwi{ext}"))
            result['sbref_nii'].extend(search_dir.glob(f"*_sbref{ext}"))
        
        # Find JSON files
        result['dwi_json'].extend(search_dir.glob("*_dwi.json"))
        result['sbref_json'].extend(search_dir.glob("*_sbref.json"))
        
        # Find bval and bvec files
        result['dwi_bval'].extend(search_dir.glob("*_dwi.bval"))
        result['dwi_bvec'].extend(search_dir.glob("*_dwi.bvec"))
        
        # Sort all lists
        for key in result:
            result[key] = sorted(result[key])
        
        return result
    
    def get_subject_anat_files(self, subject_id: str, modality: str = "T1w") -> List[Path]:
        """
        Get anatomical files for a subject.
        
        Args:
            subject_id: Subject ID
            modality: Modality type (T1w, T2w, etc.)
            
        Returns:
            List of anatomical file paths
        """
        search_dir = self.bids_root / subject_id / "anat"
        
        if not search_dir.exists():
            return []
        
        # Find files matching modality (support both .nii.gz and .nii)
        anat_files = []
        for ext in [".nii.gz", ".nii"]:
            pattern = f"*{modality}*{ext}"
            anat_files.extend(search_dir.glob(pattern))
        
        return sorted(anat_files)
    
    def get_subject_anat_all_files(self, subject_id: str) -> Dict[str, List[Path]]:
        """
        Get all anatomical files for a subject (NIfTI and JSON).
        
        Args:
            subject_id: Subject ID
            
        Returns:
            Dictionary with keys: 'anat_nii', 'anat_json'
        """
        search_dir = self.bids_root / subject_id / "anat"
        
        if not search_dir.exists():
            return {
                'anat_nii': [],
                'anat_json': []
            }
        
        result = {
            'anat_nii': [],
            'anat_json': []
        }
        
        # Find all NIfTI files (any modality)
        for ext in [".nii.gz", ".nii"]:
            result['anat_nii'].extend(search_dir.glob(f"*{ext}"))
        
        # Find all JSON files
        result['anat_json'].extend(search_dir.glob("*.json"))
        
        # Sort all lists
        for key in result:
            result[key] = sorted(result[key])
        
        return result
    
    def get_json_sidecar(self, nifti_file: Path) -> Optional[Dict]:
        """
        Get JSON sidecar for a NIfTI file.
        
        Args:
            nifti_file: Path to NIfTI file
            
        Returns:
            Dictionary with JSON content or None if not found
        """
        json_file = nifti_file.with_suffix("").with_suffix(".json")
        if json_file.exists():
            with open(json_file, 'r') as f:
                return json.load(f)
        return None
    
    def read_gradient_table(self, dwi_file: Path) -> Tuple[List[float], List[List[float]]]:
        """
        Read b-values and b-vectors from BIDS JSON sidecar.
        
        Args:
            dwi_file: Path to DWI NIfTI file
            
        Returns:
            Tuple of (b-values list, b-vectors list)
        """
        json_data = self.get_json_sidecar(dwi_file)
        if not json_data:
            raise ValueError(f"No JSON sidecar found for {dwi_file}")
        
        # BIDS format: bval and bvec can be in JSON or separate files
        bvals = json_data.get("BidsBval", [])
        bvecs = json_data.get("BidsBvec", [])
        
        # If not in JSON, try to find .bval and .bvec files
        if not bvals or not bvecs:
            base_path = dwi_file.with_suffix("").with_suffix("")
            bval_file = base_path.with_suffix(".bval")
            bvec_file = base_path.with_suffix(".bvec")
            
            if bval_file.exists() and bvec_file.exists():
                bvals = self._read_bval_file(bval_file)
                bvecs = self._read_bvec_file(bvec_file)
        
        if not bvals or not bvecs:
            raise ValueError(f"Could not find b-values/b-vectors for {dwi_file}")
        
        return bvals, bvecs
    
    def _read_bval_file(self, bval_file: Path) -> List[float]:
        """Read b-values from .bval file."""
        with open(bval_file, 'r') as f:
            content = f.read().strip()
            return [float(x) for x in content.split()]
    
    def _read_bvec_file(self, bvec_file: Path) -> List[List[float]]:
        """Read b-vectors from .bvec file."""
        with open(bvec_file, 'r') as f:
            lines = f.readlines()
            # bvec files have 3 lines (x, y, z components)
            if len(lines) >= 3:
                x = [float(v) for v in lines[0].strip().split()]
                y = [float(v) for v in lines[1].strip().split()]
                z = [float(v) for v in lines[2].strip().split()]
                return [[x[i], y[i], z[i]] for i in range(len(x))]
        return []
    
    @staticmethod
    def infer_bids_paths(input_file: Path) -> tuple:
        """
        Infer BIDS root and subject ID from an input file path.

        Handles both raw BIDS paths and derivatives paths:
          - Raw:        /data/ALC/sub-01/dwi/file.nii.gz
          - Derivatives (new): /data/ALC/sub-01/derivatives/diffyui/dwi/file.nii.gz
          - Derivatives (old): /data/ALC/derivatives/diffyui/sub-01/dwi/file.nii.gz

        Args:
            input_file: Path to the input file

        Returns:
            Tuple of (bids_root: Path or None, subject_id: str or None)
        """
        path_parts = input_file.parts
        subject_id = None
        bids_root = None

        if "derivatives" in path_parts:
            deriv_idx = path_parts.index("derivatives")
            # New structure: sub-XX is the component immediately before "derivatives"
            if deriv_idx > 0 and path_parts[deriv_idx - 1].startswith("sub-"):
                subject_id = path_parts[deriv_idx - 1]
                bids_root = Path(*path_parts[:deriv_idx - 1]) if deriv_idx > 1 else Path("/")
            else:
                # Old structure: sub-XX appears somewhere after "derivatives/pipeline/"
                for i in range(deriv_idx + 1, len(path_parts)):
                    if path_parts[i].startswith("sub-"):
                        subject_id = path_parts[i]
                        bids_root = Path(*path_parts[:deriv_idx])
                        break
        else:
            # Raw BIDS: search for sub-* in path
            for i, part in enumerate(path_parts):
                if part.startswith("sub-"):
                    subject_id = part
                    if i > 0:
                        bids_root = Path(*path_parts[:i])
                    break

        return (bids_root, subject_id)

    def get_derivatives_path(self, subject_id: str, pipeline: str = "diffyui") -> Path:
        """
        Get path for BIDS derivatives directory.
        
        Args:
            subject_id: Subject ID
            pipeline: Pipeline name for derivatives
            
        Returns:
            Path to derivatives directory
        """
        return self.bids_root / subject_id / "derivatives" / pipeline
    
    def write_derivative_file(self, output_file: Path, source_file: Path,
                             metadata: Optional[Dict] = None) -> Path:
        """
        Write a derivative file with proper BIDS naming and metadata.
        
        Args:
            output_file: Path where derivative should be written
            source_file: Source file path (for metadata reference)
            metadata: Additional metadata to include in JSON sidecar
            
        Returns:
            Path to written file
        """
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON sidecar if metadata provided
        if metadata:
            json_file = output_file.with_suffix("").with_suffix(".json")
            source_json = self.get_json_sidecar(source_file)
            if source_json:
                metadata = {**source_json, **metadata}
            
            with open(json_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        return output_file
