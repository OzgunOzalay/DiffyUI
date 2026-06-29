"""
DKI Fit Node — Diffusion Kurtosis Imaging via DIPY (pure Python, no subprocess).
Requires multi-shell data (≥2 non-zero b-value shells).
Outputs: MK, AK, RK, KFA, FA, MD, AD, RD maps.
"""

from pathlib import Path

from ._import_utils import BIDSHandler, CacheManager


class DKIFitNode:
    """
    Fit Diffusion Kurtosis Imaging (DKI) model using DIPY.
    Requires multi-shell DWI data. Outputs eight parametric maps.
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
                    "tooltip": "Binary brain mask NIfTI",
                }),
            },
            "optional": {
                "min_kurtosis": ("FLOAT", {
                    "default": -0.42,
                    "min": -2.0,
                    "max": 0.0,
                    "tooltip": "Minimum physically plausible kurtosis (default -0.42)",
                }),
                "max_kurtosis": ("FLOAT", {
                    "default": 10.0,
                    "min": 0.0,
                    "max": 20.0,
                    "tooltip": "Maximum physically plausible kurtosis (default 10.0)",
                }),
            },
        }

    RETURN_TYPES = ("STRING",) * 8
    RETURN_NAMES = ("mk_map", "ak_map", "rk_map", "kfa_map", "fa_map", "md_map", "ad_map", "rd_map")
    FUNCTION = "run_dki"
    CATEGORY = "DWI/Preprocessing"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Diffusion Kurtosis Imaging via DIPY. "
        "Requires ≥2 non-zero b-shells. Outputs MK, AK, RK, KFA, FA, MD, AD, RD."
    )

    @classmethod
    def IS_CHANGED(cls, dwi_file, bvec_file, bval_file, mask_file,
                   min_kurtosis=-0.42, max_kurtosis=10.0):
        try:
            params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "bvec_file": bvec_file,
                        "bval_file": bval_file, "mask_file": mask_file,
                        "min_kurtosis": min_kurtosis, "max_kurtosis": max_kurtosis},
                file_keys=["dwi_file", "bvec_file", "bval_file", "mask_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def run_dki(self, dwi_file: str, bvec_file: str, bval_file: str, mask_file: str,
                min_kurtosis: float = -0.42, max_kurtosis: float = 10.0) -> tuple:
        """
        Fit DKI model and save parametric maps.

        Args:
            dwi_file: Pre-processed DWI NIfTI path
            bvec_file: FSL bvec file path
            bval_file: FSL bval file path
            mask_file: Binary brain mask path
            min_kurtosis: Minimum kurtosis clamp value
            max_kurtosis: Maximum kurtosis clamp value

        Returns:
            Tuple of 8 paths: (mk, ak, rk, kfa, fa, md, ad, rd)
        """
        _err8 = ("",) * 8
        print("[DKI Fit] ===== FUNCTION CALLED =====")
        try:
            # Lazy import — dipy is heavy and may not be installed
            try:
                from dipy.io.image import load_nifti, save_nifti
                from dipy.io.gradients import read_bvals_bvecs
                from dipy.core.gradients import gradient_table
                from dipy.reconst.dki import DiffusionKurtosisModel
            except ImportError:
                msg = "Error: dipy is not installed. Run: pip install 'dipy>=1.7.0'"
                print(f"[DKI Fit] {msg}")
                return (msg,) + ("",) * 7

            for label, val in [("dwi_file", dwi_file), ("bvec_file", bvec_file),
                                ("bval_file", bval_file), ("mask_file", mask_file)]:
                if not val or not val.strip():
                    return (f"Error: {label} is required",) + ("",) * 7

            input_dwi = Path(dwi_file.strip())
            bvec_path  = Path(bvec_file.strip())
            bval_path  = Path(bval_file.strip())
            mask_path  = Path(mask_file.strip())
            for p in (input_dwi, bvec_path, bval_path, mask_path):
                if not p.exists():
                    return (f"Error: file not found: {p}",) + ("",) * 7

            # Guard: require multi-shell
            bvals_raw = [float(v) for v in bval_path.read_text().split()]
            shells = set(round(b / 100) * 100 for b in bvals_raw if b > 100)
            if len(shells) < 2:
                msg = (f"Error: DKI requires ≥2 non-zero b-shells; "
                       f"found {len(shells)} ({sorted(shells)})")
                print(f"[DKI Fit] {msg}")
                return (msg,) + ("",) * 7

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "bvec_file": bvec_file,
                        "bval_file": bval_file, "mask_file": mask_file,
                        "min_kurtosis": min_kurtosis, "max_kurtosis": max_kurtosis},
                file_keys=["dwi_file", "bvec_file", "bval_file", "mask_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            # BIDS output routing
            bids_root, subject_id = BIDSHandler.infer_bids_paths(input_dwi)
            if subject_id and bids_root:
                bids = BIDSHandler(str(bids_root))
                output_dir = bids.get_derivatives_path(subject_id, "diffyui") / "dwi" / "DKI"
            else:
                output_dir = input_dwi.parent / "DKI"
            output_dir.mkdir(parents=True, exist_ok=True)

            stem = input_dwi.name.replace(".nii.gz", "").replace(".nii", "")
            mk_out  = output_dir / f"{stem}_MK.nii.gz"
            ak_out  = output_dir / f"{stem}_AK.nii.gz"
            rk_out  = output_dir / f"{stem}_RK.nii.gz"
            kfa_out = output_dir / f"{stem}_KFA.nii.gz"
            fa_out  = output_dir / f"{stem}_FA.nii.gz"
            md_out  = output_dir / f"{stem}_MD.nii.gz"
            ad_out  = output_dir / f"{stem}_AD.nii.gz"
            rd_out  = output_dir / f"{stem}_RD.nii.gz"

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(p) for p in (mk_out, ak_out, rk_out, kfa_out,
                                           fa_out, md_out, ad_out, rd_out)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "DKIFit", _param_hash, _expected
            )
            if _is_hit:
                print("[DKI Fit] Cache hit — skipping.")
                return tuple(_cached)

            print(f"[DKI Fit] Loading DWI: {input_dwi}")
            data, affine = load_nifti(str(input_dwi))
            bvals, bvecs = read_bvals_bvecs(str(bval_path), str(bvec_path))
            gtab = gradient_table(bvals, bvecs)
            mask_data, _ = load_nifti(str(mask_path))

            print("[DKI Fit] Fitting DKI model…")
            dkimodel = DiffusionKurtosisModel(gtab)
            dkifit = dkimodel.fit(data, mask=mask_data.astype(bool))

            print("[DKI Fit] Saving parametric maps…")
            save_nifti(str(mk_out),  dkifit.mk(min_kurtosis, max_kurtosis), affine)
            save_nifti(str(ak_out),  dkifit.ak(min_kurtosis, max_kurtosis), affine)
            save_nifti(str(rk_out),  dkifit.rk(min_kurtosis, max_kurtosis), affine)
            save_nifti(str(kfa_out), dkifit.kfa,                             affine)
            save_nifti(str(fa_out),  dkifit.fa,                              affine)
            save_nifti(str(md_out),  dkifit.md,                              affine)
            save_nifti(str(ad_out),  dkifit.ad,                              affine)
            save_nifti(str(rd_out),  dkifit.rd,                              affine)

            for p in (mk_out, ak_out, rk_out, kfa_out, fa_out, md_out, ad_out, rd_out):
                if not p.exists():
                    raise RuntimeError(f"Expected output missing: {p}")
                print(f"[DKI Fit] {p.name}: {p}")

            result = [str(p) for p in (mk_out, ak_out, rk_out, kfa_out,
                                        fa_out, md_out, ad_out, rd_out)]

            # ── Block 3: update cache ──
            CacheManager.update_cache(_cache_path, "DKIFit", _param_hash, _params, result)

            return tuple(result)

        except Exception as e:
            import traceback
            print(f"[DKI Fit] ERROR: {e}")
            print(traceback.format_exc())
            return (f"Error: {e}",) + ("",) * 7
