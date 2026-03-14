"""
TBSS 2 Reg Node - FSL tbss_2_reg: non-linear registration to template or midpoint.
"""

from pathlib import Path

from ._import_utils import get_executor


class TBSS2RegNode:
    """
    Run FSL tbss_2_reg. Connect project_dir from TBSS 1 Preproc.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "project_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Project directory from TBSS 1 Preproc (project_dir output)."
                }),
                "target": (["Template (FMRIB58_FA)", "Mid-point (most representative subject)"], {
                    "default": "Template (FMRIB58_FA)",
                    "tooltip": "Registration target: -T = FMRIB58_FA template, -n = midpoint subject."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("project_dir",)
    FUNCTION = "reg"
    CATEGORY = "DWI"
    DESCRIPTION = "TBSS step 2: non-linear registration of all FA images to standard space (-T template or -n midpoint)."

    def reg(self, project_dir: str, target: str):
        try:
            proj = Path(project_dir).expanduser().resolve()
            if not proj.exists() or not proj.is_dir():
                err = f"Project directory not found: {project_dir}"
                print(f"[TBSS 2 Reg] {err}")
                return (err,)

            flag = "-T" if target.startswith("Template") else "-n"
            executor = get_executor("fsl")
            cmd = ["tbss_2_reg", flag]
            return_code, stdout, stderr = executor.execute(cmd, working_dir=str(proj))

            if return_code != 0:
                err = f"tbss_2_reg failed: {stderr or stdout}"
                print(f"[TBSS 2 Reg] {err}")
                return (err,)

            print(f"[TBSS 2 Reg] Success. project_dir={proj}")
            return (str(proj),)

        except Exception as e:
            err = f"Error: {e}"
            print(f"[TBSS 2 Reg] {err}")
            return (err,)
