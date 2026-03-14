"""
TBSS 4 Prestats Node - FSL tbss_4_prestats: threshold skeleton, project FA onto it.
"""

from pathlib import Path

from ._import_utils import get_executor


class TBSS4PrestatsNode:
    """
    Run FSL tbss_4_prestats. Connect project_dir from TBSS 3 Postreg.
    Outputs all_fa_skeletonised_path for downstream voxelwise stats.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "project_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Project directory from TBSS 3 Postreg (project_dir output)."
                }),
            },
            "optional": {
                "threshold": ("FLOAT", {
                    "default": 0.2,
                    "min": 0.1,
                    "max": 0.5,
                    "step": 0.05,
                    "tooltip": "Mean FA skeleton threshold (typical 0.2)."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("project_dir", "all_fa_skeletonised_path")
    FUNCTION = "prestats"
    CATEGORY = "DWI"
    DESCRIPTION = "TBSS step 4: threshold mean FA skeleton and project each subject's FA onto it. Outputs 4D all_FA_skeletonised path."

    def prestats(self, project_dir: str, threshold: float = 0.2):
        try:
            proj = Path(project_dir).expanduser().resolve()
            if not proj.exists() or not proj.is_dir():
                err = f"Project directory not found: {project_dir}"
                print(f"[TBSS 4 Prestats] {err}")
                return (err, err)

            executor = get_executor("fsl")
            # FSL tbss_4_prestats takes threshold as argument
            cmd = ["tbss_4_prestats", str(threshold)]
            return_code, stdout, stderr = executor.execute(cmd, working_dir=str(proj))

            if return_code != 0:
                err = f"tbss_4_prestats failed: {stderr or stdout}"
                print(f"[TBSS 4 Prestats] {err}")
                return (err, err)

            stats_dir = proj / "stats"
            all_fa_skel = stats_dir / "all_FA_skeletonised.nii.gz"
            if not all_fa_skel.exists():
                all_fa_skel = proj / "all_FA_skeletonised.nii.gz"

            print(f"[TBSS 4 Prestats] Success. project_dir={proj}")
            return (str(proj), str(all_fa_skel))

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS 4 Prestats] {err}")
            return (err, err)
