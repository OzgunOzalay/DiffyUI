"""
FBA Log FC + FDC Node — Stage: logfc-fdc
Compute log(FC) for normally distributed statistics and FDC (FD × FC) for all subjects.
"""

import shutil
from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


def _get_subjects(data_dir: Path, subject_ids_str: str):
    if subject_ids_str and subject_ids_str.strip():
        raw = subject_ids_str.replace(",", " ").replace("\n", " ").split()
        return [s.strip() for s in raw if s.strip()]
    return sorted(p.name for p in data_dir.iterdir()
                  if p.is_dir() and p.name.startswith("sub-"))


class FBALogFCFDCNode:
    """
    FBA Log FC + FDC: compute log(FC) for normally distributed group analysis,
    and FDC = FD × FC as a combined diffusion measure, for all subjects.
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
                    "tooltip": "Template directory containing fd/ and fc/ fixel data (from FBA Subject 3b)."
                }),
            },
            "optional": {
                "subject_ids": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Comma- or newline-separated subject IDs. Leave empty to use all sub-*."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("template_dir",)
    FUNCTION = "logfc_fdc"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 10 (logfc-fdc): compute log(FC) (for normally distributed statistics) "
        "and FDC = FD × FC (combined fibre density and cross-section) for all subjects."
    )

    @classmethod
    def IS_CHANGED(cls, data_dir, template_dir, subject_ids=""):
        try:
            d = Path(data_dir)
            t = Path(template_dir)
            subjects = _get_subjects(d, subject_ids)
            mtimes = []
            for subj in subjects:
                fc = t / "fc" / f"{subj}.mif"
                if fc.exists():
                    mtimes.append(fc.stat().st_mtime)
            params = {"subjects": subjects, "mtimes": sorted(mtimes)}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def logfc_fdc(self, data_dir, template_dir, subject_ids=""):
        print("[FBA LogFCFDC] ===== FUNCTION CALLED =====")
        try:
            for name, val in [("data_dir", data_dir), ("template_dir", template_dir)]:
                if _is_upstream_error(val):
                    print(f"[FBA LogFCFDC] Upstream error on {name}: {val}")
                    return (val,)

            d = Path(data_dir.strip())
            t = Path(template_dir.strip())

            fc_dir = t / "fc"
            fd_dir = t / "fd"
            if not fc_dir.is_dir() or not fd_dir.is_dir():
                err = "fd/ or fc/ not found in template_dir. Run FBA Subject 3b for all subjects first."
                print(f"[FBA LogFCFDC] ERROR: {err}")
                return (f"Error: {err}",)

            subjects = _get_subjects(d, subject_ids)
            # Filter to subjects that have fc data
            available = [s for s in subjects if (fc_dir / f"{s}.mif").exists()]
            if not available:
                err = "No subject FC files found. Run FBA Subject 3b first."
                print(f"[FBA LogFCFDC] ERROR: {err}")
                return (f"Error: {err}",)

            # ── Block 1: build param hash ──
            _params = {
                "subjects": available,
                "mtimes": sorted((fc_dir / f"{s}.mif").stat().st_mtime for s in available),
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = t / ".diffyui_fba_cache.json"
            log_fc_dir = t / "log_fc"
            fdc_dir = t / "fdc"
            last_subj = available[-1]
            _expected = [str(log_fc_dir / f"{last_subj}.mif"), str(fdc_dir / f"{last_subj}.mif")]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBALogFCFDC", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA LogFCFDC] Cache hit — skipping.")
                return (str(t),)

            # Set up log_fc and fdc directories with structural files
            for out_dir in [log_fc_dir, fdc_dir]:
                out_dir.mkdir(parents=True, exist_ok=True)
                for f in ["index.mif", "directions.mif"]:
                    dst = out_dir / f
                    src = fc_dir / f
                    if not dst.exists() and src.exists():
                        shutil.copy2(src, dst)

            executor = get_executor("mrtrix")

            for subj in available:
                fc_file = fc_dir / f"{subj}.mif"
                fd_file = fd_dir / f"{subj}.mif"
                log_fc_file = log_fc_dir / f"{subj}.mif"
                fdc_file = fdc_dir / f"{subj}.mif"

                # Step 18: log(FC)
                if not log_fc_file.exists():
                    print(f"[FBA LogFCFDC] {subj}: computing log(FC)")
                    rc, _, stderr = executor.execute([
                        "mrcalc", str(fc_file), "-log", str(log_fc_file), "-force"
                    ])
                    if rc != 0:
                        raise RuntimeError(f"mrcalc log(FC) failed for {subj}: {stderr}")

                # Step 19: FDC = FD × FC
                if not fdc_file.exists():
                    if not fd_file.exists():
                        print(f"[FBA LogFCFDC] WARN: fd/{subj}.mif missing, skipping FDC")
                        continue
                    print(f"[FBA LogFCFDC] {subj}: computing FDC")
                    rc, _, stderr = executor.execute([
                        "mrcalc", str(fd_file), str(fc_file), "-mult", str(fdc_file), "-force"
                    ])
                    if rc != 0:
                        raise RuntimeError(f"mrcalc FDC failed for {subj}: {stderr}")

            print(f"[FBA LogFCFDC] log_fc and fdc written to {t}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBALogFCFDC", _param_hash, _params, _expected)

            return (str(t),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA LogFCFDC] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
