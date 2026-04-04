"""
FBA Prep Node — Stage: prep
Copy eddy-corrected DWI, brain mask, bvecs, and bvals into each subject's FBA folder.
This is the first step of the Fixel-Based Analysis pipeline.
"""

import shutil
from pathlib import Path

from ._import_utils import BIDSHandler, CacheManager, _is_upstream_error


class FBAPrepNode:
    """
    FBA Prep: copy DWI, brain mask, bvecs, and bvals into the subject's FBA working directory.
    Outputs the path to the FBA directory for downstream FBA nodes.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "Eddy-corrected DWI NIfTI file (.nii.gz). Will be copied to fba_dir/data.nii.gz."
                }),
                "brain_mask": ("STRING", {
                    "default": "",
                    "tooltip": "Brain mask MIF file (.mif). Will be copied to fba_dir/data_brain_mask.mif."
                }),
                "bvec_file": ("STRING", {
                    "default": "",
                    "tooltip": "Gradient directions file (.bvec). Will be copied to fba_dir/data.bvecs."
                }),
                "bval_file": ("STRING", {
                    "default": "",
                    "tooltip": "B-value file (.bval). Will be copied to fba_dir/data.bvals."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("fba_dir",)
    FUNCTION = "prep"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 1 (prep): copies the eddy-corrected DWI, brain mask, bvecs, and bvals "
        "into <subject>/derivatives/diffyui/dwi/FBA/. Connect outputs to FBA Subject 1."
    )

    @classmethod
    def IS_CHANGED(cls, dwi_file, brain_mask, bvec_file, bval_file):
        try:
            params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "brain_mask": brain_mask,
                        "bvec_file": bvec_file, "bval_file": bval_file},
                file_keys=["dwi_file", "brain_mask", "bvec_file", "bval_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def prep(self, dwi_file, brain_mask, bvec_file, bval_file):
        print("[FBA Prep] ===== FUNCTION CALLED =====")
        try:
            for name, val in [("dwi_file", dwi_file), ("brain_mask", brain_mask),
                               ("bvec_file", bvec_file), ("bval_file", bval_file)]:
                if _is_upstream_error(val):
                    print(f"[FBA Prep] Upstream error on {name}: {val}")
                    return (val,)
                if not val or not val.strip():
                    err = f"{name} is required"
                    print(f"[FBA Prep] ERROR: {err}")
                    return (f"Error: {err}",)

            dwi_path = Path(dwi_file.strip())
            mask_path = Path(brain_mask.strip())
            bvec_path = Path(bvec_file.strip())
            bval_path = Path(bval_file.strip())

            for p in [dwi_path, mask_path, bvec_path, bval_path]:
                if not p.exists():
                    err = f"File not found: {p}"
                    print(f"[FBA Prep] ERROR: {err}")
                    return (f"Error: {err}",)

            # Infer BIDS layout
            bids_root, subject_id = BIDSHandler.infer_bids_paths(dwi_path)
            if bids_root and subject_id:
                fba_dir = Path(bids_root) / subject_id / "derivatives" / "diffyui" / "dwi" / "FBA"
            else:
                fba_dir = dwi_path.parent / "FBA"

            fba_dir.mkdir(parents=True, exist_ok=True)
            print(f"[FBA Prep] FBA directory: {fba_dir}")

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "brain_mask": brain_mask,
                        "bvec_file": bvec_file, "bval_file": bval_file},
                file_keys=["dwi_file", "brain_mask", "bvec_file", "bval_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = fba_dir / ".diffyui_fba_cache.json"
            _expected = [str(fba_dir)]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "FBAPrep", _param_hash, _expected)
            if _is_hit:
                print("[FBA Prep] Cache hit — skipping.")
                return (str(fba_dir),)

            # Copy files
            dst_dwi = fba_dir / "data.nii.gz"
            dst_mask = fba_dir / "data_brain_mask.mif"
            dst_bvec = fba_dir / "data.bvecs"
            dst_bval = fba_dir / "data.bvals"

            shutil.copy2(dwi_path, dst_dwi)
            print(f"[FBA Prep] Copied DWI → {dst_dwi}")
            shutil.copy2(mask_path, dst_mask)
            print(f"[FBA Prep] Copied brain mask → {dst_mask}")
            shutil.copy2(bvec_path, dst_bvec)
            print(f"[FBA Prep] Copied bvecs → {dst_bvec}")
            shutil.copy2(bval_path, dst_bval)
            print(f"[FBA Prep] Copied bvals → {dst_bval}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBAPrep", _param_hash, _params, _expected)

            print(f"[FBA Prep] Done. fba_dir={fba_dir}")
            return (str(fba_dir),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA Prep] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
