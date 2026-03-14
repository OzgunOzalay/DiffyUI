"""
TBSS 3 Postreg Node - FSL tbss_3_postreg: apply warps, create mean FA and skeleton.
"""

from pathlib import Path

from ._import_utils import get_executor


class TBSS3PostregNode:
    """
    Run FSL tbss_3_postreg. Connect project_dir from TBSS 2 Reg.
    Outputs mean_fa_path and mean_fa_skeleton_path for NIfTI Preview / NIfTI Stats.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "project_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Project directory from TBSS 2 Reg (project_dir output)."
                }),
                "use_study_mean": (["Study-derived mean (-S)", "Standard template (-T)"], {
                    "default": "Study-derived mean (-S)",
                    "tooltip": "-S = study mean FA; -T = standard template."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("project_dir", "mean_fa_path", "mean_fa_skeleton_path")
    FUNCTION = "postreg"
    CATEGORY = "DWI"
    DESCRIPTION = "TBSS step 3: apply warps, create mean FA and mean FA skeleton. Outputs paths for preview/stats."

    def postreg(self, project_dir: str, use_study_mean: str):
        try:
            proj = Path(project_dir).expanduser().resolve()
            if not proj.exists() or not proj.is_dir():
                err = f"Project directory not found: {project_dir}"
                print(f"[TBSS 3 Postreg] {err}")
                return (err, err, err)

            flag = "-S" if "Study-derived" in use_study_mean else "-T"
            executor = get_executor("fsl")
            cmd = ["tbss_3_postreg", flag]
            return_code, stdout, stderr = executor.execute(cmd, working_dir=str(proj))

            if return_code != 0:
                err = f"tbss_3_postreg failed: {stderr or stdout}"
                print(f"[TBSS 3 Postreg] {err}")
                return (err, err, err)

            # FSL typically writes mean_FA and mean_FA_skeleton into stats/
            stats_dir = proj / "stats"
            mean_fa = stats_dir / "mean_FA.nii.gz"
            mean_skeleton = stats_dir / "mean_FA_skeleton.nii.gz"
            if not mean_fa.exists():
                mean_fa = proj / "mean_FA.nii.gz"
            if not mean_skeleton.exists():
                mean_skeleton = proj / "mean_FA_skeleton.nii.gz"

            print(f"[TBSS 3 Postreg] Success. project_dir={proj}")
            return (str(proj), str(mean_fa), str(mean_skeleton))

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS 3 Postreg] {err}")
            return (err, err, err)
