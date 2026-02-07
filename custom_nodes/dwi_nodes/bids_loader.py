"""
BIDS Loader Node - Primary input node for loading BIDS datasets.
Scans anat/ and dwi/ folders and outputs all available files and metadata.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Import utils using helper module
from ._import_utils import BIDSHandler, get_executor, FileManager


class BIDSLoaderNode:
    """
    BIDS Loader Node - Scans BIDS dataset and outputs all available files.
    This is the PRIMARY INPUT node for the DWI processing pipeline.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bids_dataset": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Path to BIDS dataset root directory. All subjects will be processed."
                }),
            },
            "optional": {},
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }
    
    RETURN_TYPES = (
        "STRING",  # bids_dataset path
        "STRING",  # all_subject_ids (comma-separated)
        "STRING",  # AP phase dwi (comma-separated paths)
        "STRING",  # AP phase bvec (comma-separated paths)
        "STRING",  # AP phase bval (comma-separated paths)
        "STRING",  # PA phase dwi (comma-separated paths)
        "STRING",  # PA phase bvec (comma-separated paths)
        "STRING",  # PA phase bval (comma-separated paths)
        "STRING",  # T1w nii (comma-separated paths)
    )
    RETURN_NAMES = (
        "bids_dataset",
        "all_subject_ids",
        "AP_phase_dwi",
        "AP_phase_bvec",
        "AP_phase_bval",
        "PA_phase_dwi",
        "PA_phase_bvec",
        "PA_phase_bval",
        "T1w_nii",
    )
    FUNCTION = "load_bids"
    CATEGORY = "DWI"
    DESCRIPTION = "Load BIDS dataset and scan for all available files in anat/ and dwi/ folders. Processes all subjects automatically. Use dataset_info output to see all available subjects and files."
    OUTPUT_NODE = True
    
    def load_bids(self, bids_dataset: str, unique_id: str = None):
        """
        Load and scan BIDS dataset for all available files.
        Processes all subjects automatically.
        
        Args:
            bids_dataset: Path to BIDS dataset root
            
        Returns:
            Tuple of (bids_dataset, all_subject_ids, all_dwi_nii, ...)
        """
        # Debug: Log that function was called
        print(f"[BIDS Loader] Called with dataset={bids_dataset}")
        
        try:
            # Validate bids_dataset path
            if not bids_dataset or not bids_dataset.strip():
                raise ValueError("BIDS dataset path is empty. Please provide a valid path.")
            
            # Normalize path - handle relative paths and common mount points
            bids_path = Path(bids_dataset)
            
            # Try to resolve common paths
            possible_paths = [bids_path]
            
            # If path doesn't start with /, try common mount points
            if not bids_dataset.startswith('/'):
                possible_paths.extend([
                    Path('/app/data') / bids_dataset,
                    Path('/app/data') / bids_path.name,
                    Path('/app') / bids_dataset,
                ])
            
            # Also try /app/data directly if user just gave a name
            if '/' not in bids_dataset and not bids_dataset.startswith('.'):
                possible_paths.append(Path('/app/data') / bids_dataset)
            
            # Find first existing path
            bids_path = None
            for p in possible_paths:
                if p.exists():
                    bids_path = p
                    print(f"[BIDS Loader] Found path: {bids_path}")
                    break
            
            # If still not found, check what's available in /app/data
            if bids_path is None:
                data_dir = Path('/app/data')
                available_dirs = []
                if data_dir.exists():
                    try:
                        available_dirs = [d.name for d in data_dir.iterdir() if d.is_dir()]
                    except Exception:
                        pass
                
                error_msg = (
                    f"BIDS dataset path does not exist: {bids_dataset}\n\n"
                    f"IMPORTANT: Use absolute paths to your BIDS dataset!\n\n"
                    f"Tried paths:\n"
                )
                for p in possible_paths:
                    error_msg += f"  - {p} (exists: {p.exists()})\n"
                
                if available_dirs:
                    error_msg += f"\n✓ Found {len(available_dirs)} directories in /app/data:\n"
                    for d in available_dirs[:10]:
                        error_msg += f"  - /app/data/{d}\n"
                    if len(available_dirs) > 10:
                        error_msg += f"  ... and {len(available_dirs) - 10} more\n"
                    error_msg += f"\n→ Try using: /app/data/{available_dirs[0] if available_dirs else 'your_dataset'}\n"
                else:
                    error_msg += f"\n✗ No directories found in /app/data\n"
                    error_msg += f"\nTo fix this:\n"
                    error_msg += f"1. Create ./data folder in your DiffyUI directory\n"
                    error_msg += f"2. Copy your BIDS dataset to ./data/ALC (or your dataset name)\n"
                    error_msg += f"3. Use path: /app/data/ALC in the node\n"
                    error_msg += f"\nExample structure:\n"
                    error_msg += f"  ./data/\n"
                    error_msg += f"    └── ALC/\n"
                    error_msg += f"        ├── anat/\n"
                    error_msg += f"        └── dwi/\n"
                
                error_msg += (
                    f"\nCurrent working directory: {Path.cwd()}\n"
                    f"Data directory exists: {data_dir.exists()}\n"
                )
                
                print(f"[BIDS Loader] ERROR: Path does not exist. Tried: {possible_paths}")
                raise ValueError(error_msg)
            
            # Update bids_dataset to the resolved path
            bids_dataset = str(bids_path)
            
            print(f"[BIDS Loader] Path exists: {bids_path.exists()}, Path: {bids_path}")
            print(f"[BIDS Loader] Path is directory: {bids_path.is_dir()}")
            if bids_path.exists() and bids_path.is_dir():
                try:
                    contents = list(bids_path.iterdir())[:5]
                    print(f"[BIDS Loader] Path contents (first 5): {[str(c.name) for c in contents]}")
                except Exception as e:
                    print(f"[BIDS Loader] Could not list directory contents: {e}")
            
            # Initialize BIDS handler
            bids = BIDSHandler(bids_dataset)
            
            # Get all available subjects first (before validation, in case structure is different)
            all_subjects = bids.get_all_subjects()
            total_subjects = len(all_subjects)
            
            print(f"[BIDS Loader] Found {total_subjects} subjects: {all_subjects[:5]}")
            
            # Check structure, but be more lenient
            structure_valid = bids.validate_structure()
            if not structure_valid and total_subjects == 0:
                # Try to provide helpful error
                error_msg = (
                    f"BIDS structure validation failed.\n"
                    f"Expected folders: {bids.anat_dir} and {bids.dwi_dir}\n"
                    f"Anat folder exists: {bids.anat_dir.exists()}\n"
                    f"DWI folder exists: {bids.dwi_dir.exists()}\n"
                    f"Found {total_subjects} subjects.\n"
                    f"Please check your BIDS dataset structure."
                )
                raise ValueError(error_msg)
            
            # Process all subjects - collect only the files we care about
            print(f"[BIDS Loader] Processing all {total_subjects} subjects")
            
            # Collect only specific files across all subjects
            ap_dwi = []
            ap_bvec = []
            ap_bval = []
            pa_dwi = []
            pa_bvec = []
            pa_bval = []
            t1w_nii = []
            
            for subject_id in all_subjects:
                print(f"[BIDS Loader] Processing subject: {subject_id}")
                
                # Get DWI directory
                dwi_dir = bids.bids_root / subject_id / "dwi"
                anat_dir = bids.bids_root / subject_id / "anat"
                
                if dwi_dir.exists():
                    # Find AP phase files
                    for ext in [".nii.gz", ".nii"]:
                        ap_files = list(dwi_dir.glob(f"*_dir-AP_dwi{ext}"))
                        ap_dwi.extend([str(f) for f in ap_files])
                    
                    # Find PA phase files
                    for ext in [".nii.gz", ".nii"]:
                        pa_files = list(dwi_dir.glob(f"*_dir-PA_dwi{ext}"))
                        pa_dwi.extend([str(f) for f in pa_files])
                    
                    # Find corresponding bvec and bval files for AP
                    for ap_file in ap_dwi:
                        base = Path(ap_file).with_suffix("").with_suffix("")
                        bvec_file = base.with_suffix(".bvec")
                        bval_file = base.with_suffix(".bval")
                        if bvec_file.exists() and str(bvec_file) not in ap_bvec:
                            ap_bvec.append(str(bvec_file))
                        if bval_file.exists() and str(bval_file) not in ap_bval:
                            ap_bval.append(str(bval_file))
                    
                    # Find corresponding bvec and bval files for PA
                    for pa_file in pa_dwi:
                        base = Path(pa_file).with_suffix("").with_suffix("")
                        bvec_file = base.with_suffix(".bvec")
                        bval_file = base.with_suffix(".bval")
                        if bvec_file.exists() and str(bvec_file) not in pa_bvec:
                            pa_bvec.append(str(bvec_file))
                        if bval_file.exists() and str(bval_file) not in pa_bval:
                            pa_bval.append(str(bval_file))
                
                if anat_dir.exists():
                    # Find T1w files
                    for ext in [".nii.gz", ".nii"]:
                        t1w_files = list(anat_dir.glob(f"*T1w{ext}"))
                        t1w_nii.extend([str(f) for f in t1w_files])
            
            # Format display text
            display_text = self._format_simple_display(
                bids_dataset, all_subjects, total_subjects,
                ap_dwi, ap_bvec, ap_bval,
                pa_dwi, pa_bvec, pa_bval,
                t1w_nii
            )
            
            # Return all files as comma-separated strings
            all_subject_ids_str = ",".join(all_subjects)
            
            result = (
                bids_dataset,
                all_subject_ids_str,
                ",".join(sorted(ap_dwi)),
                ",".join(sorted(ap_bvec)),
                ",".join(sorted(ap_bval)),
                ",".join(sorted(pa_dwi)),
                ",".join(sorted(pa_bvec)),
                ",".join(sorted(pa_bval)),
                ",".join(sorted(t1w_nii)),
            )
            
            print(f"[BIDS Loader] Processed {total_subjects} subjects")
            print(f"[BIDS Loader] Found files:")
            print(f"  - AP phase DWI: {len(ap_dwi)}")
            print(f"  - AP phase bvec: {len(ap_bvec)}")
            print(f"  - AP phase bval: {len(ap_bval)}")
            print(f"  - PA phase DWI: {len(pa_dwi)}")
            print(f"  - PA phase bvec: {len(pa_bvec)}")
            print(f"  - PA phase bval: {len(pa_bval)}")
            print(f"  - T1w NIfTI: {len(t1w_nii)}")
            
            return {
                "ui": {
                    "text": [display_text]
                },
                "result": result
            }
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            error_info = {
                "error": str(e),
                "bids_dataset": bids_dataset,
                "traceback": error_trace
            }
            error_text = f"""
{'=' * 50}
ERROR Loading BIDS Dataset
{'=' * 50}
Error: {str(e)}

BIDS Dataset: {bids_dataset}

Debug Info:
- Dataset path exists: {Path(bids_dataset).exists() if bids_dataset else 'N/A'}
- Dataset path: {bids_dataset}

{'=' * 50}
Full Traceback:
{error_trace}
{'=' * 50}
"""
            result = (
                bids_dataset,
                "",
                "",  # AP phase dwi
                "",  # AP phase bvec
                "",  # AP phase bval
                "",  # PA phase dwi
                "",  # PA phase bvec
                "",  # PA phase bval
                "",  # T1w nii
            )
            return {"ui": {"text": [error_text]}, "result": result}
    
    def _find_mask_files(self, bids: BIDSHandler, subject_id: str) -> List[Path]:
        """Find mask files in anat folder."""
        mask_files = []
        
        anat_search = bids.bids_root / subject_id / "anat"
        
        if anat_search.exists():
            # Common mask file patterns
            mask_patterns = [
                "*mask*.nii.gz",
                "*brainmask*.nii.gz",
                "*mask*.nii",
                "*brain_mask*.nii.gz",
            ]
            for pattern in mask_patterns:
                mask_files.extend(list(anat_search.glob(pattern)))
        
        return sorted(set(mask_files))  # Remove duplicates and sort
    
    
    def _format_simple_display(
        self, bids_dataset: str, all_subjects: List[str], total_subjects: int,
        ap_dwi: List[str], ap_bvec: List[str], ap_bval: List[str],
        pa_dwi: List[str], pa_bvec: List[str], pa_bval: List[str],
        t1w_nii: List[str]
    ) -> str:
        """Format display text for all subjects with simplified file list."""
        lines = []
        lines.append("=" * 70)
        lines.append("BIDS Dataset - All Subjects Processed")
        lines.append("=" * 70)
        lines.append(f"Dataset: {Path(bids_dataset).name}")
        lines.append(f"Full Path: {bids_dataset}")
        lines.append(f"Total Subjects: {total_subjects}")
        lines.append("")
        
        # File counts summary
        lines.append("File Summary:")
        lines.append(f"  AP phase DWI: {len(ap_dwi)}")
        lines.append(f"  AP phase bvec: {len(ap_bvec)}")
        lines.append(f"  AP phase bval: {len(ap_bval)}")
        lines.append(f"  PA phase DWI: {len(pa_dwi)}")
        lines.append(f"  PA phase bvec: {len(pa_bvec)}")
        lines.append(f"  PA phase bval: {len(pa_bval)}")
        lines.append(f"  T1w NIfTI: {len(t1w_nii)}")
        lines.append("")
        
        # List AP files
        if ap_dwi:
            lines.append("AP Phase DWI Files:")
            for f in ap_dwi[:10]:
                lines.append(f"  • {Path(f).name}")
            if len(ap_dwi) > 10:
                lines.append(f"  ... and {len(ap_dwi) - 10} more")
            lines.append("")
        
        # List PA files
        if pa_dwi:
            lines.append("PA Phase DWI Files:")
            for f in pa_dwi[:10]:
                lines.append(f"  • {Path(f).name}")
            if len(pa_dwi) > 10:
                lines.append(f"  ... and {len(pa_dwi) - 10} more")
            lines.append("")
        
        # List T1w files
        if t1w_nii:
            lines.append("T1w NIfTI Files:")
            for f in t1w_nii[:10]:
                lines.append(f"  • {Path(f).name}")
            if len(t1w_nii) > 10:
                lines.append(f"  ... and {len(t1w_nii) - 10} more")
            lines.append("")
        
        # List subjects
        lines.append("Subjects:")
        for subject_id in all_subjects[:20]:  # Show first 20
            lines.append(f"  • {subject_id}")
        if len(all_subjects) > 20:
            lines.append(f"  ... and {len(all_subjects) - 20} more subjects")
        
        lines.append("")
        lines.append("=" * 70)
        lines.append("Files are available as separate outputs (comma-separated)")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def _format_display_info(self, dataset_info: Dict, availability: Dict[str, bool] = None) -> str:
        """Format dataset information for display in widget."""
        if availability is None:
            availability = {}
        
        # Status symbols
        AVAILABLE = "✓"
        NOT_AVAILABLE = "✗"
        
        lines = []
        lines.append("=" * 50)
        lines.append("BIDS Dataset Information")
        lines.append("=" * 50)
        lines.append(f"Dataset: {dataset_info.get('bids_dataset', 'N/A')}")
        lines.append(f"Subject: {dataset_info.get('subject_id', 'N/A')}")
        lines.append(f"BIDS Structure Valid: {dataset_info.get('bids_structure_valid', False)}")
        lines.append("")
        
        # Output Availability Summary
        lines.append("Output Availability:")
        lines.append(f"  {AVAILABLE if availability.get('dwi_file') else NOT_AVAILABLE} DWI File")
        lines.append(f"  {AVAILABLE if availability.get('dwi_json') else NOT_AVAILABLE} DWI JSON Metadata")
        lines.append(f"  {AVAILABLE if availability.get('bval_file') else NOT_AVAILABLE} B-values File")
        lines.append(f"  {AVAILABLE if availability.get('bvec_file') else NOT_AVAILABLE} B-vectors File")
        lines.append(f"  {AVAILABLE if availability.get('t1_file') else NOT_AVAILABLE} T1 File")
        lines.append(f"  {AVAILABLE if availability.get('t2_file') else NOT_AVAILABLE} T2 File")
        lines.append(f"  {AVAILABLE if availability.get('mask_file') else NOT_AVAILABLE} Mask File")
        lines.append("")
        
        # DWI Information
        dwi_info = dataset_info.get('dwi', {})
        lines.append("DWI Data:")
        lines.append(f"  Files Found: {dwi_info.get('files_found', 0)}")
        if dwi_info.get('primary_file'):
            status = AVAILABLE if availability.get('dwi_file') else NOT_AVAILABLE
            lines.append(f"  {status} Primary File: {Path(dwi_info['primary_file']).name}")
        
        dwi_meta = dwi_info.get('metadata', {})
        if dwi_meta:
            if 'b_values' in dwi_meta:
                bval_info = dwi_meta['b_values']
                lines.append(f"  B-values: {bval_info.get('count', 0)} volumes")
                if bval_info.get('unique_values'):
                    unique = bval_info['unique_values']
                    lines.append(f"    Unique b-values: {len(unique)} ({', '.join(map(str, unique[:5]))}{'...' if len(unique) > 5 else ''})")
                    lines.append(f"    Range: {bval_info.get('min')} - {bval_info.get('max')} s/mm²")
            
            if dwi_meta.get('PhaseEncodingDirection'):
                lines.append(f"  Phase Encoding: {dwi_meta['PhaseEncodingDirection']}")
            if dwi_meta.get('RepetitionTime'):
                lines.append(f"  TR: {dwi_meta['RepetitionTime']} s")
            if dwi_meta.get('EchoTime'):
                lines.append(f"  TE: {dwi_meta['EchoTime']} s")
        
        if 'file_info' in dwi_info:
            file_info = dwi_info['file_info']
            lines.append(f"  File Size: {file_info.get('size_mb', 0)} MB")
            if file_info.get('shape'):
                lines.append(f"  Dimensions: {file_info['shape']}")
        
        lines.append("")
        
        # Anatomical Information
        anat_info = dataset_info.get('anatomical', {})
        lines.append("Anatomical Data:")
        t1_status = AVAILABLE if availability.get('t1_file') else NOT_AVAILABLE
        lines.append(f"  {t1_status} T1 Files: {anat_info.get('t1_files_found', 0)}")
        if anat_info.get('t1_files'):
            lines.append(f"    {Path(anat_info['t1_files'][0]).name}")
        t2_status = AVAILABLE if availability.get('t2_file') else NOT_AVAILABLE
        lines.append(f"  {t2_status} T2 Files: {anat_info.get('t2_files_found', 0)}")
        mask_status = AVAILABLE if availability.get('mask_file') else NOT_AVAILABLE
        lines.append(f"  {mask_status} Mask Files: {anat_info.get('mask_files_found', 0)}")
        if anat_info.get('mask_files'):
            lines.append(f"    {Path(anat_info['mask_files'][0]).name}")
        
        # Gradient table availability
        lines.append("")
        lines.append("Gradient Table:")
        bval_status = AVAILABLE if availability.get('bval_file') else NOT_AVAILABLE
        bvec_status = AVAILABLE if availability.get('bvec_file') else NOT_AVAILABLE
        lines.append(f"  {bval_status} B-values file")
        lines.append(f"  {bvec_status} B-vectors file")
        
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Force re-execution if inputs change
        return float("nan")
