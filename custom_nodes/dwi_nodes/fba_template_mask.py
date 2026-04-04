"""
FBA Template Mask Node — Stage: template-mask
Intersect all subjects' warped brain masks to create a template mask,
then segment the template FOD to create the fixel analysis mask.
"""

from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


def _get_subjects(data_dir: Path, subject_ids_str: str):
    if subject_ids_str and subject_ids_str.strip():
        raw = subject_ids_str.replace(",", " ").replace("\n", " ").split()
        return [s.strip() for s in raw if s.strip()]
    return sorted(p.name for p in data_dir.iterdir()
                  if p.is_dir() and p.name.startswith("sub-"))


class FBATemplateMaskNode:
    """
    FBA Template Mask: intersect all subjects' warped brain masks (mrmath min) to
    produce template_mask.mif, then segment the template FOD with fod2fixel to
    create the fixel analysis mask (fixel_mask/).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "data_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Root directory containing sub-* subject folders."
                }),
                "template_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Template directory containing wmfod_template.mif (from FBA Template Build)."
                }),
            },
            "optional": {
                "fmls_peak_value": ("FLOAT", {
                    "default": 0.06,
                    "min": 0.01,
                    "max": 0.5,
                    "step": 0.01,
                    "tooltip": "FOD amplitude threshold for fixel segmentation (default 0.06)."
                }),
                "subject_ids": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Comma- or newline-separated subject IDs. Leave empty to use all sub-*."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("template_dir",)
    FUNCTION = "template_mask"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 8 (template-mask): intersect all subjects' warped brain masks to create "
        "template_mask.mif, then segment the template FOD to create fixel_mask/."
    )

    @classmethod
    def IS_CHANGED(cls, data_dir, template_dir, fmls_peak_value=0.06, subject_ids=""):
        try:
            d = Path(data_dir)
            subjects = _get_subjects(d, subject_ids)
            mtimes = []
            for subj in subjects:
                mask = d / subj / "derivatives" / "diffyui" / "dwi" / "FBA" / "dwi_mask_in_template_space.mif"
                if mask.exists():
                    mtimes.append(mask.stat().st_mtime)
            params = {"mtimes": sorted(mtimes), "fmls_peak_value": fmls_peak_value}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def template_mask(self, data_dir, template_dir, fmls_peak_value=0.06, subject_ids=""):
        print("[FBA TemplateMask] ===== FUNCTION CALLED =====")
        try:
            for name, val in [("data_dir", data_dir), ("template_dir", template_dir)]:
                if _is_upstream_error(val):
                    print(f"[FBA TemplateMask] Upstream error on {name}: {val}")
                    return (val,)

            d = Path(data_dir.strip())
            t = Path(template_dir.strip())

            wmfod_template = t / "wmfod_template.mif"
            if not wmfod_template.exists():
                err = f"wmfod_template.mif not found in {template_dir}. Run FBA Template Build first."
                print(f"[FBA TemplateMask] ERROR: {err}")
                return (f"Error: {err}",)

            subjects = _get_subjects(d, subject_ids)
            mask_files = []
            for subj in subjects:
                mask = d / subj / "derivatives" / "diffyui" / "dwi" / "FBA" / "dwi_mask_in_template_space.mif"
                if not mask.exists():
                    print(f"[FBA TemplateMask] WARN: warped mask missing for {subj}, skipping")
                    continue
                mask_files.append(str(mask))

            if not mask_files:
                err = "No warped masks found. Run FBA Subject 3a first."
                print(f"[FBA TemplateMask] ERROR: {err}")
                return (f"Error: {err}",)

            template_mask = t / "template_mask.mif"
            fixel_mask_dir = t / "fixel_mask"

            # ── Block 1: build param hash ──
            _params = {
                "mtimes": sorted(Path(f).stat().st_mtime for f in mask_files),
                "fmls_peak_value": fmls_peak_value,
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = t / ".diffyui_fba_cache.json"
            _expected = [str(fixel_mask_dir / "index.mif")]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBATemplateMask", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA TemplateMask] Cache hit — skipping.")
                return (str(t),)

            executor = get_executor("mrtrix")

            # Step 11: Intersect warped masks
            print(f"[FBA TemplateMask] Computing template mask from {len(mask_files)} subjects (mrmath min)")
            rc, _, stderr = executor.execute(
                ["mrmath"] + mask_files + ["min", str(template_mask), "-datatype", "bit", "-force"]
            )
            if rc != 0:
                raise RuntimeError(f"mrmath min failed: {stderr}")

            # Step 12: Create fixel analysis mask
            print(f"[FBA TemplateMask] Creating fixel analysis mask (fmls_peak_value={fmls_peak_value})")
            if fixel_mask_dir.exists():
                import shutil
                shutil.rmtree(fixel_mask_dir)
            rc, _, stderr = executor.execute([
                "fod2fixel",
                "-mask", str(template_mask),
                "-fmls_peak_value", str(fmls_peak_value),
                str(wmfod_template),
                str(fixel_mask_dir),
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"fod2fixel (fixel_mask) failed: {stderr}")

            print(f"[FBA TemplateMask] Fixel mask created at {fixel_mask_dir}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBATemplateMask", _param_hash, _params, _expected)

            return (str(t),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA TemplateMask] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
