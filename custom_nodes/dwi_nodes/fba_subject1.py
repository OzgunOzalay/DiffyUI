"""
FBA Subject 1 Node — Stage: subject-1
Upsample DWI and brain mask; estimate 3-tissue response functions (dhollander algorithm).
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


class FBASubject1Node:
    """
    FBA Subject 1: upsample DWI + mask to target voxel size, then estimate
    WM/GM/CSF response functions using dwi2response dhollander.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fba_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Path to the subject FBA directory (from FBA Prep)."
                }),
            },
            "optional": {
                "voxel_size": ("FLOAT", {
                    "default": 1.25,
                    "min": 0.5,
                    "max": 3.0,
                    "step": 0.05,
                    "tooltip": "Upsampled voxel size in mm (default 1.25)."
                }),
                "nthreads": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 64,
                    "tooltip": "Number of threads for MRtrix3 commands."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("fba_dir",)
    FUNCTION = "subject1"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 2 (subject-1): upsample DWI and brain mask to the target voxel size, "
        "then estimate 3-tissue (WM/GM/CSF) response functions with dwi2response dhollander."
    )

    @classmethod
    def IS_CHANGED(cls, fba_dir, voxel_size=1.25, nthreads=10):
        try:
            fba = Path(fba_dir)
            data_mif = fba / "data.nii.gz"
            mtime = data_mif.stat().st_mtime if data_mif.exists() else 0.0
            params = {"fba_dir": fba_dir, "data_mtime": mtime, "voxel_size": voxel_size}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def subject1(self, fba_dir, voxel_size=1.25, nthreads=10):
        print("[FBA Subject1] ===== FUNCTION CALLED =====")
        try:
            if _is_upstream_error(fba_dir):
                print(f"[FBA Subject1] Upstream error: {fba_dir}")
                return (fba_dir,)

            fba = Path(fba_dir.strip())
            if not fba.is_dir():
                err = f"FBA directory not found: {fba_dir}"
                print(f"[FBA Subject1] ERROR: {err}")
                return (f"Error: {err}",)

            data_nii = fba / "data.nii.gz"
            data_mif = fba / "data.mif"
            data_up = fba / "data_upsampled.mif"
            mask_mif = fba / "data_brain_mask.mif"
            mask_up = fba / "data_brain_mask_upsampled.mif"
            wm_resp = fba / "wm_response.txt"
            bvecs = fba / "data.bvecs"
            bvals = fba / "data.bvals"

            for p in [data_nii, mask_mif, bvecs, bvals]:
                if not p.exists():
                    err = f"Required file missing: {p}"
                    print(f"[FBA Subject1] ERROR: {err}")
                    return (f"Error: {err}",)

            # ── Block 1: build param hash ──
            _params = {
                "fba_dir": fba_dir,
                "data_mtime": data_nii.stat().st_mtime,
                "voxel_size": voxel_size,
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = fba / ".diffyui_fba_cache.json"
            _expected = [str(wm_resp)]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "FBASubject1", _param_hash, _expected)
            if _is_hit:
                print("[FBA Subject1] Cache hit — skipping.")
                return (str(fba),)

            executor = get_executor("mrtrix")

            # Step 1: Convert NIfTI → MIF
            print(f"[FBA Subject1] Converting DWI to MIF")
            rc, stdout, stderr = executor.execute(
                ["mrconvert", str(data_nii), str(data_mif), "-force",
                 "-nthreads", str(nthreads)]
            )
            if rc != 0:
                raise RuntimeError(f"mrconvert failed: {stderr}")

            # Step 2: Upsample DWI
            print(f"[FBA Subject1] Upsampling DWI to {voxel_size}mm")
            rc, stdout, stderr = executor.execute(
                ["mrgrid", str(data_mif), "regrid", "-vox", str(voxel_size),
                 str(data_up), "-force", "-nthreads", str(nthreads)]
            )
            if rc != 0:
                raise RuntimeError(f"mrgrid (DWI) failed: {stderr}")

            # Step 3: Upsample brain mask
            print(f"[FBA Subject1] Upsampling brain mask to {voxel_size}mm")
            rc, stdout, stderr = executor.execute(
                ["mrgrid", str(mask_mif), "regrid", "-vox", str(voxel_size),
                 "-interp", "nearest", str(mask_up), "-force",
                 "-nthreads", str(nthreads)]
            )
            if rc != 0:
                raise RuntimeError(f"mrgrid (mask) failed: {stderr}")

            # Step 4: Estimate 3-tissue response functions
            print(f"[FBA Subject1] Estimating response functions (dhollander)")
            rc, stdout, stderr = executor.execute(
                ["dwi2response", "dhollander", str(data_up),
                 "-fslgrad", str(bvecs), str(bvals),
                 str(fba / "wm_response.txt"),
                 str(fba / "gm_response.txt"),
                 str(fba / "csf_response.txt"),
                 "-nthreads", str(nthreads), "-force"]
            )
            if rc != 0:
                raise RuntimeError(f"dwi2response failed: {stderr}")

            print(f"[FBA Subject1] Response functions saved to {fba}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBASubject1", _param_hash, _params, _expected)

            return (str(fba),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA Subject1] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
