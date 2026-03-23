"""
TBSS 3 Postreg Node - FSL tbss_3_postreg: apply warps, create mean FA and skeleton.
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager


class TBSS3PostregNode:
    """
    Run FSL tbss_3_postreg. Connect project_dir from TBSS 2 Reg.
    Outputs mean_fa_path and mean_fa_skeleton_path for NIfTI Preview / NIfTI Stats.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "project_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Project directory from TBSS 2 Reg (project_dir output)."
                }),
                "use_study_mean": (["Study-derived mean (-S)", "Standard template (-T)"], {
                    "default": "Study-derived mean (-S)",
                    "tooltip": "-S = study mean FA; -T = standard template."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("project_dir", "mean_fa_path", "mean_fa_skeleton_path")
    FUNCTION = "postreg"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = "TBSS step 3: apply warps, create mean FA and mean FA skeleton. Outputs paths for preview/stats."

    @classmethod
    def IS_CHANGED(cls, project_dir, use_study_mean):
        """Re-run only when inputs actually change."""
        try:
            from pathlib import Path
            from ._import_utils import CacheManager
            proj = Path(project_dir).expanduser().resolve()
            _fa_dir = proj / "FA"
            _fa_mtime = _fa_dir.stat().st_mtime if _fa_dir.exists() else 0.0
            params = {"fa_dir_mtime": _fa_mtime, "use_study_mean": use_study_mean}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def postreg(self, project_dir: str, use_study_mean: str):
        try:
            proj = Path(project_dir).expanduser().resolve()
            if not proj.exists() or not proj.is_dir():
                err = f"Project directory not found: {project_dir}"
                print(f"[TBSS 3 Postreg] {err}")
                return (err, err, err)

            flag = "-S" if "Study-derived" in use_study_mean else "-T"

            # ── Block 1+2: hash on proj FA dir mtime + use_study_mean, check cache ──
            _fa_dir = proj / "FA"
            _fa_mtime = _fa_dir.stat().st_mtime if _fa_dir.exists() else 0.0
            _params = {"fa_dir_mtime": _fa_mtime, "use_study_mean": use_study_mean}
            _param_hash = CacheManager.compute_param_hash(_params)
            _cache_path = proj / ".diffyui_tbss_cache.json"
            _mean_fa_pre = str(proj / "stats" / "mean_FA.nii.gz")
            _expected = [_mean_fa_pre]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "TBSS3Postreg", _param_hash, _expected)
            if _is_hit:
                print("[TBSS 3 Postreg] Cache hit — skipping.")
                _mean_fa_h = Path(_cached[0])
                _mean_skel_h = _mean_fa_h.parent / "mean_FA_skeleton.nii.gz"
                return (str(proj), str(_mean_fa_h), str(_mean_skel_h))

            executor = get_executor("fsl")
            cmd = ["tbss_3_postreg", flag]
            return_code, stdout, stderr = executor.execute(cmd, working_dir=str(proj))

            if return_code != 0:
                err = f"tbss_3_postreg failed: {stderr or stdout}"
                print(f"[TBSS 3 Postreg] {err}")
                return (err, err, err)

            # FSL typically writes mean_FA and mean_FA_skeleton into stats/
            stats_dir = proj / "stats"
            mean_fa = stats_dir / "mean_FA.nii.gz"
            mean_skeleton = stats_dir / "mean_FA_skeleton.nii.gz"
            if not mean_fa.exists():
                mean_fa = proj / "mean_FA.nii.gz"
            if not mean_skeleton.exists():
                mean_skeleton = proj / "mean_FA_skeleton.nii.gz"

            print(f"[TBSS 3 Postreg] Success. project_dir={proj}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "TBSS3Postreg", _param_hash, _params, [str(mean_fa)])

            return (str(proj), str(mean_fa), str(mean_skeleton))

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS 3 Postreg] {err}")
            return (err, err, err)
