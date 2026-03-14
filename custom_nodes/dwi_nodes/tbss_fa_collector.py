"""
TBSS FA Collector Node - Gathers FA images from BIDS derivatives for TBSS pipeline.
Inputs match BIDS Loader outputs (bids_dataset, all_subject_ids).
"""

from pathlib import Path

from ._import_utils import BIDSHandler


class TBSSFACollectorNode:
    """
    Collect FA images from derivatives/diffyui/sub-*/dwi/*_FA.nii.gz into a single
    directory for TBSS 1 Preproc. Connect BIDS Loader bids_dataset and optionally
    all_subject_ids to this node.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bids_dataset": ("STRING", {
                    "default": "",
                    "tooltip": "BIDS dataset root. Connect from BIDS Loader → bids_dataset."
                }),
            },
            "optional": {
                "all_subject_ids": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Comma- or newline-separated subject IDs (e.g. from BIDS Loader). If empty, use all subjects under derivatives."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("fa_directory",)
    FUNCTION = "collect_fa"
    CATEGORY = "DWI"
    DESCRIPTION = "Gather FA images from BIDS derivatives/diffyui into one directory for TBSS. Connect bids_dataset (and optionally all_subject_ids) from BIDS Loader."

    def collect_fa(self, bids_dataset: str, all_subject_ids: str = ""):
        try:
            bids_root = Path(bids_dataset).expanduser().resolve()
            if not bids_root.exists() or not bids_root.is_dir():
                err = f"BIDS dataset not found or not a directory: {bids_dataset}"
                print(f"[TBSS FA Collector] {err}")
                return (err,)

            bids = BIDSHandler(str(bids_root))
            derivatives_root = bids_root / "derivatives" / "diffyui"

            if not derivatives_root.exists():
                err = f"No derivatives/diffyui found at {derivatives_root}"
                print(f"[TBSS FA Collector] {err}")
                return (err,)

            # Resolve subject list
            if all_subject_ids and str(all_subject_ids).strip():
                raw = str(all_subject_ids).replace(",", " ").replace("\n", " ").split()
                subject_ids = [s.strip() for s in raw if s.strip() and s.strip().startswith("sub-")]
                if not subject_ids:
                    subject_ids = [s.strip() for s in raw if s.strip()]
            else:
                subject_ids = bids.get_all_subjects()
                if not subject_ids:
                    err = "No subjects found in BIDS root"
                    print(f"[TBSS FA Collector] {err}")
                    return (err,)

            # Collect all *_FA.nii.gz from derivatives/diffyui/sub-XX/dwi/
            fa_files = []  # (subject_id, path)
            for sid in subject_ids:
                dwi_dir = derivatives_root / sid / "dwi"
                if not dwi_dir.exists():
                    continue
                for fa in dwi_dir.glob("*_FA.nii.gz"):
                    fa_files.append((sid, fa))

            if not fa_files:
                err = f"No *_FA.nii.gz found under {derivatives_root} for subjects {subject_ids}"
                print(f"[TBSS FA Collector] {err}")
                return (err,)

            # Output directory: derivatives/diffyui/tbss_fa
            fa_directory = derivatives_root / "tbss_fa"
            fa_directory.mkdir(parents=True, exist_ok=True)

            for sid, fa_path in fa_files:
                # Unique name per subject to avoid overwrites (e.g. sub-01_foo_FA.nii.gz)
                link_name = f"{sid}_{fa_path.name}"
                link_path = fa_directory / link_name
                if link_path.exists():
                    continue
                try:
                    link_path.symlink_to(fa_path.resolve())
                except OSError:
                    import shutil
                    shutil.copy2(fa_path, link_path)

            print(f"[TBSS FA Collector] Collected {len(fa_files)} FA images into {fa_directory}")
            return (str(fa_directory),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS FA Collector] {err}")
            return (err,)
