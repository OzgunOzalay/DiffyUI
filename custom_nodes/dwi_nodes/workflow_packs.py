"""
Workflow Pack nodes — unpack a BIDS_SUBJECT bundle into the file paths
each analysis workflow needs.

DWIPreprocPack   → raw DWI inputs for the preprocessing pipeline
DerivedFilePicker → pick any processed file from derivatives (TBSS, FBA, etc.)

Note: separate pack nodes are used instead of a single "mode" dropdown
because ComfyUI's RETURN_TYPES are fixed at class definition time and
cannot change based on a widget value.
"""

from pathlib import Path

from .bids_subject_type import BIDS_SUBJECT


class DWIPreprocPack:
    """
    Unpack a BIDS_SUBJECT into the raw DWI file paths needed by the
    standard DWI preprocessing pipeline (BrainMask → Denoise → Topup → Eddy → …).

    Outputs empty strings for any file that is not present in the BIDS
    dataset (e.g. dwi_pa / bvec_pa / bval_pa when there is no reverse-phase).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subject": (BIDS_SUBJECT, {}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("subject_id", "dwi_ap", "bvec_ap", "bval_ap", "dwi_pa", "bvec_pa", "bval_pa", "t1w")
    FUNCTION = "unpack"
    CATEGORY = "DiffyUI/Packs"
    OUTPUT_NODE = False
    DESCRIPTION = (
        "Unpack a BIDS_SUBJECT into raw DWI file paths for the preprocessing pipeline. "
        "Connect subject from SubjectBatchRunner and wire outputs into BrainMask, Denoise, "
        "Topup, and Eddy nodes."
    )

    @classmethod
    def IS_CHANGED(cls, subject=None, **kwargs):
        if isinstance(subject, dict):
            return subject.get("subject_id", float("nan"))
        return float("nan")

    def unpack(self, subject):
        files = subject.get("files", {}) if isinstance(subject, dict) else {}
        sid = subject.get("subject_id", "") if isinstance(subject, dict) else ""

        # Support both AP/PA labelled and single-phase DWI
        dwi_ap   = files.get("dwi_ap",   files.get("dwi",   ""))
        bvec_ap  = files.get("bvec_ap",  files.get("bvec",  ""))
        bval_ap  = files.get("bval_ap",  files.get("bval",  ""))
        dwi_pa   = files.get("dwi_pa",   "")
        bvec_pa  = files.get("bvec_pa",  "")
        bval_pa  = files.get("bval_pa",  "")
        t1w      = files.get("t1w",      "")

        return (sid, dwi_ap, bvec_ap, bval_ap, dwi_pa, bvec_pa, bval_pa, t1w)


class DerivedFilePicker:
    """
    Pick a processed file from a subject's derivatives folder.

    Use this to feed downstream workflows that consume outputs produced
    by an earlier pipeline stage (e.g. FA maps for TBSS, normalised FODs
    for FBA group analysis).

    file_pattern examples
    ---------------------
    DTI FA map         : dwi/DTI/*_FA.nii.gz
    DTI MD map         : dwi/DTI/*_MD.nii.gz
    Eddy-corrected DWI : dwi/*_eddy_corrected.nii.gz
    Brain mask         : dwi/*_brain_mask.nii.gz
    FBA WM FOD (norm)  : fba/wmfod_norm.mif
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subject": (BIDS_SUBJECT, {}),
                "file_pattern": ("STRING", {
                    "default": "dwi/DTI/*_FA.nii.gz",
                    "tooltip": (
                        "Glob pattern relative to derivatives/diffyui/{subject_id}/. "
                        "Returns the first match (sorted). "
                        "Examples: 'dwi/DTI/*_FA.nii.gz', 'fba/wmfod_norm.mif'"
                    ),
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("subject_id", "file_path")
    FUNCTION = "pick"
    CATEGORY = "DiffyUI/Packs"
    OUTPUT_NODE = False
    DESCRIPTION = (
        "Pick a processed file from derivatives/diffyui/{subject}/ using a glob pattern. "
        "Use for feeding TBSS, FBA group steps, or any downstream node that needs "
        "a specific output from the preprocessing pipeline."
    )

    @classmethod
    def IS_CHANGED(cls, subject=None, file_pattern="", **kwargs):
        sid = subject.get("subject_id", "") if isinstance(subject, dict) else ""
        return f"{sid}::{file_pattern}"

    def pick(self, subject, file_pattern: str = ""):
        if not isinstance(subject, dict):
            return ("", "")

        sid = subject.get("subject_id", "")
        deriv_root = Path(subject.get("derivatives_root", ""))

        if not file_pattern.strip() or not deriv_root.exists():
            return (sid, "")

        matches = sorted(deriv_root.glob(file_pattern.strip()))
        file_path = str(matches[0]) if matches else ""

        if not file_path:
            print(f"[DerivedFilePicker] No match for '{file_pattern}' in {deriv_root}")

        return (sid, file_path)
