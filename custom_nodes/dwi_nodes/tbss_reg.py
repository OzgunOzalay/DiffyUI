"""
TBSS 2 Reg Node - FSL tbss_2_reg: non-linear registration to template or midpoint.
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager


class TBSS2RegNode:
    """
    Run FSL tbss_2_reg. Connect project_dir from TBSS 1 Preproc.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "project_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Project directory from TBSS 1 Preproc (project_dir output)."
                }),
                "target": (["Template (FMRIB58_FA)", "Mid-point (most representative subject)"], {
                    "default": "Template (FMRIB58_FA)",
                    "tooltip": "Registration target: -T = FMRIB58_FA template, -n = midpoint subject."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("project_dir",)
    FUNCTION = "reg"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = "TBSS step 2: non-linear registration of all FA images to standard space (-T template or -n midpoint)."

    @classmethod
    def IS_CHANGED(cls, project_dir, target):
        """Re-run only when inputs actually change."""
        try:
            from pathlib import Path
            from ._import_utils import CacheManager
            proj = Path(project_dir).expanduser().resolve()
            _fa_dir = proj / "FA"
            _fa_mtime = _fa_dir.stat().st_mtime if _fa_dir.exists() else 0.0
            params = {"fa_dir_mtime": _fa_mtime, "target": target}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def reg(self, project_dir: str, target: str):
        try:
            proj = Path(project_dir).expanduser().resolve()
            if not proj.exists() or not proj.is_dir():
                err = f"Project directory not found: {project_dir}"
                print(f"[TBSS 2 Reg] {err}")
                return (err,)

            flag = "-T" if target.startswith("Template") else "-n"

            # ── Block 1+2: hash on proj FA dir mtime + target, check cache ──
            _fa_dir = proj / "FA"
            _fa_mtime = _fa_dir.stat().st_mtime if _fa_dir.exists() else 0.0
            _params = {"fa_dir_mtime": _fa_mtime, "target": target}
            _param_hash = CacheManager.compute_param_hash(_params)
            _cache_path = proj / ".diffyui_tbss_cache.json"
            # Reg creates warp files inside FA/ subdir; check FA dir still exists
            _expected = [str(_fa_dir)]
            # Use a sentinel file created by tbss_2_reg as proxy (FA/ subdir with .mat files)
            _warp_sentinel = proj / "FA" / "target.nii.gz"
            _files_to_check = [str(_warp_sentinel)] if _warp_sentinel.exists() else _expected
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "TBSS2Reg", _param_hash, _expected, files_to_check=_files_to_check
            )
            if _is_hit:
                print("[TBSS 2 Reg] Cache hit — skipping.")
                return (str(proj),)

            executor = get_executor("fsl")
            cmd = ["tbss_2_reg", flag]
            return_code, stdout, stderr = executor.execute(cmd, working_dir=str(proj))

            if return_code != 0:
                err = f"tbss_2_reg failed: {stderr or stdout}"
                print(f"[TBSS 2 Reg] {err}")
                return (err,)

            print(f"[TBSS 2 Reg] Success. project_dir={proj}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "TBSS2Reg", _param_hash, _params, _expected)

            return (str(proj),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS 2 Reg] {err}")
            return (err,)
