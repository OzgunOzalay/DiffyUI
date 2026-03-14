"""
DWI Eddy Correction Node - Eddy current and motion correction.
Uses FSL eddy: prefers CUDA version (eddy_cuda, eddy_cuda10.2, etc.) when available,
then falls back to CPU (eddy_cpu, eddy_openmp, eddy). Topup field for distortion correction.
Frees GPU memory before running eddy_cuda for optimal performance.
"""

import os
import shutil
import multiprocessing
from pathlib import Path

from ._import_utils import BIDSHandler, get_executor

print("[DWI Eddy] ===== MODULE LOADING =====")

# Import ComfyUI model management for GPU cleanup
try:
    import comfy.model_management as model_management
    HAS_MODEL_MANAGEMENT = True
except ImportError:
    HAS_MODEL_MANAGEMENT = False
    print("[DWI Eddy] Warning: ComfyUI model_management not available; GPU cleanup disabled")


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
                    "tooltip": "AP-phase DWI file only (e.g. topup-corrected). If comma-separated, first file is used."
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
                    "tooltip": "AP-phase bvec only (e.g. from Subject Bucket ap_phase_bvec). If comma-separated, first is used."
                }),
                "bval_file": ("STRING", {
                    "default": "",
                    "tooltip": "AP-phase bval only (e.g. from Subject Bucket ap_phase_bval). If comma-separated, first is used."
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

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("corrected_dwi", "rotated_bvecs")
    FUNCTION = "eddy_correct"
    CATEGORY = "DWI"
    DESCRIPTION = "Eddy current and motion correction using FSL eddy (prefers CUDA) with topup. Automatically frees GPU memory before running eddy_cuda for optimal performance. Processes AP-phase DWI only (single file); comma-separated inputs use first path only. Outputs to BIDS derivatives (e.g. derivatives/diffyui/sub-XX/dwi/Eddy/)."

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
        Run FSL eddy (prefers CUDA binary when available) with topup field.
        Processes AP-phase DWI only (single file per run). If inputs are comma-separated
        (e.g. from Subject Bucket), only the first path is used to avoid extra files or loops.
        """
        def first_path(value):
            """Take first path from comma-separated string or list; ensure single file for AP phase."""
            if value is None or (isinstance(value, str) and not value.strip()):
                return None
            if isinstance(value, (list, tuple)):
                s = str(value[0]).strip() if value else ""
            else:
                s = str(value).strip()
            if not s:
                return None
            # Comma-separated: use first only (AP phase; do not process PA or multiple runs here)
            first = s.split(",")[0].strip()
            return Path(first).expanduser() if first else None

        print("[DWI Eddy] ===== FUNCTION CALLED =====")
        flm_options = ["linear", "quadratic", "cubic"]
        if isinstance(flm, int) and 0 <= flm < len(flm_options):
            flm = flm_options[flm]
        elif flm not in flm_options:
            flm = "quadratic"
        try:
            # Resolve to single path per input (AP phase only; ignore PA and any extra comma-separated files)
            dwi_path = first_path(dwi_file)
            mask_path = first_path(mask_file)
            acqp_path = first_path(acqp_file)
            bvec_path = first_path(bvec_file)
            bval_path = first_path(bval_file)
            topup_field_path = first_path(topup_field)
            if dwi_file and "," in str(dwi_file).strip():
                print("[DWI Eddy] Multiple paths in dwi_file: using first only (AP phase). Do not process PA or extra runs in this node.")
            if bval_file and "," in str(bval_file).strip():
                print("[DWI Eddy] Multiple paths in bval_file: using first only.")
            if bvec_file and "," in str(bvec_file).strip():
                print("[DWI Eddy] Multiple paths in bvec_file: using first only.")

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
                    return (f"Error: {error_msg}", "")
                if not path.is_file():
                    error_msg = f"{name} path is not a file: {path}"
                    print(f"[DWI Eddy] ERROR: {error_msg}")
                    return (f"Error: {error_msg}", "")

            print("[DWI Eddy] All required input files validated.")

            # Topup prefix from topup_field (expect ..._fieldcoef.nii.gz from Topup node)
            if topup_field_path.name.endswith("_fieldcoef.nii.gz"):
                topup_prefix = str(
                    topup_field_path.parent / topup_field_path.name.replace("_fieldcoef.nii.gz", "")
                )
            else:
                topup_prefix = str(topup_field_path)
            print(f"[DWI Eddy] Topup prefix: {topup_prefix}")

            # BIDS inference from dwi_file
            bids_root, subject_id = BIDSHandler.infer_bids_paths(dwi_path)
            if not subject_id or not bids_root:
                output_dir = dwi_path.parent / "Eddy"
            else:
                bids = BIDSHandler(str(bids_root))
                derivatives_path = bids.get_derivatives_path(subject_id, "diffyui")
                output_dir = derivatives_path / "dwi" / "Eddy"

            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[DWI Eddy] Output directory: {output_dir}")
            
            # Check if output is on fast storage
            try:
                import subprocess
                mount_result = subprocess.run(
                    ["df", "-T", str(output_dir)],
                    capture_output=True, text=True, timeout=2
                )
                if mount_result.returncode == 0:
                    fs_type = mount_result.stdout.split('\n')[1].split()[1] if len(mount_result.stdout.split('\n')) > 1 else "unknown"
                    if fs_type in ("tmpfs", "ramfs"):
                        print(f"[DWI Eddy] Output on RAM disk ({fs_type}) - optimal I/O performance")
                    elif fs_type in ("ext4", "xfs", "btrfs"):
                        print(f"[DWI Eddy] Output on {fs_type} filesystem")
                        print(f"[DWI Eddy] Tip: For faster processing, consider using tmpfs/RAM disk for output")
            except Exception:
                pass  # Skip filesystem check if it fails

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

            # Eddy binary: prefer CUDA version for speed, then fall back to CPU
            fsl_bin = Path(os.environ.get("FSLDIR", "/usr/share/fsl")) / "bin"
            eddy_bin = None
            # 1) Prefer CUDA: eddy_cuda, eddy_cuda10.2, eddy_cuda11.x, or any eddy_*cuda* in PATH then FSLDIR/bin
            for name in ("eddy_cuda", "eddy_cuda10.2", "eddy_cuda11.0", "eddy_cuda11.2", "eddy_cuda11.4", "eddy_cuda11.6", "eddy_cuda11.8"):
                candidate = shutil.which(name) or (str(fsl_bin / name) if (fsl_bin / name).exists() else None)
                if candidate:
                    eddy_bin = candidate
                    break
            if not eddy_bin and fsl_bin.exists():
                for candidate in sorted(fsl_bin.glob("eddy_cuda*")):
                    if candidate.is_file() and os.access(candidate, os.X_OK):
                        eddy_bin = str(candidate)
                        break
                    if candidate.is_symlink():
                        eddy_bin = str(candidate)
                        break
            # 2) Fall back to CPU: eddy_cpu, eddy_openmp, eddy
            if not eddy_bin:
                eddy_bin = shutil.which("eddy_cpu") or shutil.which("eddy_openmp") or shutil.which("eddy")
            if not eddy_bin and fsl_bin.exists():
                for name in ("eddy_cpu", "eddy_openmp", "eddy"):
                    candidate = fsl_bin / name
                    if candidate.exists():
                        eddy_bin = str(candidate)
                        break
            if not eddy_bin:
                error_msg = "No eddy binary found (tried eddy_cuda*, eddy_cpu, eddy_openmp, eddy in PATH and FSLDIR/bin)"
                print(f"[DWI Eddy] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "")

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
                
                # Performance optimizations for eddy_cuda
                if "cuda" in eddy_bin_lower or "gpu" in eddy_bin_lower:
                    # --dont_sep_offs_move: Skip separation of field offset & subject movement (faster, minimal quality impact)
                    cmd.append("--dont_sep_offs_move")
                    # --dont_peas: Skip post-eddy alignment of shells (faster for single-shell or if not needed)
                    # Only add if single-shell data (check bval file)
                    try:
                        with open(bval_path, "r") as f:
                            bvals = [int(float(x)) for x in f.read().split()]
                        unique_shells = len(set(b for b in bvals if b > 100))  # Exclude b0
                        if unique_shells <= 1:
                            cmd.append("--dont_peas")
                            print(f"[DWI Eddy] Single-shell data detected: adding --dont_peas for faster processing")
                    except Exception as e:
                        print(f"[DWI Eddy] Warning: Could not parse bvals for shell detection: {e}")
                    
                    # --nvoxhp=1000: Reduce hyperparameter voxels (faster, good for most data)
                    cmd.append("--nvoxhp=1000")
                    
                    print("[DWI Eddy] CUDA performance optimizations enabled: --dont_sep_offs_move, --nvoxhp=1000")
                
                return cmd

            eddy_cmd = build_eddy_cmd(nthr)
            print(f"[DWI Eddy] Running: {' '.join(eddy_cmd)}")
            
            # Free GPU memory before running eddy_cuda for max performance
            if HAS_MODEL_MANAGEMENT and ("cuda" in eddy_bin_lower or "gpu" in eddy_bin_lower):
                print("[DWI Eddy] Freeing GPU memory (unloading ComfyUI models)...")
                try:
                    model_management.unload_all_models()
                    model_management.soft_empty_cache()
                    print("[DWI Eddy] GPU memory freed. eddy_cuda now has full GPU access.")
                except Exception as e:
                    print(f"[DWI Eddy] Warning: GPU cleanup failed: {e}. Continuing anyway.")
            
            executor = get_executor("fsl")
            return_code, stdout, stderr = executor.execute(
                eddy_cmd,
                working_dir=str(output_dir),
            )

            # GPU build named "eddy" (no cuda in path) still requires --nthr=1; retry if we get that error
            if return_code != 0 and nthr != 1 and ("only use 1 CPU thread" in stderr or "nthr=1" in stderr):
                print(f"[DWI Eddy] GPU eddy requires --nthr=1, retrying with 1 thread")
                eddy_cmd = build_eddy_cmd(1)
                # GPU still clean from previous call; no need to free again
                return_code, stdout, stderr = executor.execute(
                    eddy_cmd,
                    working_dir=str(output_dir),
                )

            if return_code != 0:
                error_msg = f"eddy failed: {stderr}"
                if stdout:
                    error_msg += f" stdout: {stdout}"
                print(f"[DWI Eddy] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "")

            corrected_dwi = Path(str(eddy_out_prefix) + ".nii.gz")
            if not corrected_dwi.exists():
                error_msg = f"Eddy output not found: {corrected_dwi}"
                print(f"[DWI Eddy] ERROR: {error_msg}")
                return (f"Error: {error_msg}", "")

            # FSL eddy outputs rotated bvecs (critical for downstream DTIfit)
            rotated_bvecs = Path(str(eddy_out_prefix) + ".eddy_rotated_bvecs")
            rotated_bvecs_str = str(rotated_bvecs) if rotated_bvecs.exists() else ""
            if rotated_bvecs_str:
                print(f"[DWI Eddy] Rotated bvecs: {rotated_bvecs}")
            else:
                print("[DWI Eddy] Warning: Rotated bvecs file not found")

            print("[DWI Eddy] Eddy correction completed successfully.")
            print(f"[DWI Eddy] Corrected DWI: {corrected_dwi}")
            print("[DWI Eddy] ===== CORRECTION COMPLETE =====")
            return (str(corrected_dwi), rotated_bvecs_str)

        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            print(f"[DWI Eddy] {error_msg}")
            print(f"[DWI Eddy] Traceback: {traceback.format_exc()}")
            return (error_msg, "")
