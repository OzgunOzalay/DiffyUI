"""
Gibbs Unringing Node — MRtrix3 mrdegibbs.
Must run after denoising and before any interpolation.
"""

from pathlib import Path

from ._import_utils import BIDSHandler, get_executor, CacheManager


class GibbsUnringingNode:
    """Remove Gibbs ringing artefacts using MRtrix3 mrdegibbs."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "Denoised DWI NIfTI file path (output of DWI Denoise)",
                }),
            },
            "optional": {
                "axes": ("STRING", {
                    "default": "0,1",
                    "tooltip": "Comma-separated slice axes for Gibbs removal (default: 0,1)",
                }),
                "maxlength": ("INT", {
                    "default": 128,
                    "min": 1,
                    "max": 512,
                    "tooltip": "Maximum length of partial Fourier shift (default 128)",
                }),
                "minlength": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 512,
                    "tooltip": "Minimum length of partial Fourier shift (default 1)",
                }),
                "nshifts": ("INT", {
                    "default": 20,
                    "min": 1,
                    "max": 100,
                    "tooltip": "Number of shifts used to sample Gibbs artefacts (default 20)",
                }),
                "nthreads": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 32,
                    "tooltip": "Number of threads (0 = use 10)",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("degibbs_dwi",)
    FUNCTION = "degibbs"
    CATEGORY = "DWI/Preprocessing"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Remove Gibbs ringing artefacts using MRtrix3 mrdegibbs. "
        "Run after denoising, before any interpolation or eddy correction."
    )

    @classmethod
    def IS_CHANGED(cls, dwi_file, axes="0,1", maxlength=128, minlength=1, nshifts=20, nthreads=10):
        try:
            params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "axes": axes, "maxlength": maxlength,
                        "minlength": minlength, "nshifts": nshifts},
                file_keys=["dwi_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def degibbs(self, dwi_file: str, axes: str = "0,1", maxlength: int = 128,
                minlength: int = 1, nshifts: int = 20, nthreads: int = 10) -> tuple:
        """
        Remove Gibbs ringing artefacts from DWI data.

        Args:
            dwi_file: Full path to denoised DWI NIfTI file
            axes: Comma-separated slice axes for Gibbs removal
            maxlength: Maximum length of partial Fourier shift
            minlength: Minimum length of partial Fourier shift
            nshifts: Number of shifts to sample Gibbs artefacts
            nthreads: Number of threads

        Returns:
            Tuple of (degibbs_dwi_path,)
        """
        print("[Gibbs Unringing] ===== FUNCTION CALLED =====")
        try:
            if not dwi_file or not dwi_file.strip():
                return ("Error: DWI file path is required",)

            input_dwi = Path(dwi_file.strip())
            if not input_dwi.exists():
                return (f"Error: DWI file not found: {dwi_file}",)

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={"dwi_file": dwi_file, "axes": axes, "maxlength": maxlength,
                        "minlength": minlength, "nshifts": nshifts},
                file_keys=["dwi_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            # BIDS output routing
            bids_root, subject_id = BIDSHandler.infer_bids_paths(input_dwi)
            if subject_id and bids_root:
                bids = BIDSHandler(str(bids_root))
                output_dir = bids.get_derivatives_path(subject_id, "diffyui") / "dwi"
            else:
                output_dir = input_dwi.parent / "Degibbs"
            output_dir.mkdir(parents=True, exist_ok=True)

            input_stem = input_dwi.name.replace(".nii.gz", "").replace(".nii", "")
            degibbs_output = output_dir / f"{input_stem}_degibbs.nii.gz"

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(degibbs_output)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "GibbsUnringing", _param_hash, _expected
            )
            if _is_hit:
                print("[Gibbs Unringing] Cache hit — skipping.")
                return tuple(_cached)

            print(f"[Gibbs Unringing] Input DWI : {input_dwi}")
            print(f"[Gibbs Unringing] Output dir: {output_dir}")
            executor = get_executor("mrtrix")

            if nthreads <= 0:
                nthreads = 10

            cmd = [
                "mrdegibbs",
                str(input_dwi),
                str(degibbs_output),
                "-axes", axes,
                "-maxlength", str(maxlength),
                "-minlength", str(minlength),
                "-nshifts", str(nshifts),
                "-nthreads", str(nthreads),
                "-force",
            ]
            print(f"[Gibbs Unringing] Command: {' '.join(cmd)}")

            return_code, stdout, stderr = executor.execute(cmd)
            if return_code != 0:
                raise RuntimeError(f"mrdegibbs failed: {stderr}")

            if not degibbs_output.exists():
                raise RuntimeError(f"Output not found: {degibbs_output}")

            print(f"[Gibbs Unringing] Saved to: {degibbs_output}")

            # Write BIDS metadata sidecar
            if subject_id and bids_root:
                try:
                    BIDSHandler(str(bids_root)).write_derivative_file(
                        degibbs_output, input_dwi,
                        {"ProcessingStep": "GibbsUnringing", "Tool": "MRtrix3 mrdegibbs",
                         "Axes": axes, "MaxLength": maxlength, "MinLength": minlength,
                         "NShifts": nshifts},
                    )
                except Exception as e:
                    print(f"[Gibbs Unringing] Warning: could not write BIDS sidecar: {e}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(
                _cache_path, "GibbsUnringing", _param_hash, _params, [str(degibbs_output)]
            )

            return (str(degibbs_output),)

        except Exception as e:
            import traceback
            print(f"[Gibbs Unringing] ERROR: {e}")
            print(traceback.format_exc())
            return (f"Error: {e}",)
