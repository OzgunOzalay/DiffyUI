"""
FBA Group Node — Stage: group
Whole-brain tractography on the FOD template, SIFT, fixel-fixel connectivity matrix,
and fixel data smoothing (FD, log_FC, FDC).
"""

import shutil
from pathlib import Path

from ._import_utils import get_executor, CacheManager, _is_upstream_error


class FBAGroupNode:
    """
    FBA Group: whole-brain tractography (tckgen) on the FOD template, SIFT to reduce
    streamline count (tcksift), generate fixel-fixel connectivity matrix (fixelconnectivity),
    and smooth FD, log_FC, and FDC fixel data (fixelfilter smooth).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Template directory with wmfod_template.mif, fixel_mask/, fd/, log_fc/, fdc/ (from FBA Log FC + FDC)."
                }),
            },
            "optional": {
                "num_tracks": ("INT", {
                    "default": 2000000,
                    "min": 100000,
                    "tooltip": "Number of streamlines to generate with tckgen (default 2M)."
                }),
                "sift_tracks": ("INT", {
                    "default": 1000000,
                    "min": 100000,
                    "tooltip": "Target number of streamlines after SIFT (default 1M)."
                }),
                "fmls_peak_value": ("FLOAT", {
                    "default": 0.06,
                    "min": 0.01,
                    "max": 0.5,
                    "step": 0.01,
                    "tooltip": "FOD amplitude cutoff for tckgen (default 0.06)."
                }),
                "angle": ("FLOAT", {
                    "default": 22.5,
                    "min": 1.0,
                    "max": 90.0,
                    "step": 0.5,
                    "tooltip": "Maximum angle between successive steps (degrees, default 22.5)."
                }),
                "maxlen": ("INT", {
                    "default": 250,
                    "min": 10,
                    "max": 1000,
                    "tooltip": "Maximum streamline length in mm (default 250)."
                }),
                "minlen": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 100,
                    "tooltip": "Minimum streamline length in mm (default 10)."
                }),
                "power": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.1,
                    "max": 4.0,
                    "step": 0.1,
                    "tooltip": "Exponent for FOD-based streamline seeding density (default 1.0)."
                }),
                "nthreads": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 64,
                    "tooltip": "Number of threads for MRtrix3 commands."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("fd_smooth_dir", "log_fc_smooth_dir", "fdc_smooth_dir", "template_dir")
    FUNCTION = "group"
    CATEGORY = "DWI/FBA"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "FBA stage 11 (group): whole-brain tractography (tckgen), SIFT (tcksift), "
        "fixel-fixel connectivity matrix (fixelconnectivity), and smooth FD/log_FC/FDC "
        "(fixelfilter smooth). Outputs smoothed fixel directories ready for group statistics."
    )

    @classmethod
    def IS_CHANGED(cls, template_dir, num_tracks=2000000, sift_tracks=1000000,
                   fmls_peak_value=0.06, angle=22.5, maxlen=250, minlen=10,
                   power=1.0, nthreads=10):
        try:
            t = Path(template_dir)
            tmpl = t / "wmfod_template.mif"
            mtime = tmpl.stat().st_mtime if tmpl.exists() else 0.0
            params = {
                "tmpl_mtime": mtime, "num_tracks": num_tracks,
                "sift_tracks": sift_tracks, "fmls_peak_value": fmls_peak_value,
            }
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def group(self, template_dir, num_tracks=2000000, sift_tracks=1000000,
              fmls_peak_value=0.06, angle=22.5, maxlen=250, minlen=10,
              power=1.0, nthreads=10):
        print("[FBA Group] ===== FUNCTION CALLED =====")
        try:
            if _is_upstream_error(template_dir):
                print(f"[FBA Group] Upstream error: {template_dir}")
                return (template_dir, template_dir, template_dir, template_dir)

            t = Path(template_dir.strip())
            wmfod_template = t / "wmfod_template.mif"
            template_mask = t / "template_mask.mif"
            fixel_mask_dir = t / "fixel_mask"

            for p in [wmfod_template, template_mask, fixel_mask_dir]:
                if not p.exists():
                    err = f"Required path missing: {p}. Complete earlier FBA stages first."
                    print(f"[FBA Group] ERROR: {err}")
                    return (f"Error: {err}", "", "", "")

            millions_all = num_tracks // 1000000
            millions_sift = sift_tracks // 1000000
            tck_all = t / f"tracks_{millions_all}_million.tck"
            tck_sift = t / f"tracks_{millions_sift}_million_sift.tck"
            matrix_dir = t / "matrix"

            fd_smooth = t / "fd_smooth"
            log_fc_smooth = t / "log_fc_smooth"
            fdc_smooth = t / "fdc_smooth"

            # ── Block 1: build param hash ──
            _params = {
                "tmpl_mtime": wmfod_template.stat().st_mtime,
                "num_tracks": num_tracks,
                "sift_tracks": sift_tracks,
                "fmls_peak_value": fmls_peak_value,
                "angle": angle,
                "maxlen": maxlen,
                "minlen": minlen,
                "power": power,
            }
            _param_hash = CacheManager.compute_param_hash(_params)

            # ── Block 2: check cache ──
            _cache_path = t / ".diffyui_fba_cache.json"
            _expected = [str(fd_smooth), str(log_fc_smooth), str(fdc_smooth), str(t)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "FBAGroup", _param_hash, _expected
            )
            if _is_hit:
                print("[FBA Group] Cache hit — skipping.")
                return tuple(_cached)

            executor = get_executor("mrtrix")

            # Step 20: Whole-brain tractography
            if not tck_all.exists():
                print(f"[FBA Group] Tractography ({millions_all}M streamlines, cutoff={fmls_peak_value})")
                rc, _, stderr = executor.execute([
                    "tckgen",
                    "-angle", str(angle),
                    "-maxlen", str(maxlen),
                    "-minlen", str(minlen),
                    "-power", str(power),
                    str(wmfod_template),
                    "-seed_image", str(template_mask),
                    "-mask", str(template_mask),
                    "-select", str(num_tracks),
                    "-cutoff", str(fmls_peak_value),
                    str(tck_all),
                    "-nthreads", str(nthreads),
                    "-force",
                ])
                if rc != 0:
                    raise RuntimeError(f"tckgen failed: {stderr}")
                print(f"[FBA Group] Tractogram written to {tck_all}")
            else:
                print(f"[FBA Group] Skipping tckgen — {tck_all} exists")

            # Step 21: SIFT
            if not tck_sift.exists():
                print(f"[FBA Group] SIFT (reducing to {millions_sift}M streamlines)")
                rc, _, stderr = executor.execute([
                    "tcksift",
                    str(tck_all),
                    str(wmfod_template),
                    str(tck_sift),
                    "-term_number", str(sift_tracks),
                    "-nthreads", str(nthreads),
                    "-force",
                ])
                if rc != 0:
                    raise RuntimeError(f"tcksift failed: {stderr}")
                print(f"[FBA Group] SIFTed tractogram written to {tck_sift}")
            else:
                print(f"[FBA Group] Skipping tcksift — {tck_sift} exists")

            # Step 22: Fixel-fixel connectivity matrix
            if not (matrix_dir / "index.mif").exists():
                print("[FBA Group] Generating fixel-fixel connectivity matrix")
                if matrix_dir.exists():
                    shutil.rmtree(matrix_dir)
                matrix_dir.mkdir(parents=True, exist_ok=True)
                rc, _, stderr = executor.execute([
                    "fixelconnectivity",
                    str(fixel_mask_dir),
                    str(tck_sift),
                    str(matrix_dir) + "/",
                    "-force",
                ])
                if rc != 0:
                    raise RuntimeError(f"fixelconnectivity failed: {stderr}")
                print(f"[FBA Group] Connectivity matrix written to {matrix_dir}")
            else:
                print(f"[FBA Group] Skipping fixelconnectivity — matrix exists")

            # Step 23: Smooth fixel data
            smooth_targets = [
                (t / "fd", fd_smooth),
                (t / "log_fc", log_fc_smooth),
                (t / "fdc", fdc_smooth),
            ]
            for src_dir, dst_dir in smooth_targets:
                metric_name = src_dir.name
                if not src_dir.is_dir():
                    print(f"[FBA Group] WARN: {src_dir} not found, skipping smoothing")
                    continue
                if not (dst_dir / "index.mif").exists():
                    print(f"[FBA Group] Smoothing: {metric_name}")
                    if dst_dir.exists():
                        shutil.rmtree(dst_dir)
                    rc, _, stderr = executor.execute([
                        "fixelfilter",
                        str(src_dir),
                        "smooth",
                        str(dst_dir),
                        "-matrix", str(matrix_dir) + "/",
                        "-force",
                    ])
                    if rc != 0:
                        raise RuntimeError(f"fixelfilter smooth ({metric_name}) failed: {stderr}")
                    print(f"[FBA Group] Smoothed {metric_name} → {dst_dir}")
                else:
                    print(f"[FBA Group] Skipping smoothing — {dst_dir} exists")

            print(f"[FBA Group] Group-level processing complete.")
            result = (str(fd_smooth), str(log_fc_smooth), str(fdc_smooth), str(t))

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "FBAGroup", _param_hash, _params, list(result))

            return result

        except Exception as e:
            err = f"Error: {e}"
            print(f"[FBA Group] {err}")
            import traceback
            print(traceback.format_exc())
            return (err, "", "", "")
