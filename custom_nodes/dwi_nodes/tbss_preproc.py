"""
TBSS 1 Preproc Node - FSL tbss_1_preproc: scale/crop FA, create FA/ and origdata/.
"""

from pathlib import Path

from ._import_utils import get_executor


class TBSS1PreprocNode:
    """
    Run FSL tbss_1_preproc on a directory of FA images. Connect fa_directory from
    TBSS FA Collector or provide path manually.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fa_directory": ("STRING", {
                    "default": "",
                    "tooltip": "Path to directory containing FA .nii.gz files. Connect from TBSS FA Collector → fa_directory or enter manually."
                }),
            },
            "optional": {
                "pattern": ("STRING", {
                    "default": "*FA*.nii.gz",
                    "tooltip": "Glob pattern for FA files (e.g. *FA*.nii.gz or *_FA.nii.gz)."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("project_dir",)
    FUNCTION = "preproc"
    CATEGORY = "DWI"
    DESCRIPTION = "TBSS step 1: preprocess FA images (scale, crop, remove outer slices). Creates FA/ and origdata/ in the project directory."

    def preproc(self, fa_directory: str, pattern: str = "*FA*.nii.gz"):
        try:
            proj = Path(fa_directory).expanduser().resolve()
            if not proj.exists() or not proj.is_dir():
                err = f"FA directory not found or not a directory: {fa_directory}"
                print(f"[TBSS 1 Preproc] {err}")
                return (err,)

            fa_list = sorted(proj.glob(pattern.strip() or "*FA*.nii.gz"))
            if not fa_list:
                err = f"No FA files matching '{pattern}' in {proj}"
                print(f"[TBSS 1 Preproc] {err}")
                return (err,)

            executor = get_executor("fsl")
            # FSL tbss_1_preproc expects filenames as arguments (run from project dir)
            cmd = ["tbss_1_preproc"] + [str(f.name) for f in fa_list]
            return_code, stdout, stderr = executor.execute(cmd, working_dir=str(proj))

            if return_code != 0:
                err = f"tbss_1_preproc failed: {stderr or stdout}"
                print(f"[TBSS 1 Preproc] {err}")
                return (err,)

            print(f"[TBSS 1 Preproc] Success. project_dir={proj}")
            return (str(proj),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS 1 Preproc] {err}")
            return (err,)
