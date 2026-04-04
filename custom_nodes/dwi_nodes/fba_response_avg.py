"""
FBA Response Average Node — Stage: response-avg
Average WM/GM/CSF response functions across all subjects using responsemean.
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


def _get_subjects(data_dir: Path, subject_ids_str: str):
    """Return sorted list of subject IDs found in data_dir, or from the provided string."""
    if subject_ids_str and subject_ids_str.strip():
        raw = subject_ids_str.replace(",", " ").replace("\n", " ").split()
        return [s.strip() for s in raw if s.strip()]
    return sorted(p.name for p in data_dir.iterdir()
                  if p.is_dir() and p.name.startswith("sub-"))


class FBAResponseAvgNode:
    """
    FBA Response Average: average WM, GM, and CSF response functions across subjects
    using MRtrix3 responsemean. Outputs group_average_response_*.txt in data_dir.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "data_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Root directory containing sub-* subject folders."
                }),
            },
            "optional": {
                "subject_ids": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Comma- or newline-separated subject IDs (e.g. sub-01,sub-02). Leave empty to use all sub-* in data_dir."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("data_dir",)
    FUNCTION = "response_avg"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 3 (response-avg): average WM, GM, and CSF response functions across all "
        "subjects using responsemean. Run after FBA Subject 1 has completed for all subjects."
    )

    @classmethod
    def IS_CHANGED(cls, data_dir, subject_ids=""):
        try:
            d = Path(data_dir)
            subjects = _get_subjects(d, subject_ids)
            mtimes = []
            for subj in subjects:
                wm = d / subj / "derivatives" / "diffyui" / "dwi" / "FBA" / "wm_response.txt"
                if wm.exists():
                    mtimes.append(wm.stat().st_mtime)
            params = {"mtimes": sorted(mtimes), "subjects": subjects}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def response_avg(self, data_dir, subject_ids=""):
        print("[FBA ResponseAvg] ===== FUNCTION CALLED =====")
        try:
            if _is_upstream_error(data_dir):
                print(f"[FBA ResponseAvg] Upstream error: {data_dir}")
                return (data_dir,)

            d = Path(data_dir.strip())
            if not d.is_dir():
                err = f"data_dir not found: {data_dir}"
                print(f"[FBA ResponseAvg] ERROR: {err}")
                return (f"Error: {err}",)

            subjects = _get_subjects(d, subject_ids)
            if not subjects:
                err = "No subjects found in data_dir"
                print(f"[FBA ResponseAvg] ERROR: {err}")
                return (f"Error: {err}",)

            wm_files, gm_files, csf_files = [], [], []
            for subj in subjects:
                fba = d / subj / "derivatives" / "diffyui" / "dwi" / "FBA"
                wm = fba / "wm_response.txt"
                gm = fba / "gm_response.txt"
                csf = fba / "csf_response.txt"
                if not wm.exists():
                    print(f"[FBA ResponseAvg] WARN: missing wm_response.txt for {subj}, skipping")
                    continue
                wm_files.append(str(wm))
                gm_files.append(str(gm))
                csf_files.append(str(csf))

            if not wm_files:
                err = "No response function files found. Run FBA Subject 1 first."
                print(f"[FBA ResponseAvg] ERROR: {err}")
                return (f"Error: {err}",)

            # ── Block 1: build param hash ──
            mtimes = [Path(f).stat().st_mtime for f in wm_files]
            _params = {"wm_files": sorted(wm_files), "mtimes": sorted(mtimes)}
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = d / ".diffyui_fba_cache.json"
            avg_wm = d / "group_average_response_wm.txt"
            avg_gm = d / "group_average_response_gm.txt"
            avg_csf = d / "group_average_response_csf.txt"
            _expected = [str(avg_wm), str(avg_gm), str(avg_csf)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBAResponseAvg", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA ResponseAvg] Cache hit — skipping.")
                return (str(d),)

            executor = get_executor("mrtrix")

            print(f"[FBA ResponseAvg] Averaging WM response ({len(wm_files)} subjects)")
            rc, _, stderr = executor.execute(["responsemean"] + wm_files + [str(avg_wm)])
            if rc != 0:
                raise RuntimeError(f"responsemean (WM) failed: {stderr}")

            print("[FBA ResponseAvg] Averaging GM response")
            rc, _, stderr = executor.execute(["responsemean"] + gm_files + [str(avg_gm)])
            if rc != 0:
                raise RuntimeError(f"responsemean (GM) failed: {stderr}")

            print("[FBA ResponseAvg] Averaging CSF response")
            rc, _, stderr = executor.execute(["responsemean"] + csf_files + [str(avg_csf)])
            if rc != 0:
                raise RuntimeError(f"responsemean (CSF) failed: {stderr}")

            print(f"[FBA ResponseAvg] Group average response functions written to {d}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBAResponseAvg", _param_hash, _params, _expected)

            return (str(d),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA ResponseAvg] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
