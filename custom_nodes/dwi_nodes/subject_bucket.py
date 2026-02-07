"""
Subject Bucket Node - Holds files for a single subject being processed.
Acts as a container/organizer for one subject's data during processing pipeline.
"""

from pathlib import Path


class SubjectBucketNode:
    """
    Subject Bucket Node - Container for a single subject's files.
    This node doesn't process anything, just organizes and passes through the files.
    Useful for clarity in workflow visualization.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subject_id": ("STRING", {
                    "default": "",
                    "tooltip": "Subject ID"
                }),
                "ap_phase_dwi": ("STRING", {
                    "default": "",
                    "tooltip": "AP phase DWI file(s) - comma-separated if multiple"
                }),
                "ap_phase_bvec": ("STRING", {
                    "default": "",
                    "tooltip": "AP phase bvec file"
                }),
                "ap_phase_bval": ("STRING", {
                    "default": "",
                    "tooltip": "AP phase bval file"
                }),
                "pa_phase_dwi": ("STRING", {
                    "default": "",
                    "tooltip": "PA phase DWI file(s) - comma-separated if multiple"
                }),
                "pa_phase_bvec": ("STRING", {
                    "default": "",
                    "tooltip": "PA phase bvec file"
                }),
                "pa_phase_bval": ("STRING", {
                    "default": "",
                    "tooltip": "PA phase bval file"
                }),
                "t1w_nii": ("STRING", {
                    "default": "",
                    "tooltip": "T1w NIfTI file"
                }),
            }
        }
    
    RETURN_TYPES = (
        "STRING",  # subject_id
        "STRING",  # ap_phase_dwi
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
    FUNCTION = "bucket_subject"
    CATEGORY = "DWI"
    DESCRIPTION = "Subject Bucket - Container for one subject's files. Passes through all inputs. Useful for workflow organization."
    OUTPUT_NODE = True
    
    def bucket_subject(
        self,
        subject_id: str,
        ap_phase_dwi: str,
        ap_phase_bvec: str,
        ap_phase_bval: str,
        pa_phase_dwi: str,
        pa_phase_bvec: str,
        pa_phase_bval: str,
        t1w_nii: str
    ):
        """
        Pass through subject files (bucket container).
        
        Args:
            All inputs are passed through as outputs
            
        Returns:
            Tuple of all inputs (pass-through)
        """
        # Validate files exist
        files_to_check = [
            ("AP DWI", ap_phase_dwi),
            ("AP bvec", ap_phase_bvec),
            ("AP bval", ap_phase_bval),
            ("PA DWI", pa_phase_dwi),
            ("PA bvec", pa_phase_bvec),
            ("PA bval", pa_phase_bval),
            ("T1w", t1w_nii),
        ]
        
        def to_path_list(file_path):
            """Normalize string or list from widget/linked input to list of path strings."""
            if file_path is None or file_path == "":
                return []
            if isinstance(file_path, list):
                return [str(p).strip() for p in file_path if str(p).strip()]
            return [p.strip() for p in str(file_path).split(",") if p.strip()]

        missing_files = []
        for file_type, file_path in files_to_check:
            if file_path:
                paths = to_path_list(file_path)
                for path in paths:
                    if not Path(path).exists():
                        missing_files.append(f"{file_type}: {path}")
        
        # Create display text
        display_lines = []
        display_lines.append("=" * 60)
        display_lines.append(f"Subject Bucket: {subject_id or 'N/A'}")
        display_lines.append("=" * 60)
        display_lines.append("")
        
        if missing_files:
            display_lines.append("⚠️  WARNING: Some files not found:")
            for missing in missing_files:
                display_lines.append(f"  • {missing}")
            display_lines.append("")
        
        display_lines.append("Files in bucket:")
        for file_type, file_path in files_to_check:
            if file_path:
                paths = to_path_list(file_path)
                status = "✓" if all(Path(p).exists() for p in paths) else "✗"
                display_lines.append(f"  {status} {file_type}: {len(paths)} file(s)")
                for path in paths[:3]:  # Show first 3
                    display_lines.append(f"      • {Path(path).name}")
                if len(paths) > 3:
                    display_lines.append(f"      ... and {len(paths) - 3} more")
            else:
                display_lines.append(f"  ✗ {file_type}: Not provided")
        
        display_lines.append("")
        display_lines.append("=" * 60)
        
        display_text = "\n".join(display_lines)
        
        print(f"[Subject Bucket] Subject: {subject_id}")
        print(f"[Subject Bucket] Files validated and passed through")
        
        result = (
            subject_id,
            ap_phase_dwi,
            ap_phase_bvec,
            ap_phase_bval,
            pa_phase_dwi,
            pa_phase_bvec,
            pa_phase_bval,
            t1w_nii,
        )
        
        return {
            "ui": {
                "text": [display_text]
            },
            "result": result
        }
