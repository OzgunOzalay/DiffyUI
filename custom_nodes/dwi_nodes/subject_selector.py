"""
Subject Selector Node - Extract files for a single subject from BIDS Loader outputs.
"""

from pathlib import Path
from typing import List, Optional


class SubjectSelectorNode:
    """
    Subject Selector Node - Extracts files for a single subject from BIDS Loader outputs.
    Filters the comma-separated file lists to only include files for the specified subject.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "all_subject_ids": ("STRING", {
                    "default": "",
                    "tooltip": "Comma-separated list of all subject IDs from BIDS Loader"
                }),
                "subject_id": ("STRING", {
                    "default": "",
                    "tooltip": "Subject ID to select (e.g., sub-ALC2151). Leave empty to select first subject."
                }),
                "ap_phase_dwi": ("STRING", {
                    "default": "",
                    "tooltip": "All AP phase DWI files from BIDS Loader (comma-separated)"
                }),
                "ap_phase_bvec": ("STRING", {
                    "default": "",
                    "tooltip": "All AP phase bvec files from BIDS Loader (comma-separated)"
                }),
                "ap_phase_bval": ("STRING", {
                    "default": "",
                    "tooltip": "All AP phase bval files from BIDS Loader (comma-separated)"
                }),
                "pa_phase_dwi": ("STRING", {
                    "default": "",
                    "tooltip": "All PA phase DWI files from BIDS Loader (comma-separated)"
                }),
                "pa_phase_bvec": ("STRING", {
                    "default": "",
                    "tooltip": "All PA phase bvec files from BIDS Loader (comma-separated)"
                }),
                "pa_phase_bval": ("STRING", {
                    "default": "",
                    "tooltip": "All PA phase bval files from BIDS Loader (comma-separated)"
                }),
                "t1w_nii": ("STRING", {
                    "default": "",
                    "tooltip": "All T1w files from BIDS Loader (comma-separated)"
                }),
            },
            "optional": {
                "auto_next": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "If true, automatically select next subject when processing completes"
                }),
            }
        }
    
    RETURN_TYPES = (
        "STRING",  # selected_subject_id
        "STRING",  # ap_phase_dwi (single file or comma-separated if multiple)
        "STRING",  # ap_phase_bvec
        "STRING",  # ap_phase_bval
        "STRING",  # pa_phase_dwi
        "STRING",  # pa_phase_bvec
        "STRING",  # pa_phase_bval
        "STRING",  # t1w_nii
    )
    RETURN_NAMES = (
        "subject_id",
        "ap_phase_dwi",
        "ap_phase_bvec",
        "ap_phase_bval",
        "pa_phase_dwi",
        "pa_phase_bvec",
        "pa_phase_bval",
        "t1w_nii",
    )
    FUNCTION = "select_subject"
    CATEGORY = "DWI"
    DESCRIPTION = "Select files for a single subject from BIDS Loader outputs. Filters files to match the specified subject ID."
    
    def select_subject(
        self,
        all_subject_ids: str,
        subject_id: str,
        ap_phase_dwi: str,
        ap_phase_bvec: str,
        ap_phase_bval: str,
        pa_phase_dwi: str,
        pa_phase_bvec: str,
        pa_phase_bval: str,
        t1w_nii: str,
        auto_next: bool = False
    ):
        """
        Select files for a single subject.
        
        Args:
            all_subject_ids: Comma-separated list of all subject IDs
            subject_id: Subject ID to select (empty = first subject)
            ap_phase_dwi: All AP DWI files (comma-separated)
            ap_phase_bvec: All AP bvec files (comma-separated)
            ap_phase_bval: All AP bval files (comma-separated)
            pa_phase_dwi: All PA DWI files (comma-separated)
            pa_phase_bvec: All PA bvec files (comma-separated)
            pa_phase_bval: All PA bval files (comma-separated)
            t1w_nii: All T1w files (comma-separated)
            auto_next: Auto-select next subject (not implemented yet)
            
        Returns:
            Tuple of selected subject's files
        """
        try:
            # Parse all subject IDs (accept string from widget or list from linked BIDS Loader)
            if isinstance(all_subject_ids, list):
                available_subjects = [str(s).strip() for s in all_subject_ids if str(s).strip()]
            elif all_subject_ids:
                available_subjects = [s.strip() for s in str(all_subject_ids).split(",") if s.strip()]
            else:
                available_subjects = []
            
            # Determine which subject to select
            if not subject_id or not subject_id.strip():
                if available_subjects:
                    selected_subject = available_subjects[0]
                    print(f"[Subject Selector] No subject specified, selecting first: {selected_subject}")
                else:
                    raise ValueError("No subjects available and no subject ID specified")
            else:
                selected_subject = subject_id.strip()
                if selected_subject not in available_subjects:
                    print(f"[Subject Selector] WARNING: Subject '{selected_subject}' not in available subjects")
                    print(f"[Subject Selector] Available subjects: {available_subjects}")
                    if available_subjects:
                        selected_subject = available_subjects[0]
                        print(f"[Subject Selector] Falling back to first subject: {selected_subject}")
                    else:
                        raise ValueError(f"Subject '{subject_id}' not found and no subjects available")
            
            print(f"[Subject Selector] Selecting subject: {selected_subject}")
            
            # Filter files for this subject (file_list can be string or list from linked input)
            def filter_files(file_list, subject: str) -> str:
                """Filter comma-separated file list to only include files for this subject."""
                if file_list is None:
                    return ""
                if isinstance(file_list, list):
                    parts = [str(p).strip() for p in file_list if str(p).strip()]
                else:
                    s = str(file_list).strip()
                    if not s:
                        return ""
                    parts = [p.strip() for p in s.split(",") if p.strip()]
                if not parts:
                    return ""
                filtered = [f for f in parts if subject in Path(f).name]
                return ",".join(filtered) if filtered else ""
            
            # Filter all file types
            ap_dwi = filter_files(ap_phase_dwi, selected_subject)
            ap_bvec = filter_files(ap_phase_bvec, selected_subject)
            ap_bval = filter_files(ap_phase_bval, selected_subject)
            pa_dwi = filter_files(pa_phase_dwi, selected_subject)
            pa_bvec = filter_files(pa_phase_bvec, selected_subject)
            pa_bval = filter_files(pa_phase_bval, selected_subject)
            t1w = filter_files(t1w_nii, selected_subject)
            
            # Log results
            print(f"[Subject Selector] Selected files for {selected_subject}:")
            print(f"  AP DWI: {ap_dwi if ap_dwi else 'None'}")
            print(f"  AP bvec: {ap_bvec if ap_bvec else 'None'}")
            print(f"  AP bval: {ap_bval if ap_bval else 'None'}")
            print(f"  PA DWI: {pa_dwi if pa_dwi else 'None'}")
            print(f"  PA bvec: {pa_bvec if pa_bvec else 'None'}")
            print(f"  PA bval: {pa_bval if pa_bval else 'None'}")
            print(f"  T1w: {t1w if t1w else 'None'}")
            
            return (
                selected_subject,
                ap_dwi,
                ap_bvec,
                ap_bval,
                pa_dwi,
                pa_bvec,
                pa_bval,
                t1w,
            )
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[Subject Selector] ERROR: {str(e)}")
            print(f"[Subject Selector] Traceback:\n{error_trace}")
            
            # Return empty strings on error
            return ("", "", "", "", "", "", "", "")
