"""
FBA Template Build Node — Stage: template-build
Build the FOD population template using MRtrix3 population_template.
This is the longest step in the FBA pipeline.
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


class FBATemplateBuildNode:
    """
    FBA Template Build: run population_template to build a group FOD template from
    subjects' normalised wmfod images. This step can take hours on a large cohort.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Template directory containing fod_input/ and mask_input/ (from FBA Template Prep)."
                }),
            },
            "optional": {
                "voxel_size": ("FLOAT", {
                    "default": 1.25,
                    "min": 0.5,
                    "max": 3.0,
                    "step": 0.05,
                    "tooltip": "Voxel size of the output template in mm (default 1.25)."
                }),
                "nthreads": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 64,
                    "tooltip": "Number of threads for population_template."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("template_dir",)
    FUNCTION = "template_build"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 6 (template-build): build the FOD population template with "
        "population_template. WARNING: This step can take many hours for large cohorts."
    )

    @classmethod
    def IS_CHANGED(cls, template_dir, voxel_size=1.25, nthreads=10):
        try:
            t = Path(template_dir)
            fod_input = t / "fod_input"
            if not fod_input.is_dir():
                return float("nan")
            mtimes = sorted(f.stat().st_mtime for f in fod_input.glob("*.mif") if f.is_file() or f.is_symlink())
            params = {"mtimes": mtimes, "voxel_size": voxel_size, "template_dir": str(t)}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def template_build(self, template_dir, voxel_size=1.25, nthreads=10):
        print("[FBA TemplateBuild] ===== FUNCTION CALLED =====")
        try:
            if _is_upstream_error(template_dir):
                print(f"[FBA TemplateBuild] Upstream error: {template_dir}")
                return (template_dir,)

            t = Path(template_dir.strip())
            fod_input = t / "fod_input"
            mask_input = t / "mask_input"
            wmfod_template = t / "wmfod_template.mif"

            if not fod_input.is_dir():
                err = f"fod_input/ not found in {template_dir}. Run FBA Template Prep first."
                print(f"[FBA TemplateBuild] ERROR: {err}")
                return (f"Error: {err}",)

            fod_files = sorted(fod_input.glob("*.mif"))
            if not fod_files:
                err = "No FOD files found in fod_input/. Run FBA Template Prep first."
                print(f"[FBA TemplateBuild] ERROR: {err}")
                return (f"Error: {err}",)

            # ── Block 1: build param hash ──
            mtimes = sorted(f.stat().st_mtime for f in fod_files)
            _params = {"mtimes": mtimes, "voxel_size": voxel_size, "template_dir": str(t)}
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = t / ".diffyui_fba_cache.json"
            _expected = [str(wmfod_template)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBATemplateBuild", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA TemplateBuild] Cache hit — skipping.")
                return (str(t),)

            executor = get_executor("mrtrix")

            scratch_dir = t / "tmp_population_template"
            scratch_dir.mkdir(parents=True, exist_ok=True)

            cmd = [
                "population_template", str(fod_input),
                "-mask_dir", str(mask_input),
                str(wmfod_template),
                "-voxel_size", str(voxel_size),
                "-scratch", str(scratch_dir),
                "-nthreads", str(nthreads),
                "-force",
            ]
            print(f"[FBA TemplateBuild] Running population_template ({len(fod_files)} subjects) — this may take a very long time")
            print(f"[FBA TemplateBuild] Command: {' '.join(cmd)}")

            # population_template can run for hours — no timeout
            rc, _, stderr = executor.execute(cmd)
            if rc != 0:
                raise RuntimeError(f"population_template failed: {stderr}")

            print(f"[FBA TemplateBuild] Template written to {wmfod_template}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBATemplateBuild", _param_hash, _params, _expected)

            return (str(t),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA TemplateBuild] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
