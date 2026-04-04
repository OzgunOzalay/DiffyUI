"""
TBSS 1 Preproc Node - FSL tbss_1_preproc: scale/crop FA, create FA/ and origdata/.
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


class TBSS1PreprocNode:
    """
    Run FSL tbss_1_preproc on a directory of FA images. Connect fa_directory from
    TBSS FA Collector or provide path manually.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fa_directory": ("STRING", {
                    "default": "",
                    "tooltip": "Path to directory containing FA .nii.gz files. Connect from TBSS FA Collector → fa_directory or enter manually."
                }),
            },
            "optional": {
                "pattern": ("STRING", {
                    "default": "*FA*.nii.gz",
                    "tooltip": "Glob pattern for FA files (e.g. *FA*.nii.gz or *_FA.nii.gz)."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("project_dir",)
    FUNCTION = "preproc"
    CATEGORY = "DWI/TBSS"
    OUTPUT_NODE = True
    DESCRIPTION = "TBSS step 1: preprocess FA images (scale, crop, remove outer slices). Creates FA/ and origdata/ in the project directory."

    @classmethod
    def IS_CHANGED(cls, fa_directory, pattern="*FA*.nii.gz"):
        """Re-run only when inputs actually change."""
        try:
            from pathlib import Path
            from ._import_utils import CacheManager
            proj = Path(fa_directory).expanduser().resolve()
            fa_list = sorted(proj.glob(pattern)) if proj.exists() else []
            _proj_stat = proj.stat() if proj.exists() else None
            params = {
                "fa_names": sorted(f.name for f in fa_list),
                "pattern": pattern,
                "proj_mtime": _proj_stat.st_mtime if _proj_stat else 0.0,
            }
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def preproc(self, fa_directory: str, pattern: str = "*FA*.nii.gz"):
        try:
            if _is_upstream_error(fa_directory):
                print(f"[TBSS 1 Preproc] Upstream error: {fa_directory}")
                return (fa_directory,)
            proj = Path(fa_directory).expanduser().resolve()
            if not proj.exists() or not proj.is_dir():
                err = f"FA directory not found: {fa_directory}"
                print(f"[TBSS 1 Preproc] {err}")
                return (err,)

            fa_list = sorted(proj.glob(pattern.strip() or "*FA*.nii.gz"))
            if not fa_list:
                err = f"No FA files matching '{pattern}' in {proj}"
                print(f"[TBSS 1 Preproc] {err}")
                return (err,)

            # ── Block 1+2: hash on sorted FA names + proj dir mtime, check cache ──
            _proj_stat = proj.stat()
            _params = {
                "fa_names": sorted(f.name for f in fa_list),
                "pattern": pattern,
                "proj_mtime": _proj_stat.st_mtime,
            }
            _param_hash = CacheManager.compute_param_hash(_params)
            _cache_path = proj / ".diffyui_tbss_cache.json"
            _fa_dir = proj / "FA"
            _origdata_dir = proj / "origdata"
            _expected = [str(_fa_dir), str(_origdata_dir)]
            _is_hit, _cached = CacheManager.check_cache(_cache_path, "TBSS1Preproc", _param_hash, _expected)
            if _is_hit:
                print("[TBSS 1 Preproc] Cache hit — skipping.")
                return (str(proj),)

            executor = get_executor("fsl")
            # FSL tbss_1_preproc expects filenames as arguments (run from project dir)
            cmd = ["tbss_1_preproc"] + [str(f.name) for f in fa_list]
            return_code, stdout, stderr = executor.execute(cmd, working_dir=str(proj))

            if return_code != 0:
                err = f"tbss_1_preproc failed: {stderr or stdout}"
                print(f"[TBSS 1 Preproc] {err}")
                return (err,)

            print(f"[TBSS 1 Preproc] Success. project_dir={proj}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "TBSS1Preproc", _param_hash, _params, _expected)

            return (str(proj),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS 1 Preproc] {err}")
            return (err,)
