"""
FBA Subject 3b Node — Stage: subject-3b
Warp FOD to template space, segment fixels, reorient, assign to template fixels (FD),
and compute fibre cross-section (FC).
"""

import shutil
from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


class FBASubject3bNode:
    """
    FBA Subject 3b: warp the normalised FOD to template space (without reorientation),
    segment fixels and estimate FD, reorient fixels using the warp Jacobian,
    assign subject fixels to template fixels (FD), and compute fibre cross-section (FC).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fba_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Path to the subject FBA directory (from FBA Subject 3a)."
                }),
                "template_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Template directory containing fixel_mask/ (from FBA Template Mask)."
                }),
                "subject_id": ("STRING", {
                    "default": "",
                    "tooltip": "Subject ID (e.g. sub-01). Used to name output fixel files in template_dir/fd/ and template_dir/fc/."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("fba_dir",)
    FUNCTION = "subject3b"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 9 (subject-3b): warp FOD to template space, segment fixels (FD), "
        "reorient fixels, assign to template (FD), and compute fibre cross-section (FC). "
        "Run after FBA Template Mask."
    )

    @classmethod
    def IS_CHANGED(cls, fba_dir, template_dir, subject_id):
        try:
            fba = Path(fba_dir)
            fod = fba / "wmfod_norm.mif"
            t = Path(template_dir)
            fixel_mask = t / "fixel_mask" / "index.mif"
            fod_mtime = fod.stat().st_mtime if fod.exists() else 0.0
            fm_mtime = fixel_mask.stat().st_mtime if fixel_mask.exists() else 0.0
            params = {"fba_dir": fba_dir, "fod_mtime": fod_mtime, "fm_mtime": fm_mtime,
                      "subject_id": subject_id}
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def subject3b(self, fba_dir, template_dir, subject_id):
        print("[FBA Subject3b] ===== FUNCTION CALLED =====")
        try:
            for name, val in [("fba_dir", fba_dir), ("template_dir", template_dir),
                               ("subject_id", subject_id)]:
                if _is_upstream_error(val):
                    print(f"[FBA Subject3b] Upstream error on {name}: {val}")
                    return (val,)
                if not val or not str(val).strip():
                    err = f"{name} is required"
                    print(f"[FBA Subject3b] ERROR: {err}")
                    return (f"Error: {err}",)

            fba = Path(fba_dir.strip())
            t = Path(template_dir.strip())
            subj = subject_id.strip()

            wmfod_norm = fba / "wmfod_norm.mif"
            warp_s2t = fba / "subject2template_warp.mif"
            fixel_mask_dir = t / "fixel_mask"
            template_mask = t / "template_mask.mif"

            for p in [wmfod_norm, warp_s2t]:
                if not p.exists():
                    err = f"Required file missing: {p}. Run FBA Subject 3a first."
                    print(f"[FBA Subject3b] ERROR: {err}")
                    return (f"Error: {err}",)

            for p in [fixel_mask_dir, template_mask]:
                if not p.exists():
                    err = f"Required path missing: {p}. Run FBA Template Mask first."
                    print(f"[FBA Subject3b] ERROR: {err}")
                    return (f"Error: {err}",)

            # Ensure fd/ and fc/ exist with index.mif + directions.mif from fixel_mask
            for metric in ["fd", "fc"]:
                metric_dir = t / metric
                metric_dir.mkdir(parents=True, exist_ok=True)
                for f in ["index.mif", "directions.mif"]:
                    dst = metric_dir / f
                    src = fixel_mask_dir / f
                    if not dst.exists() and src.exists():
                        shutil.copy2(src, dst)

            fod_not_reoriented = fba / "fod_in_template_space_NOT_REORIENTED.mif"
            fixel_not_reoriented = fba / "fixel_in_template_space_NOT_REORIENTED"
            fixel_reoriented = fba / "fixel_in_template_space"

            # ── Block 1: build param hash ──
            _params = {
                "fba_dir": fba_dir,
                "fod_mtime": wmfod_norm.stat().st_mtime,
                "fm_mtime": (fixel_mask_dir / "index.mif").stat().st_mtime,
                "subject_id": subj,
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = fba / ".diffyui_fba_cache.json"
            _expected = [str(t / "fc" / f"{subj}.mif")]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBASubject3b", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA Subject3b] Cache hit — skipping.")
                return (str(fba),)

            executor = get_executor("mrtrix")

            # Step 13: Warp FOD (no reorientation)
            print("[FBA Subject3b] Warping FOD to template space (no reorientation)")
            rc, _, stderr = executor.execute([
                "mrtransform", str(wmfod_norm),
                "-warp", str(warp_s2t),
                "-reorient_fod", "no",
                str(fod_not_reoriented),
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"mrtransform (FOD warp) failed: {stderr}")

            # Step 14: Segment fixels and estimate FD
            print("[FBA Subject3b] Segmenting fixels (FD)")
            if fixel_not_reoriented.exists():
                shutil.rmtree(fixel_not_reoriented)
            rc, _, stderr = executor.execute([
                "fod2fixel",
                "-mask", str(template_mask),
                str(fod_not_reoriented),
                str(fixel_not_reoriented),
                "-afd", "fd.mif",
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"fod2fixel (FD) failed: {stderr}")

            # Step 15: Reorient fixels
            print("[FBA Subject3b] Reorienting fixels")
            if fixel_reoriented.exists():
                shutil.rmtree(fixel_reoriented)
            rc, _, stderr = executor.execute([
                "fixelreorient",
                str(fixel_not_reoriented),
                str(warp_s2t),
                str(fixel_reoriented),
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"fixelreorient failed: {stderr}")

            # Step 16: Assign fixels to template (FD)
            print("[FBA Subject3b] Assigning fixels to template (FD)")
            rc, _, stderr = executor.execute([
                "fixelcorrespondence",
                str(fixel_reoriented / "fd.mif"),
                str(fixel_mask_dir),
                str(t / "fd"),
                f"{subj}.mif",
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"fixelcorrespondence (FD) failed: {stderr}")

            # Step 17: Compute fibre cross-section (FC)
            print("[FBA Subject3b] Computing fibre cross-section (FC)")
            rc, _, stderr = executor.execute([
                "warp2metric", str(warp_s2t),
                "-fc", str(fixel_mask_dir),
                str(t / "fc"),
                f"{subj}.mif",
                "-force",
            ])
            if rc != 0:
                raise RuntimeError(f"warp2metric (FC) failed: {stderr}")

            print(f"[FBA Subject3b] FD and FC written to {t}/fd/ and {t}/fc/")

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBASubject3b", _param_hash, _params, _expected)

            return (str(fba),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA Subject3b] {err}")
            import traceback
            print(traceback.format_exc())
            return (err,)
