"""
DWI Tractography Node — MRtrix3 tckgen + optional tcksift2.
Takes WM FOD from the CSD node; does NOT run CSD internally.
"""

from pathlib import Path

from ._import_utils import BIDSHandler, get_executor, CacheManager


class DWITractographyNode:
    """
    Whole-brain tractography via MRtrix3 tckgen (iFOD2 / SD_STREAM / Tensor modes).
    Input is a WM FOD image (output of CSD node). Optional SIFT2 weight estimation.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fod_file": ("STRING", {
                    "default": "",
                    "tooltip": "WM FOD image from CSD node (.mif)",
                }),
                "mask_file": ("STRING", {
                    "default": "",
                    "tooltip": "Brain mask (seed image and tract mask)",
                }),
            },
            "optional": {
                "algorithm": (["iFOD2", "SD_STREAM", "Tensor_Det", "Tensor_Prob"], {
                    "default": "iFOD2",
                    "tooltip": "Tractography algorithm",
                }),
                "num_streamlines": ("INT", {
                    "default": 10000000,
                    "min": 1000,
                    "max": 100000000,
                    "tooltip": "Number of streamlines to generate",
                }),
                "step_size": ("FLOAT", {
                    "default": 0.625,
                    "min": 0.1,
                    "max": 2.0,
                    "tooltip": "Step size in mm (default 0.625)",
                }),
                "max_length": ("FLOAT", {
                    "default": 200.0,
                    "min": 10.0,
                    "max": 500.0,
                    "tooltip": "Maximum streamline length in mm",
                }),
                "min_length": ("FLOAT", {
                    "default": 10.0,
                    "min": 0.0,
                    "max": 100.0,
                    "tooltip": "Minimum streamline length in mm",
                }),
                "angle": ("FLOAT", {
                    "default": 45.0,
                    "min": 1.0,
                    "max": 90.0,
                    "tooltip": "Maximum curvature angle (degrees) between steps",
                }),
                "run_sift2": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Run tcksift2 to compute per-streamline weights",
                }),
                "nthreads": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 32,
                    "tooltip": "Number of threads (0 = use 10)",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tractogram_file", "sift2_weights")
    FUNCTION = "track"
    CATEGORY = "DWI"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Whole-brain tractography with MRtrix3 tckgen. "
        "Connect WM FOD from CSD node. Optional SIFT2 streamline-weight estimation."
    )

    @classmethod
    def IS_CHANGED(cls, fod_file, mask_file, algorithm="iFOD2", num_streamlines=10000000,
                   step_size=0.625, max_length=200.0, min_length=10.0, angle=45.0,
                   run_sift2=True, nthreads=10):
        try:
            params = CacheManager.build_params_for_hash(
                kwargs={"fod_file": fod_file, "mask_file": mask_file, "algorithm": algorithm,
                        "num_streamlines": num_streamlines, "step_size": step_size,
                        "max_length": max_length, "min_length": min_length,
                        "angle": angle, "run_sift2": run_sift2},
                file_keys=["fod_file", "mask_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def track(self, fod_file: str, mask_file: str, algorithm: str = "iFOD2",
              num_streamlines: int = 10000000, step_size: float = 0.625,
              max_length: float = 200.0, min_length: float = 10.0, angle: float = 45.0,
              run_sift2: bool = True, nthreads: int = 10) -> tuple:
        """
        Run whole-brain tractography on a WM FOD image.

        Args:
            fod_file: Path to WM FOD (.mif) from CSD node
            mask_file: Brain mask used as seed and include mask
            algorithm: tckgen algorithm (iFOD2 / SD_STREAM / Tensor_Det / Tensor_Prob)
            num_streamlines: Number of streamlines to select
            step_size: Step size in mm
            max_length: Maximum streamline length in mm
            min_length: Minimum streamline length in mm
            angle: Maximum curvature angle between steps (degrees)
            run_sift2: Whether to run tcksift2 for streamline weight estimation
            nthreads: Number of threads

        Returns:
            Tuple of (tractogram_tck_path, sift2_weights_path_or_empty)
        """
        print("[DWI Tractography] ===== FUNCTION CALLED =====")
        try:
            for label, val in [("fod_file", fod_file), ("mask_file", mask_file)]:
                if not val or not val.strip():
                    return (f"Error: {label} is required", "")
            fod_path = Path(fod_file.strip())
            mask_path = Path(mask_file.strip())
            if not fod_path.exists():
                return (f"Error: FOD file not found: {fod_path}", "")
            if not mask_path.exists():
                return (f"Error: mask file not found: {mask_path}", "")

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={"fod_file": fod_file, "mask_file": mask_file, "algorithm": algorithm,
                        "num_streamlines": num_streamlines, "step_size": step_size,
                        "max_length": max_length, "min_length": min_length,
                        "angle": angle, "run_sift2": run_sift2},
                file_keys=["fod_file", "mask_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            # BIDS output routing (infer from FOD path)
            bids_root, subject_id = BIDSHandler.infer_bids_paths(fod_path)
            if subject_id and bids_root:
                bids = BIDSHandler(str(bids_root))
                output_dir = bids.get_derivatives_path(subject_id, "diffyui") / "dwi" / "Tractography"
            else:
                output_dir = fod_path.parent / "Tractography"
            output_dir.mkdir(parents=True, exist_ok=True)

            tractogram = output_dir / "whole_brain.tck"
            sift2_weights = output_dir / "sift2_weights.txt"

            # ── Block 2: check cache ──
            _cache_path = output_dir / ".diffyui_cache.json"
            _expected = [str(tractogram), str(sift2_weights) if run_sift2 else ""]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "DWITractography", _param_hash, _expected
            )
            if _is_hit:
                print("[DWI Tractography] Cache hit — skipping.")
                return tuple(_cached)

            if nthreads <= 0:
                nthreads = 10
            executor = get_executor("mrtrix")

            # tckgen
            tckgen_cmd = [
                "tckgen",
                str(fod_path),
                str(tractogram),
                "-algorithm", algorithm,
                "-select", str(num_streamlines),
                "-step", str(step_size),
                "-maxlength", str(max_length),
                "-minlength", str(min_length),
                "-angle", str(angle),
                "-seed_image", str(mask_path),
                "-mask", str(mask_path),
                "-nthreads", str(nthreads),
                "-force",
            ]
            print(f"[DWI Tractography] tckgen: {' '.join(tckgen_cmd)}")
            rc, _out, err = executor.execute(tckgen_cmd)
            if rc != 0:
                raise RuntimeError(f"tckgen failed: {err}")
            if not tractogram.exists():
                raise RuntimeError(f"Tractogram not found: {tractogram}")
            print(f"[DWI Tractography] Tractogram: {tractogram}")

            # tcksift2 (optional)
            weights_path = ""
            if run_sift2:
                sift2_cmd = [
                    "tcksift2",
                    str(tractogram),
                    str(fod_path),
                    str(sift2_weights),
                    "-nthreads", str(nthreads),
                    "-force",
                ]
                print(f"[DWI Tractography] tcksift2: {' '.join(sift2_cmd)}")
                rc, _out, err = executor.execute(sift2_cmd)
                if rc != 0:
                    print(f"[DWI Tractography] Warning: tcksift2 failed: {err}")
                elif sift2_weights.exists():
                    weights_path = str(sift2_weights)
                    print(f"[DWI Tractography] SIFT2 weights: {sift2_weights}")

            result = [str(tractogram), weights_path]

            # ── Block 3: update cache ──
            CacheManager.update_cache(
                _cache_path, "DWITractography", _param_hash, _params, result
            )

            return tuple(result)

        except Exception as e:
            import traceback
            print(f"[DWI Tractography] ERROR: {e}")
            print(traceback.format_exc())
            return (f"Error: {e}", "")
