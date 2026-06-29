"""
Eddy QC Node — FSL eddy_quad quality control report.
Reads outputs from DWI Eddy Correction and runs eddy_quad.
Non-blocking: failures are returned as error strings, not exceptions.
"""

import shutil
from pathlib import Path

from ._import_utils import BIDSHandler, get_executor, CacheManager


class EddyQCNode:
    """
    Run FSL eddy_quad on eddy correction outputs to produce a QC report.
    Connect eddy_corrected_dwi from the DWI Eddy Correction node.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "eddy_corrected_dwi": ("STRING", {
                    "default": "",
                    "tooltip": "Corrected DWI from DWI Eddy Correction (the .nii.gz output)",
                }),
            },
            "optional": {
                "acqp_file": ("STRING", {
                    "default": "",
                    "tooltip": "Acquisition parameters file (acqp_file output from Topup node)",
                }),
                "mask_file": ("STRING", {
                    "default": "",
                    "tooltip": "Brain mask used during eddy correction",
                }),
                "bval_file": ("STRING", {
                    "default": "",
                    "tooltip": "b-values file (.bval)",
                }),
                "field_file": ("STRING", {
                    "default": "",
                    "tooltip": "Fieldmap file from topup (optional, improves QC plot)",
                }),
                "verbose": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable verbose output from eddy_quad",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("qc_report_dir",)
    FUNCTION = "run_qc"
    CATEGORY = "DWI/Preprocessing"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Run FSL eddy_quad QC on eddy correction outputs. "
        "Returns the path to the .qc directory. Never raises — failures are returned as strings."
    )

    @classmethod
    def IS_CHANGED(cls, eddy_corrected_dwi, acqp_file="", mask_file="",
                   bval_file="", field_file="", verbose=False):
        try:
            params = CacheManager.build_params_for_hash(
                kwargs={"eddy_corrected_dwi": eddy_corrected_dwi, "acqp_file": acqp_file,
                        "mask_file": mask_file, "bval_file": bval_file, "field_file": field_file},
                file_keys=["eddy_corrected_dwi", "acqp_file", "mask_file", "bval_file"],
            )
            return CacheManager.compute_param_hash(params)
        except Exception:
            return float("nan")

    def run_qc(self, eddy_corrected_dwi: str, acqp_file: str = "", mask_file: str = "",
               bval_file: str = "", field_file: str = "", verbose: bool = False) -> tuple:
        """
        Run eddy_quad QC report.

        Args:
            eddy_corrected_dwi: Path to eddy-corrected DWI (.nii.gz from EddyCorrection node)
            acqp_file: Acquisition parameters file
            mask_file: Brain mask
            bval_file: b-values file
            field_file: Topup fieldmap (optional)
            verbose: Enable verbose eddy_quad output

        Returns:
            Tuple of (qc_report_dir,) — error string if eddy_quad failed
        """
        print("[Eddy QC] ===== FUNCTION CALLED =====")
        try:
            if not eddy_corrected_dwi or not eddy_corrected_dwi.strip():
                return ("Error: eddy_corrected_dwi is required",)

            corrected_dwi = Path(eddy_corrected_dwi.strip())
            if not corrected_dwi.exists():
                return (f"Error: eddy corrected DWI not found: {corrected_dwi}",)

            # Derive eddy prefix by stripping .nii.gz
            eddy_prefix = corrected_dwi.with_suffix("").with_suffix("")
            eddy_dir = corrected_dwi.parent

            # Locate index.txt in the same directory (written by eddy_correction.py)
            index_path = eddy_dir / "index.txt"
            if not index_path.exists():
                return (f"Error: index.txt not found in {eddy_dir}",)

            # ── Block 1: build param hash ──
            _params = CacheManager.build_params_for_hash(
                kwargs={"eddy_corrected_dwi": eddy_corrected_dwi, "acqp_file": acqp_file,
                        "mask_file": mask_file, "bval_file": bval_file, "field_file": field_file},
                file_keys=["eddy_corrected_dwi", "acqp_file", "mask_file", "bval_file"],
            )
            _param_hash = CacheManager.compute_param_hash(_params)

            qc_dir = Path(str(eddy_prefix) + ".qc")

            # ── Block 2: check cache ──
            _cache_path = eddy_dir / ".diffyui_qc_cache.json"
            _expected = [str(qc_dir)]
            _is_hit, _cached = CacheManager.check_cache(
                _cache_path, "EddyQC", _param_hash, _expected
            )
            if _is_hit:
                print("[Eddy QC] Cache hit — skipping.")
                return tuple(_cached)

            # eddy_quad refuses to run if qc dir already exists — remove it
            if qc_dir.exists():
                shutil.rmtree(qc_dir)

            # Locate eddy_quad binary
            eddy_quad_bin = shutil.which("eddy_quad")
            if not eddy_quad_bin:
                fsl_bin = Path(__import__("os").environ.get("FSLDIR", "/usr/share/fsl")) / "bin"
                candidate = fsl_bin / "eddy_quad"
                if candidate.exists():
                    eddy_quad_bin = str(candidate)
            if not eddy_quad_bin:
                return ("Error: eddy_quad not found in PATH or FSLDIR/bin",)

            cmd = [
                eddy_quad_bin,
                str(eddy_prefix),
                "-idx", str(index_path),
            ]

            if acqp_file and Path(acqp_file).exists():
                cmd += ["-par", acqp_file]
            if mask_file and Path(mask_file).exists():
                cmd += ["-m", mask_file]
            if bval_file and Path(bval_file).exists():
                cmd += ["-b", bval_file]
            if field_file and Path(field_file).exists():
                cmd += ["-f", field_file]
            if verbose:
                cmd.append("-v")

            print(f"[Eddy QC] Command: {' '.join(cmd)}")
            executor = get_executor("fsl")
            rc, stdout, stderr = executor.execute(cmd, working_dir=str(eddy_dir))

            if rc != 0:
                msg = f"Error: eddy_quad exited {rc}: {stderr or stdout}"
                print(f"[Eddy QC] {msg}")
                return (msg,)

            if not qc_dir.exists():
                msg = f"Error: eddy_quad completed but QC directory not found: {qc_dir}"
                print(f"[Eddy QC] {msg}")
                return (msg,)

            print(f"[Eddy QC] QC report: {qc_dir}")

            # ── Block 3: update cache ──
            CacheManager.update_cache(
                _cache_path, "EddyQC", _param_hash, _params, [str(qc_dir)]
            )

            return (str(qc_dir),)

        except Exception as e:
            import traceback
            print(f"[Eddy QC] ERROR: {e}")
            print(traceback.format_exc())
            return (f"Error: {e}",)
