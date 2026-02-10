"""
NIfTI Stats Node - Run fslstats or mrinfo on an input image and output structured text
with all extractable structural (fslstats) or diffusion-weighted (mrinfo) info for LLM use.
"""

import re
from pathlib import Path

from ._import_utils import get_executor


def _resolve_image_path(image) -> Path | None:
    """Resolve image input to a single path (widget str or linked list/tuple)."""
    if image is None:
        return None
    if isinstance(image, (list, tuple)):
        image = image[0] if image else ""
    image = str(image).strip() if image else ""
    if not image:
        return None
    return Path(image).expanduser()


# fslstats output order for: -m -M -s -S -v -V -e -E -R -r -c -C -x -X -w -p 25 -p 50 -p 75 -P 25 -P 50 -P 75
# Each option outputs one value per line except: -R and -r give 2 lines, -c -C -x -X give 3 lines each, -w gives 6 lines
FSLSTATS_LABELS = [
    "mean", "mean_nonzero", "std", "std_nonzero",
    "volume_mm3", "volume_nonzero_mm3", "entropy", "entropy_nonzero",
    "min", "max", "robust_min", "robust_max",
    "cog_mm_x", "cog_mm_y", "cog_mm_z",
    "cog_vox_x", "cog_vox_y", "cog_vox_z",
    "coord_max_x", "coord_max_y", "coord_max_z",
    "coord_min_x", "coord_min_y", "coord_min_z",
    "roi_xmin", "roi_xmax", "roi_ymin", "roi_ymax", "roi_zmin", "roi_zmax",
    "percentile_25", "percentile_50", "percentile_75",
    "percentile_nonzero_25", "percentile_nonzero_50", "percentile_nonzero_75",
]


def _parse_fslstats_lines(stdout: str) -> list[float]:
    """Extract all numeric values from fslstats stdout (one per line or space-separated)."""
    values = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        for part in line.split():
            try:
                values.append(float(part))
            except ValueError:
                pass
    return values


def _format_fslstats_structured(path: str, stdout: str, stderr: str) -> str:
    """
    Run fslstats with all common options and parse into structured text.
    Uses fixed option order so we can label each value.
    """
    values = _parse_fslstats_lines(stdout)
    out = [
        "## Image statistics (fslstats) – full structural output",
        f"path: {path}",
        "tool: fslstats",
        "",
    ]
    for i, label in enumerate(FSLSTATS_LABELS):
        if i < len(values):
            v = values[i]
            if label.startswith("coord_") or label.startswith("cog_") or label.startswith("roi_"):
                out.append(f"{label}: {v}")
            elif "percentile" in label or "nonzero" in label:
                out.append(f"{label}: {v}")
            else:
                out.append(f"{label}: {v}")
        else:
            break
    if len(values) > len(FSLSTATS_LABELS):
        out.append("")
        out.append("# additional values (unexpected extra output)")
        for i in range(len(FSLSTATS_LABELS), len(values)):
            out.append(f"value_{i}: {values[i]}")
    if not values and stderr:
        out.append("(no numeric output)")
        out.append(f"stderr: {stderr[:800]}")
    return "\n".join(out)


def _run_fslstats_full(executor, path_str: str) -> tuple[int, str, str]:
    """Run fslstats with all structural options in fixed order."""
    cmd = [
        path_str,
        "-m", "-M", "-s", "-S", "-v", "-V", "-e", "-E",
        "-R", "-r",
        "-c", "-C", "-x", "-X", "-w",
        "-p", "25", "-p", "50", "-p", "75",
        "-P", "25", "-P", "50", "-P", "75",
    ]
    return executor.execute(["fslstats"] + cmd)


