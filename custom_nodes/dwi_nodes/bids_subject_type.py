"""
BIDS_SUBJECT — ComfyUI type that carries all per-subject BIDS file paths as a dict.

Passed between BIDSProjectLoader → SubjectBatchRunner → pack nodes.

Schema:
    {
        "bids_root":        str,          # absolute path to BIDS root
        "subject_id":       str,          # e.g. "sub-001"
        "session_id":       str | None,   # e.g. "ses-01" or None
        "sessions":         list[str],    # all sessions found, [] if none
        "files": {
            "dwi_ap":  str,  "bvec_ap":  str,  "bval_ap":  str,   # AP phase
            "dwi_pa":  str,  "bvec_pa":  str,  "bval_pa":  str,   # PA phase
            "dwi":     str,  "bvec":     str,  "bval":     str,   # single phase
            "t1w":     str,
        },
        "derivatives_root": str,          # sub-XXX/derivatives/diffyui[/ses-YY]
    }
"""

from pathlib import Path

BIDS_SUBJECT = "BIDS_SUBJECT"


def build_bids_subject(bids_root: str, subject_id: str) -> dict:
    """Scan one subject's BIDS directory and return a BIDS_SUBJECT dict."""
    bids_path = Path(bids_root)
    subject_path = bids_path / subject_id

    sessions: list[str] = []
    if subject_path.exists():
        sessions = sorted(d.name for d in subject_path.iterdir()
                         if d.is_dir() and d.name.startswith("ses-"))

    session_id = sessions[0] if sessions else None

    if session_id:
        dwi_dir = subject_path / session_id / "dwi"
        anat_dir = subject_path / session_id / "anat"
        deriv_root = bids_path / subject_id / "derivatives" / "diffyui" / session_id
    else:
        dwi_dir = subject_path / "dwi"
        anat_dir = subject_path / "anat"
        deriv_root = bids_path / subject_id / "derivatives" / "diffyui"

    files: dict[str, str] = {}
    _scan_dwi(dwi_dir, files)
    _scan_anat(anat_dir, files)

    return {
        "bids_root": str(bids_path),
        "subject_id": subject_id,
        "session_id": session_id,
        "sessions": sessions,
        "files": files,
        "derivatives_root": str(deriv_root),
    }


def _scan_dwi(dwi_dir: Path, files: dict) -> None:
    if not dwi_dir.exists():
        return

    for ext in (".nii.gz", ".nii"):
        ap = sorted(dwi_dir.glob(f"*_dir-AP_dwi{ext}"))
        if ap:
            _register(ap[0], "ap", files)
            break

    for ext in (".nii.gz", ".nii"):
        pa = sorted(dwi_dir.glob(f"*_dir-PA_dwi{ext}"))
        if pa:
            _register(pa[0], "pa", files)
            break

    if "dwi_ap" not in files:
        for ext in (".nii.gz", ".nii"):
            single = [f for f in sorted(dwi_dir.glob(f"*_dwi{ext}"))
                      if "_dir-" not in f.name]
            if single:
                _register(single[0], "", files)
                break


def _register(nii: Path, tag: str, files: dict) -> None:
    suffix = f"_{tag}" if tag else ""
    files[f"dwi{suffix}"] = str(nii)
    base = nii.with_suffix("").with_suffix("")
    for ext, key in ((".bvec", f"bvec{suffix}"), (".bval", f"bval{suffix}")):
        p = base.with_suffix(ext)
        if p.exists():
            files[key] = str(p)


def _scan_anat(anat_dir: Path, files: dict) -> None:
    if not anat_dir.exists():
        return
    for ext in (".nii.gz", ".nii"):
        t1 = sorted(anat_dir.glob(f"*_T1w{ext}"))
        if t1:
            files["t1w"] = str(t1[0])
            break
