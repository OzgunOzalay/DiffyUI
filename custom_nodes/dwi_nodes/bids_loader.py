"""
BIDS Project Loader — primary entry node for DiffyUI pipelines.

Reads a BIDS dataset root and outputs the dataset path plus a comma-separated
subject list.  The rich text widget shows project metadata and per-subject
completion status so you can see at a glance which subjects need processing.
"""

import json
from pathlib import Path

from ._import_utils import BIDSHandler


class BIDSLoaderNode:
    """
    BIDS Project Loader — scan a BIDS dataset and list all subjects.

    Connect bids_dataset → SubjectBatchRunner (bids_dataset).
    Connect subject_list → SubjectBatchRunner (subject_list).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bids_dataset": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Absolute path to the BIDS dataset root directory.",
                }),
            },
            "optional": {
                "completion_glob": ("STRING", {
                    "default": "dwi/*_FA.nii.gz",
                    "tooltip": (
                        "Glob relative to derivatives/diffyui/{subject}/ used to mark a "
                        "subject as completed in the status display. "
                        "E.g. 'dwi/*_FA.nii.gz' for DTI, 'fba/wmfod_norm.mif' for FBA."
                    ),
                }),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("bids_dataset", "subject_list")
    FUNCTION = "load_project"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Scan a BIDS dataset and list subjects. "
        "Connect outputs to SubjectBatchRunner to process subjects one by one."
    )

    @classmethod
    def IS_CHANGED(cls, bids_dataset="", **kwargs):
        return bids_dataset

    def load_project(self, bids_dataset: str, completion_glob: str = "dwi/*_FA.nii.gz",
                     unique_id: str = None):
        bids_dataset = bids_dataset.strip()
        if not bids_dataset:
            raise ValueError("BIDS dataset path is empty.")

        bids_path = Path(bids_dataset)
        if not bids_path.exists():
            raise ValueError(f"BIDS dataset path does not exist: {bids_dataset}")

        bids = BIDSHandler(bids_dataset)
        subjects = bids.get_all_subjects()
        if not subjects:
            raise ValueError(
                f"No BIDS subjects (sub-*/) found in {bids_dataset}. "
                "Each subject directory must contain an anat/ or dwi/ subfolder."
            )

        project_info = _read_dataset_description(bids_path)
        deriv_root = bids_path / "derivatives" / "diffyui"
        subject_status = _check_completion(subjects, deriv_root, completion_glob)

        display = _format_display(bids_path, project_info, subjects, subject_status, completion_glob)

        print(f"[BIDS Loader] {bids_path.name}: {len(subjects)} subjects")

        return {
            "ui": {"text": [display]},
            "result": (bids_dataset, ",".join(subjects)),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_dataset_description(bids_path: Path) -> dict:
    desc_file = bids_path / "dataset_description.json"
    if desc_file.exists():
        try:
            return json.loads(desc_file.read_text())
        except Exception:
            pass
    return {}


def _check_completion(subjects: list, deriv_root: Path, glob_pattern: str) -> dict:
    """Return {subject_id: True/False} based on whether the glob matches in derivatives."""
    status = {}
    for sub in subjects:
        sub_deriv = deriv_root / sub
        if not glob_pattern.strip():
            status[sub] = sub_deriv.exists()
        else:
            status[sub] = bool(list(sub_deriv.glob(glob_pattern))) if sub_deriv.exists() else False
    return status


def _format_display(bids_path: Path, info: dict, subjects: list,
                    status: dict, completion_glob: str) -> str:
    lines = ["=" * 64, "BIDS Project", "=" * 64]

    name = info.get("Name", bids_path.name)
    version = info.get("BIDSVersion", "")
    lines.append(f"  Project : {name}")
    if version:
        lines.append(f"  BIDS    : {version}")
    lines.append(f"  Path    : {bids_path}")
    lines.append(f"  Subjects: {len(subjects)}")

    done = sum(1 for v in status.values() if v)
    lines.append(f"  Done    : {done}/{len(subjects)}  (glob: {completion_glob or 'n/a'})")
    lines.append("")

    lines.append("Subjects:")
    for sub in subjects:
        mark = "[done]" if status.get(sub) else "[    ]"
        lines.append(f"  {mark}  {sub}")

    lines.append("")
    lines.append("=" * 64)
    return "\n".join(lines)
