"""
FBA Subject 2 Node — Stage: subject-2
Multi-tissue FOD estimation (msmt_csd) + multi-tissue intensity normalisation (mtnormalise).
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


class FBASubject2Node:
    """
    FBA Subject 2: compute multi-tissue FODs (WM, GM, CSF) using msmt_csd with the
    group-averaged response functions, then normalise with mtnormalise.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fba_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Path to the subject FBA directory (from FBA Subject 1)."
                }),
                "data_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Data root containing group_average_response_wm/gm/csf.txt (from FBA Response Average)."
                }),
            },
            "optional": {
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
    FUNCTION = "subject2"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 4 (subject-2): compute multi-tissue FODs (msmt_csd) using group-averaged "
        "response functions, then perform multi-tissue intensity normalisation (mtnormalise)."
    )

    @classmethod
    def IS_CHANGED(cls, fba_dir, data_dir, nthreads=10):
        try:
            fba = Path(fba_dir)
            up = fba / "data_upsampled.mif"
            mtime = up.stat().st_mtime if up.exists() else 0.0
            d = Path(data_dir)
            wm = d / "group_average_response_wm.txt"
            wm_mtime = wm.stat().st_mtime if wm.exists() else 0.0
            params = {"fba_dir": fba_dir, "data_mtime": mtime, "wm_mtime": wm_mtime}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def subject2(self, fba_dir, data_dir, nthreads=10):
        print("[FBA Subject2] ===== FUNCTION CALLED =====")
        try:
            for name, val in [("fba_dir", fba_dir), ("data_dir", data_dir)]:
                if _is_upstream_error(val):
                    print(f"[FBA Subject2] Upstream error on {name}: {val}")
                    return (val,)

            fba = Path(fba_dir.strip())
            d = Path(data_dir.strip())

            if not fba.is_dir():
                err = f"FBA directory not found: {fba_dir}"
                print(f"[FBA Subject2] ERROR: {err}")
                return (f"Error: {err}",)

            avg_wm = d / "group_average_response_wm.txt"
            avg_gm = d / "group_average_response_gm.txt"
            avg_csf = d / "group_average_response_csf.txt"
            for p in [avg_wm, avg_gm, avg_csf]:
                if not p.exists():
                    err = f"Group response file missing: {p}. Run FBA Response Average first."
                    print(f"[FBA Subject2] ERROR: {err}")
                    return (f"Error: {err}",)

            data_up = fba / "data_upsampled.mif"
            mask_up = fba / "data_brain_mask_upsampled.mif"
            bvecs = fba / "data.bvecs"
            bvals = fba / "data.bvals"
            for p in [data_up, mask_up, bvecs, bvals]:
                if not p.exists():
                    err = f"Required file missing: {p}. Run FBA Subject 1 first."
                    print(f"[FBA Subject2] ERROR: {err}")
                    return (f"Error: {err}",)

            wmfod_norm = fba / "wmfod_norm.mif"

            # ── Block 1: build param hash ──
            _params = {
                "fba_dir": fba_dir,
                "data_mtime": data_up.stat().st_mtime,
                "wm_mtime": avg_wm.stat().st_mtime,
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = fba / ".diffyui_fba_cache.json"
            _expected = [str(wmfod_norm)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBASubject2", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA Subject2] Cache hit — skipping.")
                return (str(fba),)

            executor = get_executor("mrtrix")

            # Step 4: Multi-tissue FOD estimation
            print("[FBA Subject2] Computing multi-tissue FODs (msmt_csd)")
            rc, _, stderr = executor.execute([
                "dwi2fod", "msmt_csd", str(data_up),
                str(avg_wm), str(fba / "wmfod.mif"),
                str(avg_gm), str(fba / "gm.mif"),
                str(avg_csf), str(fba / "csf.mif"),
                "-mask", str(mask_up),
                "-fslgrad", str(bvecs), str(bvals),
                "-nthreads", str(nthreads), "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"dwi2fod msmt_csd failed: {stderr}")

            # Step 5: Intensity normalisation
            print("[FBA Subject2] Multi-tissue intensity normalisation (mtnormalise)")
            rc, _, stderr = executor.execute([
                "mtnormalise",
                str(fba / "wmfod.mif"), str(wmfod_norm),
                str(fba / "gm.mif"), str(fba / "gm_norm.mif"),
                str(fba / "csf.mif"), str(fba / "csf_norm.mif"),
                "-mask", str(mask_up),
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"mtnormalise failed: {stderr}")

            print(f"[FBA Subject2] Normalised FODs written to {fba}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBASubject2", _param_hash, _params, _expected)

            return (str(fba),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA Subject2] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
