"""
Subject Iterator Node - Iterate through subjects for batch processing.
Outputs one subject ID at a time based on index.
"""

from typing import List


class SubjectIteratorNode:
    """
    Subject Iterator Node - Iterates through subjects for batch processing.
    Takes all subject IDs and outputs one at a time based on index.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "all_subject_ids": ("STRING", {
                    "default": "",
                    "tooltip": "Comma-separated list of all subject IDs from BIDS Loader"
                }),
                "subject_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 1000,
                    "tooltip": "Index of subject to process (0 = first subject, 1 = second, etc.)"
                }),
            },
            "optional": {
                "auto_increment": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "If true, automatically increment index (requires workflow re-execution)"
                }),
            }
        }
    
    RETURN_TYPES = (
        "STRING",  # current_subject_id
        "INT",     # current_index
        "INT",     # total_subjects
        "BOOLEAN", # has_next
        "BOOLEAN", # has_previous
    )
    RETURN_NAMES = (
        "subject_id",
        "current_index",
        "total_subjects",
        "has_next",
        "has_previous",
    )
    FUNCTION = "iterate_subject"
    CATEGORY = "DWI"
    DESCRIPTION = "Iterate through subjects for batch processing. Outputs one subject ID at a time based on index."
    OUTPUT_NODE = True
    
    def iterate_subject(
        self,
        all_subject_ids: str,
        subject_index: int,
        auto_increment: bool = False
    ):
        """
        Get subject ID at specified index.
        
        Args:
            all_subject_ids: Comma-separated list of all subject IDs
            subject_index: Index of subject to get (0-based)
            auto_increment: Whether to auto-increment (not fully automatic in ComfyUI)
            
        Returns:
            Tuple of (subject_id, current_index, total_subjects, has_next, has_previous)
        """
        try:
            # Parse all subject IDs (accept string or list from linked BIDS Loader)
            if isinstance(all_subject_ids, list):
                subjects = [str(s).strip() for s in all_subject_ids if str(s).strip()]
            elif all_subject_ids:
                subjects = [s.strip() for s in str(all_subject_ids).split(",") if s.strip()]
            else:
                subjects = []
            
            total = len(subjects)
            
            if total == 0:
                print("[Subject Iterator] WARNING: No subjects available")
                return ("", 0, 0, False, False)
            
            # Clamp index to valid range
            if subject_index < 0:
                subject_index = 0
            elif subject_index >= total:
                subject_index = total - 1
            
            # Get current subject
            current_subject = subjects[subject_index]
            
            # Determine if there are next/previous subjects
            has_next = subject_index < (total - 1)
            has_previous = subject_index > 0
            
            # Create display text
            display_lines = []
            display_lines.append("=" * 60)
            display_lines.append("Subject Iterator")
            display_lines.append("=" * 60)
            display_lines.append(f"Total Subjects: {total}")
            display_lines.append(f"Current Index: {subject_index}")
            display_lines.append(f"Current Subject: {current_subject}")
            display_lines.append("")
            
            if has_previous:
                display_lines.append(f"← Previous: {subjects[subject_index - 1]}")
            else:
                display_lines.append("← Previous: None (first subject)")
            
            if has_next:
                display_lines.append(f"→ Next: {subjects[subject_index + 1]}")
            else:
                display_lines.append("→ Next: None (last subject)")
            
            display_lines.append("")
            display_lines.append("All Subjects:")
            for i, subj in enumerate(subjects):
                marker = "→" if i == subject_index else " "
                display_lines.append(f"  {marker} [{i}] {subj}")
            
            display_lines.append("")
            display_lines.append("=" * 60)
            display_lines.append("Tip: Change 'subject_index' to process different subjects")
            display_lines.append("=" * 60)
            
            display_text = "\n".join(display_lines)
            
            print(f"[Subject Iterator] Processing subject {subject_index + 1}/{total}: {current_subject}")
            
            result = (
                current_subject,
                subject_index,
                total,
                has_next,
                has_previous,
            )
            
            return {
                "ui": {
                    "text": [display_text]
                },
                "result": result
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[Subject Iterator] ERROR: {str(e)}")
            print(f"[Subject Iterator] Traceback:\n{error_trace}")
            
            # Return empty/zero values on error
            return {
                "ui": {
                    "text": [f"ERROR: {str(e)}"]
                },
                "result": ("", 0, 0, False, False)
            }
