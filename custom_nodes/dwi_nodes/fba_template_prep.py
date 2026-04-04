"""
FBA Template Prep Node — Stage: template-prep
Create template directories and symbolic links to each subject's normalised FOD and brain mask.
"""

from pathlib import Path

from ._import_utils import CacheManager, _is_upstream_error


def _get_subjects(data_dir: Path, subject_ids_str: str):
    if subject_ids_str and subject_ids_str.strip():
        raw = subject_ids_str.replace(",", " ").replace("\n", " ").split()
        return [s.strip() for s in raw if s.strip()]
    return sorted(p.name for p in data_dir.iterdir()
                  if p.is_dir() and p.name.startswith("sub-"))


class FBATemplatePrepNode:
    """
    FBA Template Prep: create template/fod_input/ and template/mask_input/ directories,
    then create symbolic links pointing to each subject's wmfod_norm.mif and
    data_brain_mask_upsampled.mif. Used to feed population_template.
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
                    "tooltip": "Directory where the FOD template will be built. Will contain fod_input/ and mask_input/."
                }),
            },
            "optional": {
                "subject_ids": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Comma- or newline-separated subject IDs for template building. Leave empty to use all sub-*."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("template_dir",)
    FUNCTION = "template_prep"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 5 (template-prep): create template/fod_input/ and template/mask_input/ "
        "directories with symbolic links to each subject's normalised FOD and brain mask. "
        "Recommended to use 30-40 representative subjects for large studies."
    )

    @classmethod
    def IS_CHANGED(cls, data_dir, template_dir, subject_ids=""):
        try:
            d = Path(data_dir)
            subjects = _get_subjects(d, subject_ids)
            mtimes = []
            for subj in subjects:
                fod = d / subj / "derivatives" / "diffyui" / "dwi" / "FBA" / "wmfod_norm.mif"
                if fod.exists():
                    mtimes.append(fod.stat().st_mtime)
            params = {"subjects": subjects, "mtimes": sorted(mtimes), "template_dir": template_dir}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def template_prep(self, data_dir, template_dir, subject_ids=""):
        print("[FBA TemplatePrep] ===== FUNCTION CALLED =====")
        try:
            for name, val in [("data_dir", data_dir), ("template_dir", template_dir)]:
                if _is_upstream_error(val):
                    print(f"[FBA TemplatePrep] Upstream error on {name}: {val}")
                    return (val,)

            d = Path(data_dir.strip())
            t = Path(template_dir.strip())

            if not d.is_dir():
                err = f"data_dir not found: {data_dir}"
                print(f"[FBA TemplatePrep] ERROR: {err}")
                return (f"Error: {err}",)

            subjects = _get_subjects(d, subject_ids)
            if not subjects:
                err = "No subjects found in data_dir"
                print(f"[FBA TemplatePrep] ERROR: {err}")
                return (f"Error: {err}",)

            # Collect FOD files to build cache hash
            fod_files = []
            for subj in subjects:
                fod = d / subj / "derivatives" / "diffyui" / "dwi" / "FBA" / "wmfod_norm.mif"
                if fod.exists():
                    fod_files.append(fod)

            # ── Block 1: build param hash ──
            _params = {
                "subjects": subjects,
                "mtimes": sorted(f.stat().st_mtime for f in fod_files),
                "template_dir": str(t),
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = t / ".diffyui_fba_cache.json" if t.exists() else d / ".diffyui_fba_tmpl_cache.json"
            _expected = [str(t)]
            t.mkdir(parents=True, exist_ok=True)
            _cache_path = t / ".diffyui_fba_cache.json"

            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBATemplatePrep", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA TemplatePrep] Cache hit — skipping.")
                return (str(t),)

            fod_input = t / "fod_input"
            mask_input = t / "mask_input"
            fod_input.mkdir(parents=True, exist_ok=True)
            mask_input.mkdir(parents=True, exist_ok=True)

            count = 0
            for subj in subjects:
                fba = d / subj / "derivatives" / "diffyui" / "dwi" / "FBA"
                fod_src = fba / "wmfod_norm.mif"
                mask_src = fba / "data_brain_mask_upsampled.mif"

                if not fod_src.exists():
                    print(f"[FBA TemplatePrep] WARN: wmfod_norm.mif missing for {subj}, skipping")
                    continue
                if not mask_src.exists():
                    print(f"[FBA TemplatePrep] WARN: upsampled mask missing for {subj}, skipping")
                    continue

                fod_link = fod_input / f"{subj}.mif"
                mask_link = mask_input / f"{subj}.mif"

                for link, src in [(fod_link, fod_src), (mask_link, mask_src)]:
                    if link.is_symlink():
                        link.unlink()
                    link.symlink_to(src.resolve())

                count += 1
                print(f"[FBA TemplatePrep] Symlinked {subj}")

            print(f"[FBA TemplatePrep] Prepared {count} subjects in {t}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBATemplatePrep", _param_hash, _params, _expected)

            return (str(t),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA TemplatePrep] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
