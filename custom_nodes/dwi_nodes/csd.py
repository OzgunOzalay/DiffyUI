"""
CSD Node — Constrained Spherical Deconvolution (multi-shell multi-tissue).
Pipeline: dwi2response dhollander → dwi2fod msmt_csd → mtnormalise.
Requires multi-shell data (≥2 non-zero b-value shells).
"""

from pathlib import Path

from ._import_utils import BIDSHandler, get_executor, CacheManager


class CSDNode:
    """
    Multi-tissue CSD: estimate tissue response functions, compute FODs, normalise.
    Input DWI must have ≥2 non-zero b-shells (multi-shell acquisition).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "Pre-processed DWI NIfTI (after eddy/bias correction)",
                }),
                "bvec_file": ("STRING", {
                    "default": "",
                    "tooltip": "FSL-style bvec file",
                }),
                "bval_file": ("STRING", {
                    "default": "",
                    "tooltip": "FSL-style bval file",
                }),
                "mask_file": ("STRING", {
                    "default": "",
                    "tooltip": "Binary brain mask (NIfTI or MIF)",
                }),
            },
            "optional": {
                "lmax": ("STRING", {
                    "default": "",
                    "tooltip": (
                        "Maximum harmonic degree(s) for dwi2fod, e.g. '8,0,0'. "
                        "Leave blank for auto-selection."
                    ),
                }),
                "nthreads": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 32,
                    "tooltip": "Number of threads (0 = use 10)",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("wm_fod", "gm_fod", "csf_fod", "wm_response", "gm_response", "csf_response")
    FUNCTION = "run_csd"
    CATEGORY = "DWI/Preprocessing"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Multi-tissue CSD: response estimation (dhollander), FOD computation (msmt_csd), "
        "and multi-tissue normalisation. Feeds into DWI Tractography."
    )

    @classmethod
    def IS_CHANGED(cls, dwi_file, bvec_file, bval_file, mask_file, lmax="", nthreads=10):
        try:
            params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "bvec_file": bvec_file, "bval_file": bval_file,
                        "mask_file": mask_file, "lmax": lmax},
                file_keys=["dwi_file", "bvec_file", "bval_file", "mask_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def run_csd(self, dwi_file: str, bvec_file: str, bval_file: str, mask_file: str,
                lmax: str = "", nthreads: int = 10) -> tuple:
        """
        Run multi-tissue CSD pipeline.

        Args:
            dwi_file: Pre-processed DWI NIfTI path
            bvec_file: FSL bvec file path
            bval_file: FSL bval file path
            mask_file: Brain mask path (NIfTI or MIF)
            lmax: Max harmonic degree string for dwi2fod (e.g. '8,0,0'), or empty for auto
            nthreads: Number of threads

        Returns:
            Tuple of (wm_fod, gm_fod, csf_fod, wm_response, gm_response, csf_response)
        """
        _err = ("", "", "", "", "", "")
        print("[CSD] ===== FUNCTION CALLED =====")
        try:
            for label, val in [("dwi_file", dwi_file), ("bvec_file", bvec_file),
                                ("bval_file", bval_file), ("mask_file", mask_file)]:
                if not val or not val.strip():
                    return (f"Error: {label} is required",) + ("",) * 5
            input_dwi = Path(dwi_file.strip())
            bvec_path = Path(bvec_file.strip())
            bval_path = Path(bval_file.strip())
            mask_path = Path(mask_file.strip())
            for p in (input_dwi, bvec_path, bval_path, mask_path):
                if not p.exists():
                    return (f"Error: file not found: {p}",) + ("",) * 5

            # Guard: require multi-shell data
            bvals = [float(v) for v in bval_path.read_text().split()]
            shells = set(round(b / 100) * 100 for b in bvals if b > 100)
            if len(shells) < 2:
                msg = (f"Error: msmt_csd requires ≥2 non-zero b-shells; "
                       f"found {len(shells)} ({sorted(shells)})")
                print(f"[CSD] {msg}")
                return (msg,) + ("",) * 5

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "bvec_file": bvec_file, "bval_file": bval_file,
                        "mask_file": mask_file, "lmax": lmax},
                file_keys=["dwi_file", "bvec_file", "bval_file", "mask_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            # BIDS output routing
            bids_root, subject_id = BIDSHandler.infer_bids_paths(input_dwi)
            if subject_id and bids_root:
                bids = BIDSHandler(str(bids_root))
                output_dir = bids.get_derivatives_path(subject_id, "diffyui") / "dwi" / "CSD"
            else:
                output_dir = input_dwi.parent / "CSD"
            output_dir.mkdir(parents=True, exist_ok=True)

            wm_resp  = output_dir / "wm_response.txt"
            gm_resp  = output_dir / "gm_response.txt"
            csf_resp = output_dir / "csf_response.txt"
            wm_fod   = output_dir / "wm_fod.mif"
            gm_fod   = output_dir / "gm_fod.mif"
            csf_fod  = output_dir / "csf_fod.mif"
            wm_fod_norm  = output_dir / "wm_fod_norm.mif"
            gm_fod_norm  = output_dir / "gm_fod_norm.mif"
            csf_fod_norm = output_dir / "csf_fod_norm.mif"

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(wm_fod_norm), str(gm_fod_norm), str(csf_fod_norm),
                         str(wm_resp), str(gm_resp), str(csf_resp)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "CSD", _param_hash, _expected
            )
            if _is_hit:
                print("[CSD] Cache hit — skipping.")
                return tuple(_cached)

            if nthreads <= 0:
                nthreads = 10
            executor = get_executor("mrtrix")
            grad_flag = ["-fslgrad", str(bvec_path), str(bval_path)]

            # Step 1: estimate response functions
            resp_cmd = [
                "dwi2response", "dhollander",
                str(input_dwi), str(wm_resp), str(gm_resp), str(csf_resp),
                *grad_flag,
                "-mask", str(mask_path),
                "-nthreads", str(nthreads),
                "-force",
            ]
            print(f"[CSD] Step 1 – dwi2response: {' '.join(resp_cmd)}")
            rc, _out, err = executor.execute(resp_cmd)
            if rc != 0:
                raise RuntimeError(f"dwi2response failed: {err}")

            # Step 2: compute multi-tissue FODs
            fod_cmd = [
                "dwi2fod", "msmt_csd",
                str(input_dwi),
                str(wm_resp),  str(wm_fod),
                str(gm_resp),  str(gm_fod),
                str(csf_resp), str(csf_fod),
                *grad_flag,
                "-mask", str(mask_path),
                "-nthreads", str(nthreads),
                "-force",
            ]
            if lmax and lmax.strip():
                fod_cmd += ["-lmax", lmax.strip()]
            print(f"[CSD] Step 2 – dwi2fod: {' '.join(fod_cmd)}")
            rc, _out, err = executor.execute(fod_cmd)
            if rc != 0:
                raise RuntimeError(f"dwi2fod failed: {err}")

            # Step 3: multi-tissue normalisation
            try:
                norm_cmd = [
                    "mtnormalise",
                    str(wm_fod),  str(wm_fod_norm),
                    str(gm_fod),  str(gm_fod_norm),
                    str(csf_fod), str(csf_fod_norm),
                    "-mask", str(mask_path),
                    "-nthreads", str(nthreads),
                    "-force",
                ]
                print(f"[CSD] Step 3 – mtnormalise: {' '.join(norm_cmd)}")
                rc, _out, err = executor.execute(norm_cmd)
                if rc != 0:
                    raise RuntimeError(f"mtnormalise failed: {err}")
            finally:
                # Remove unnormalised FOD intermediates
                for tmp in (wm_fod, gm_fod, csf_fod):
                    try:
                        if tmp.exists():
                            tmp.unlink()
                    except Exception:
                        pass

            for p in (wm_fod_norm, gm_fod_norm, csf_fod_norm, wm_resp, gm_resp, csf_resp):
                if not p.exists():
                    raise RuntimeError(f"Expected output not found: {p}")

            print(f"[CSD] WM FOD  : {wm_fod_norm}")
            print(f"[CSD] GM FOD  : {gm_fod_norm}")
            print(f"[CSD] CSF FOD : {csf_fod_norm}")

            result = [str(wm_fod_norm), str(gm_fod_norm), str(csf_fod_norm),
                      str(wm_resp), str(gm_resp), str(csf_resp)]

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "CSD", _param_hash, _params, result)

            return tuple(result)

        except Exception as e:
            import traceback
            print(f"[CSD] ERROR: {e}")
            print(traceback.format_exc())
            return (f"Error: {e}",) + ("",) * 5