def _format_mrinfo_structured(path: str, stdout_main: str, stdout_dwgrad: str, stdout_shell: str, stdout_dw_scheme: str, stderr: str) -> str:
    """
    Combine full mrinfo output with optional DWI gradient/shell/scheme into one structured block.
    """
    out = [
        "## Image information (mrinfo) – full structural and diffusion-weighted output",
        f"path: {path}",
        "tool: mrinfo",
        "",
        "### Header and dimensions",
        "",
    ]
    key_pattern = re.compile(r"^\s*([^:]+):\s*(.+)$")
    for line in stdout_main.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = key_pattern.match(line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            out.append(f"{key}: {val}")
    if stdout_dwgrad.strip():
        out.append("")
        out.append("### Diffusion gradient table (MRtrix interpreted)")
        out.append("")
        out.append(stdout_dwgrad.strip())
    if stdout_shell.strip():
        out.append("")
        out.append("### Shell b-values / sizes / indices")
        out.append("")
        out.append(stdout_shell.strip())
    if stdout_dw_scheme.strip():
        out.append("")
        out.append("### Raw DW scheme (header property dw_scheme)")
        out.append("")
        out.append(stdout_dw_scheme.strip())
    if len(out) <= 8 and stderr:
        out.append("")
        out.append("(minimal parse)")
        out.append(f"stderr: {stderr[:500]}")
    return "\n".join(out)


def _run_mrinfo_full(executor, path_str: str) -> tuple[str, str, str, str, str]:
    """
    Run mrinfo for full info, then DWI-specific options. Returns (stdout_main, stdout_dwgrad, stdout_shell, stdout_dw_scheme, stderr).
    """
    rc_main, out_main, err_main = executor.execute(["mrinfo", path_str, "-all"])
    if rc_main != 0:
        return out_main, "", "", "", err_main or out_main

    rc_dw, out_dw, _ = executor.execute(["mrinfo", path_str, "-dwgrad"])
    stdout_dwgrad = out_dw if rc_dw == 0 else ""

    rc_shell, out_shell, _ = executor.execute([
        "mrinfo", path_str,
        "-shell_bvalues", "-shell_sizes", "-shell_indices",
    ])
    stdout_shell = out_shell if rc_shell == 0 else ""

    rc_scheme, out_scheme, _ = executor.execute(["mrinfo", path_str, "-property", "dw_scheme"])
    stdout_dw_scheme = out_scheme.strip() if rc_scheme == 0 and out_scheme.strip() else ""

    return out_main, stdout_dwgrad, stdout_shell, stdout_dw_scheme, err_main


class NIfTIStatsNode:
    """
    NIfTI Stats - Run fslstats (FSL) or mrinfo (MRtrix) on an input NIfTI image and output
    structured text with all extractable data: full structural stats (fslstats) or full
    structural + diffusion-weighted info (mrinfo). Output is LLM-friendly. Connect to Preview as Text or feed to an LLM.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("STRING", {
                    "default": "",
                    "tooltip": "Path to NIfTI image (.nii or .nii.gz)"
                }),
            },
            "optional": {
                "tool": (["fslstats", "mrinfo"], {
                    "default": "fslstats",
                    "tooltip": "Tool to use: fslstats (FSL) or mrinfo (MRtrix)"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("stats",)
    FUNCTION = "get_stats"
    CATEGORY = "DWI"
    DESCRIPTION = "Run fslstats or mrinfo on a NIfTI image; output all structural (fslstats) or structural + DWI (mrinfo) data as structured text for Preview as Text or LLM."
    OUTPUT_NODE = True

    def get_stats(self, image: str, tool: str = "fslstats"):
        """
        Run fslstats or mrinfo and return full structured text (all extractable data).
        """
        print(f"[NIfTI Stats] get_stats() tool={tool!r}", flush=True)
        path = _resolve_image_path(image)
        if not path or not path.exists():
            err = f"Image file not found: {image!r}"
            print(f"[NIfTI Stats] {err}", flush=True)
            return {"ui": {"text": (err,)}, "result": (err,)}

        if not path.is_file():
            err = f"Path is not a file: {path}"
            print(f"[NIfTI Stats] {err}", flush=True)
            return {"ui": {"text": (err,)}, "result": (err,)}

        path_str = str(path.resolve())

        try:
            if tool == "fslstats":
                executor = get_executor("fsl")
                return_code, stdout, stderr = _run_fslstats_full(executor, path_str)
                if return_code != 0:
                    err = f"fslstats failed: {stderr or stdout or 'unknown error'}"
                    print(f"[NIfTI Stats] {err}", flush=True)
                    return {"ui": {"text": (err,)}, "result": (err,)}
                summary = _format_fslstats_structured(path_str, stdout, stderr)
            else:
                executor = get_executor("mrtrix")
                out_main, out_dw, out_shell, out_scheme, err_main = _run_mrinfo_full(executor, path_str)
                if not out_main and err_main:
                    err = f"mrinfo failed: {err_main}"
                    print(f"[NIfTI Stats] {err}", flush=True)
                    return {"ui": {"text": (err,)}, "result": (err,)}
                summary = _format_mrinfo_structured(
                    path_str, out_main, out_dw, out_shell, out_scheme, err_main
                )
        except Exception as e:
            err = f"Error running {tool}: {e}"
            print(f"[NIfTI Stats] {err}", flush=True)
            return {"ui": {"text": (err,)}, "result": (err,)}

        print(f"[NIfTI Stats] Done. Output length={len(summary)}", flush=True)
        return {"ui": {"text": (summary,)}, "result": (summary,)}
