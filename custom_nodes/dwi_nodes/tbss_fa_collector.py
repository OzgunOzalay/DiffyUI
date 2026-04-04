"""
TBSS FA Collector Node - Gathers FA images from BIDS derivatives for TBSS pipeline.
Inputs match BIDS Loader outputs (bids_dataset, all_subject_ids).
"""

from pathlib import Path

from ._import_utils import BIDSHandler, CacheManager


class TBSSFACollectorNode:
    """
    Collect FA images from sub-*/derivatives/diffyui/dwi/DTI/*_FA.nii.gz into a single
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
    CATEGORY = "DWI/TBSS"
    OUTPUT_NODE = True
    DESCRIPTION = "Gather FA images from BIDS derivatives/diffyui into one directory for TBSS. Connect bids_dataset (and optionally all_subject_ids) from BIDS Loader."

    @classmethod
    def IS_CHANGED(cls, bids_dataset, all_subject_ids=""):
        """Re-run only when FA files or subject list changes."""
        try:
            from pathlib import Path
            from ._import_utils import CacheManager, BIDSHandler
            bids_root = Path(bids_dataset).expanduser().resolve()
            if not bids_root.exists():
                return float("nan")
            bids = BIDSHandler(str(bids_root))
            if all_subject_ids and str(all_subject_ids).strip():
                raw = str(all_subject_ids).replace(",", " ").replace("\n", " ").split()
                subject_ids = [s.strip() for s in raw if s.strip()]
            else:
                subject_ids = bids.get_all_subjects()
            fa_files = []
            for sid in subject_ids:
                # New structure: bids_root/sub-XX/derivatives/diffyui/dwi/DTI/
                dti_dir = bids_root / sid / "derivatives" / "diffyui" / "dwi" / "DTI"
                if dti_dir.exists():
                    fa_files.extend(dti_dir.glob("*_FA.nii.gz"))
            _fa_info = sorted(
                [(str(fa.resolve()), fa.stat().st_mtime, fa.stat().st_size) for fa in fa_files]
            )
            params = {"fa_info": _fa_info, "all_subject_ids": all_subject_ids}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def collect_fa(self, bids_dataset: str, all_subject_ids: str = ""):
        try:
            bids_root = Path(bids_dataset).expanduser().resolve()
            if not bids_root.exists() or not bids_root.is_dir():
                err = f"BIDS dataset not found or not a directory: {bids_dataset}"
                print(f"[TBSS FA Collector] {err}")
                return (err,)

            bids = BIDSHandler(str(bids_root))

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

            # Collect all *_FA.nii.gz from sub-XX/derivatives/diffyui/dwi/DTI/
            fa_files = []  # (subject_id, path)
            for sid in subject_ids:
                dti_dir = bids_root / sid / "derivatives" / "diffyui" / "dwi" / "DTI"
                if not dti_dir.exists():
                    print(f"[TBSS FA Collector] DTI dir not found for {sid}: {dti_dir}")
                    continue
                for fa in dti_dir.glob("*_FA.nii.gz"):
                    fa_files.append((sid, fa))

            if not fa_files:
                err = f"No *_FA.nii.gz found in sub-*/derivatives/diffyui/dwi/DTI/ for subjects {subject_ids}"
                print(f"[TBSS FA Collector] {err}")
                return (err,)

            # Output directory: bids_root/derivatives/tbss_fa (project-level, not per-subject)
            fa_directory = bids_root / "derivatives" / "tbss_fa"
            fa_directory.mkdir(parents=True, exist_ok=True)

            # ── Block 1+2: build hash from sorted FA file stats and check cache ──
            _fa_info = sorted(
                [(str(fa.resolve()), fa.stat().st_mtime, fa.stat().st_size) for _, fa in fa_files]
            )
            _params = {"fa_info": _fa_info, "all_subject_ids": all_subject_ids}
            _param_hash = CacheManager.compute_param_hash(_params)
            _cache_path = fa_directory / ".diffyui_tbss_cache.json"
            _expected = [str(fa_directory)]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "TBSSFACollector", _param_hash, _expected)
            if _is_hit:
                # Verify the directory still contains FA files — symlinks may have broken
                _cached_dir = Path(_cached[0])
                if _cached_dir.exists() and list(_cached_dir.glob("*FA*.nii.gz")):
                    print("[TBSS FA Collector] Cache hit — skipping.")
                    return tuple(_cached)
                print("[TBSS FA Collector] Cache hit but FA files missing — re-running.")

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

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "TBSSFACollector", _param_hash, _params, [str(fa_directory)])

            return (str(fa_directory),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS FA Collector] {err}")
            return (err,)
