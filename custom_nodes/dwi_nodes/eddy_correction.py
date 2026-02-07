"""
DWI Eddy Correction Node - Eddy current and motion correction.
Uses FSL eddy (or eddy_cuda10.2) with topup field for distortion correction.
"""

import os
import shutil
import multiprocessing
from pathlib import Path

from ._import_utils import BIDSHandler, get_executor

print("[DWI Eddy] ===== MODULE LOADING =====")


class DWIEddyCorrectionNode:
    """
    DWI Eddy Correction Node using FSL eddy.
    Expects topup field from DWI Topup Correction and acqp from same node.
    """

    def __init__(self):
        print("[DWI Eddy] Node instance created!")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dwi_file": ("STRING", {
                    "default": "",
                    "tooltip": "Input DWI file (e.g. topup-corrected)"
                }),
                "mask_file": ("STRING", {
                    "default": "",
                    "tooltip": "Brain mask file (e.g. from DWI Brain Mask)"
                }),
                "acqp_file": ("STRING", {
                    "default": "",
                    "tooltip": "Acquisition parameters file (wire from Topup acqp_file output)"
                }),
                "bvec_file": ("STRING", {
                    "default": "",
                    "tooltip": "B-vectors file (e.g. from Subject Bucket ap_phase_bvec)"
                }),
                "bval_file": ("STRING", {
                    "default": "",
                    "tooltip": "B-values file (e.g. from Subject Bucket ap_phase_bval)"
                }),
                "topup_field": ("STRING", {
                    "default": "",
                    "tooltip": "Topup field from DWI Topup Correction (topup_field output)"
                }),
            },
            "optional": {
                "flm": (["linear", "quadratic", "cubic"], {
                    "default": 1,
                    "tooltip": "First-level model for movement (quadratic = default)"
                }),
                "data_is_shelled": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Add --data_is_shelled"
                }),
                "num_threads": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 64,
                    "tooltip": "Number of threads (0 = use 10)"
                }),
                "repol": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Replace outlier slices (--repol)"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("corrected_dwi",)
    FUNCTION = "eddy_correct"
    CATEGORY = "DWI"
    DESCRIPTION = "Eddy current and motion correction using FSL eddy with topup. Outputs go to BIDS derivatives (e.g. derivatives/diffyui/sub-XX/dwi/Eddy/)."

    @classmethod
    def IS_CHANGED(cls, dwi_file, mask_file, acqp_file, bvec_file, bval_file, topup_field, **kwargs):
        import time
        return str(time.time())

    def eddy_correct(
        self,
        dwi_file: str,
        mask_file: str,
        acqp_file: str,
        bvec_file: str,
        bval_file: str,
        topup_field: str,
        flm: str = "quadratic",
        data_is_shelled: bool = True,
        num_threads: int = 10,
        repol: bool = True,
    ):
        """
        Run FSL eddy (or eddy_cuda10.2) with topup field.
        """
        print("[DWI Eddy] ===== FUNCTION CALLED =====")
        flm_options = ["linear", "quadratic", "cubic"]
        if isinstance(flm, int) and 0 <= flm < len(flm_options):
            flm = flm_options[flm]
        elif flm not in flm_options:
            flm = "quadratic"
        try:
            # Resolve and validate required paths
            dwi_path = Path(dwi_file.strip()).expanduser() if dwi_file else None
            mask_path = Path(mask_file.strip()).expanduser() if mask_file else None
            acqp_path = Path(acqp_file.strip()).expanduser() if acqp_file else None
            bvec_path = Path(bvec_file.strip()).expanduser() if bvec_file else None
            bval_path = Path(bval_file.strip()).expanduser() if bval_file else None
            topup_field_path = Path(topup_field.strip()).expanduser() if topup_field else None

            for name, path in [
                ("DWI", dwi_path),
                ("mask", mask_path),
                ("acqp", acqp_path),
                ("bvec", bvec_path),
                ("bval", bval_path),
                ("topup_field", topup_field_path),
            ]:
                if not path or not path.exists():
                    error_msg = f"{name} file not found: {path}"
                    print(f"[DWI Eddy] ERROR: {error_msg}")
                    return (f"Error: {error_msg}",)
                if not path.is_file():
                    error_msg = f"{name} path is not a file: {path}"
                    print(f"[DWI Eddy] ERROR: {error_msg}")
                    return (f"Error: {error_msg}",)

            print("[DWI Eddy] All required input files validated.")

            # Topup prefix from topup_field (expect ..._fieldcoef.nii.gz from Topup node)
            if topup_field_path.name.endswith("_fieldcoef.nii.gz"):
                topup_prefix = str(
                    topup_field_path.parent / topup_field_path.name.replace("_fieldcoef.nii.gz", "")
                )
            else:
                topup_prefix = str(topup_field_path)
            print(f"[DWI Eddy] Topup prefix: {topup_prefix}")

            # BIDS inference from dwi_file (same logic as Topup node)
            path_parts = dwi_path.parts
            subject_id = None
            bids_root = None
            if "derivatives" in path_parts:
                deriv_idx = path_parts.index("derivatives")
                if deriv_idx > 0:
                    bids_root = Path(*path_parts[:deriv_idx])
                    for i in range(deriv_idx - 1, -1, -1):
                        if path_parts[i].startswith("sub-"):
                            subject_id = path_parts[i]
                            break
            else:
                for i, part in enumerate(path_parts):
                    if part.startswith("sub-"):
                        subject_id = part
                        if i > 0:
                            bids_root = Path(*path_parts[:i])
                        break

            if not subject_id or not bids_root:
                output_dir = dwi_path.parent / "Eddy"
            else:
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi" / "Eddy"

            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[DWI Eddy] Output directory: {output_dir}")

            # Stem from DWI name (strip .nii.gz / _topup etc.)
            dwi_stem = dwi_path.stem.replace(".nii", "")
            if dwi_stem.endswith(".gz"):
                dwi_stem = dwi_stem[:-3].replace(".nii", "")
            eddy_out_prefix = output_dir / f"{dwi_stem}_eddy"
            print(f"[DWI Eddy] Eddy output prefix: {eddy_out_prefix}")

            # Index file: always auto-generate from bval count (one line of 1s per volume)
            with open(bval_path, "r") as f:
                bval_tokens = f.read().split()
            n_vols = len(bval_tokens)
            index_path = output_dir / "index.txt"
            with open(index_path, "w") as f:
                f.write(" ".join(["1"] * n_vols) + "\n")
            print(f"[DWI Eddy] Generated index.txt with {n_vols} volumes: {index_path}")

            # Eddy binary: prefer CPU version (eddy_cpu, eddy_openmp) for multi-threading; fallback to eddy
            eddy_bin = shutil.which("eddy_cpu") or shutil.which("eddy_openmp") or shutil.which("eddy")
            if not eddy_bin:
                fsl_bin = Path(os.environ.get("FSLDIR", "/usr/share/fsl")) / "bin"
                for name in ("eddy_cpu", "eddy_openmp", "eddy"):
                    candidate = fsl_bin / name
                    if candidate.exists():
                        eddy_bin = str(candidate)
                        break
            if not eddy_bin:
                error_msg = "No eddy binary found (tried eddy_cpu, eddy_openmp, eddy in PATH and FSLDIR/bin)"
                print(f"[DWI Eddy] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)

            print(f"[DWI Eddy] Using eddy binary: {eddy_bin}")

            # Threads: GPU (CUDA) eddy only allows --nthr=1; CPU eddy can use multiple threads
            # Prefer nthr=1 if binary name suggests GPU (eddy_cuda* or path contains cuda/gpu)
            eddy_bin_lower = eddy_bin.lower()
            nthr = num_threads if num_threads > 0 else 10
            if "cuda" in eddy_bin_lower or "gpu" in eddy_bin_lower:
                nthr = 1
                print(f"[DWI Eddy] GPU eddy binary detected: using --nthr=1 (required)")
            else:
                print(f"[DWI Eddy] Using {nthr} threads")

            # Build eddy command (FSL --key=value style)
            def build_eddy_cmd(nthr_val):
                cmd = [
                    eddy_bin,
                    f"--imain={dwi_path}",
                    f"--mask={mask_path}",
                    f"--index={index_path}",
                    f"--acqp={acqp_path}",
                    f"--bvecs={bvec_path}",
                    f"--bvals={bval_path}",
                    f"--topup={topup_prefix}",
                    f"--out={eddy_out_prefix}",
                    f"--flm={flm}",
                    f"--nthr={nthr_val}",
                ]
                if data_is_shelled:
                    cmd.append("--data_is_shelled")
                if repol:
                    cmd.append("--repol")
                return cmd

            eddy_cmd = build_eddy_cmd(nthr)
            print(f"[DWI Eddy] Running: {' '.join(eddy_cmd)}")
            executor = get_executor("fsl")
            return_code, stdout, stderr = executor.execute(
                eddy_cmd,
                working_dir=str(output_dir),
            )

            # GPU build named "eddy" (no cuda in path) still requires --nthr=1; retry if we get that error
            if return_code != 0 and nthr != 1 and ("only use 1 CPU thread" in stderr or "nthr=1" in stderr):
                print(f"[DWI Eddy] GPU eddy requires --nthr=1, retrying with 1 thread")
                eddy_cmd = build_eddy_cmd(1)
                return_code, stdout, stderr = executor.execute(
                    eddy_cmd,
                    working_dir=str(output_dir),
                )

            if return_code != 0:
                error_msg = f"eddy failed: {stderr}"
                if stdout:
                    error_msg += f" stdout: {stdout}"
                print(f"[DWI Eddy] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)

            corrected_dwi = Path(str(eddy_out_prefix) + ".nii.gz")
            if not corrected_dwi.exists():
                error_msg = f"Eddy output not found: {corrected_dwi}"
                print(f"[DWI Eddy] ERROR: {error_msg}")
                return (f"Error: {error_msg}",)

            print("[DWI Eddy] Eddy correction completed successfully.")
            print(f"[DWI Eddy] Corrected DWI: {corrected_dwi}")
            print("[DWI Eddy] ===== CORRECTION COMPLETE =====")
            return (str(corrected_dwi),)

        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            print(f"[DWI Eddy] {error_msg}")
            print(f"[DWI Eddy] Traceback: {traceback.format_exc()}")
            return (error_msg,)
