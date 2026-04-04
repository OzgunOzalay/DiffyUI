"""
FBA Subject 3a Node — Stage: subject-3a
Register each subject's normalised FOD to the population template,
then warp the brain mask to template space.
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


class FBASubject3aNode:
    """
    FBA Subject 3a: register the subject's normalised WM FOD to the population template
    using mrregister, then warp the brain mask to template space with mrtransform.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fba_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Path to the subject FBA directory (from FBA Subject 2)."
                }),
                "template_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Template directory containing wmfod_template.mif (from FBA Template Build)."
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
    FUNCTION = "subject3a"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 7 (subject-3a): register subject normalised FOD to the population template "
        "(mrregister), then warp the brain mask to template space (mrtransform)."
    )

    @classmethod
    def IS_CHANGED(cls, fba_dir, template_dir, nthreads=10):
        try:
            fba = Path(fba_dir)
            fod = fba / "wmfod_norm.mif"
            t = Path(template_dir)
            tmpl = t / "wmfod_template.mif"
            fod_mtime = fod.stat().st_mtime if fod.exists() else 0.0
            tmpl_mtime = tmpl.stat().st_mtime if tmpl.exists() else 0.0
            params = {"fba_dir": fba_dir, "fod_mtime": fod_mtime, "tmpl_mtime": tmpl_mtime}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def subject3a(self, fba_dir, template_dir, nthreads=10):
        print("[FBA Subject3a] ===== FUNCTION CALLED =====")
        try:
            for name, val in [("fba_dir", fba_dir), ("template_dir", template_dir)]:
                if _is_upstream_error(val):
                    print(f"[FBA Subject3a] Upstream error on {name}: {val}")
                    return (val,)

            fba = Path(fba_dir.strip())
            t = Path(template_dir.strip())

            wmfod_norm = fba / "wmfod_norm.mif"
            mask_up = fba / "data_brain_mask_upsampled.mif"
            wmfod_template = t / "wmfod_template.mif"

            for p in [wmfod_norm, mask_up]:
                if not p.exists():
                    err = f"Required file missing: {p}. Run FBA Subject 2 first."
                    print(f"[FBA Subject3a] ERROR: {err}")
                    return (f"Error: {err}",)

            if not wmfod_template.exists():
                err = f"Template not found: {wmfod_template}. Run FBA Template Build first."
                print(f"[FBA Subject3a] ERROR: {err}")
                return (f"Error: {err}",)

            warp_s2t = fba / "subject2template_warp.mif"
            warp_t2s = fba / "template2subject_warp.mif"
            mask_in_tmpl = fba / "dwi_mask_in_template_space.mif"

            # ── Block 1: build param hash ──
            _params = {
                "fba_dir": fba_dir,
                "fod_mtime": wmfod_norm.stat().st_mtime,
                "tmpl_mtime": wmfod_template.stat().st_mtime,
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = fba / ".diffyui_fba_cache.json"
            _expected = [str(mask_in_tmpl)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBASubject3a", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA Subject3a] Cache hit — skipping.")
                return (str(fba),)

            executor = get_executor("mrtrix")

            # Step 9: Register to template
            print("[FBA Subject3a] Registering subject FOD to template (mrregister)")
            rc, _, stderr = executor.execute([
                "mrregister", str(wmfod_norm),
                "-mask1", str(mask_up),
                str(wmfod_template),
                "-nl_warp", str(warp_s2t), str(warp_t2s),
                "-nthreads", str(nthreads), "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"mrregister failed: {stderr}")

            # Step 10: Warp brain mask to template space
            print("[FBA Subject3a] Warping brain mask to template space (mrtransform)")
            rc, _, stderr = executor.execute([
                "mrtransform", str(mask_up),
                "-warp", str(warp_s2t),
                "-interp", "nearest",
                "-datatype", "bit",
                str(mask_in_tmpl),
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"mrtransform (mask warp) failed: {stderr}")

            print(f"[FBA Subject3a] Warps and template-space mask written to {fba}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBASubject3a", _param_hash, _params, _expected)

            return (str(fba),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA Subject3a] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
