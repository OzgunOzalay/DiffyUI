"""
Subject Batch Runner — processes all BIDS subjects sequentially.

State is saved to ~/.diffyui/batch_state.json.  After each subject the
workflow is re-queued automatically so every subject runs without manual
intervention.

Key features vs. the old design:
  - Outputs a BIDS_SUBJECT bundle (not individual file paths) — connect to
    a workflow pack node (DWIPreprocPack, etc.) to unpack.
  - skip_completed: skips subjects whose derivatives already match
    completion_check (a glob relative to derivatives/diffyui/{subject}/).
  - Failure recording: if a subject's completion_check still doesn't match
    when the batch finishes, it is listed as failed in the batch report.
  - The batch report (STRING output) summarises done/skipped/pending counts
    every run and gives a full pass/fail table on the final subject.
"""

import hashlib
import json
import threading
import time
from pathlib import Path

from .bids_subject_type import BIDS_SUBJECT, build_bids_subject

_STATE_DIR = Path.home() / ".diffyui"
_STATE_FILE = _STATE_DIR / "batch_state.json"


class SubjectBatchRunnerNode:
    """
    Emit one BIDS_SUBJECT per workflow execution and re-queue automatically
    until every subject (that needs processing) has been handled.

    Typical wiring:
        BIDSProjectLoader → bids_dataset, subject_list → SubjectBatchRunner
        SubjectBatchRunner → subject → DWIPreprocPack → processing nodes
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bids_dataset": ("STRING", {"default": ""}),
                "subject_list": ("STRING", {
                    "default": "",
                    "tooltip": "Comma-separated subject IDs from BIDS Project Loader.",
                }),
            },
            "optional": {
                "completion_check": ("STRING", {
                    "default": "",
                    "tooltip": (
                        "Glob relative to derivatives/diffyui/{subject}/. "
                        "When it matches, the subject is considered done and skipped. "
                        "Example: 'dwi/*_FA.nii.gz'   (DTI pipeline done)\n"
                        "         'fba/wmfod_norm.mif' (FBA pipeline done)"
                    ),
                }),
                "skip_completed": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Skip subjects whose completion_check already matches.",
                }),
                "auto_queue": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Re-queue workflow automatically after each subject.",
                }),
                "reset_batch": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Toggle to True to restart from the first subject.",
                }),
            },
        }

    RETURN_TYPES = (BIDS_SUBJECT, "STRING", "INT", "INT", "STRING")
    RETURN_NAMES = ("subject", "subject_id", "current_index", "total_subjects", "batch_report")
    FUNCTION = "run_batch"
    CATEGORY = "DiffyUI/Batch"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Process all BIDS subjects one at a time. Outputs a BIDS_SUBJECT bundle — "
        "connect to DWIPreprocPack (or another pack node) to unpack into file paths."
    )

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(subjects: list) -> str:
        return hashlib.md5(",".join(subjects).encode()).hexdigest()

    @staticmethod
    def _load_state() -> dict | None:
        try:
            if _STATE_FILE.exists():
                return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
        return None

    @staticmethod
    def _save_state(state: dict) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, indent=2))

    # ------------------------------------------------------------------
    # Completion check
    # ------------------------------------------------------------------

    @staticmethod
    def _is_done(bids_root: str, subject_id: str, completion_check: str) -> bool:
        if not completion_check.strip():
            return False
        deriv = Path(bids_root) / "derivatives" / "diffyui" / subject_id
        return bool(list(deriv.glob(completion_check))) if deriv.exists() else False

    # ------------------------------------------------------------------
    # Re-queue
    # ------------------------------------------------------------------

    def _requeue(self) -> None:
        def _do():
            time.sleep(1.0)
            try:
                import requests
                queue = requests.get("http://127.0.0.1:8188/queue", timeout=5).json()
                running = queue.get("queue_running", [])
                if not running:
                    print("[Batch Runner] No running prompt — cannot re-queue.")
                    return
                entry = running[0]
                payload = {
                    "prompt": entry[2],
                    "extra_data": entry[3] if len(entry) > 3 else {},
                    "client_id": "",
                }
                requests.post("http://127.0.0.1:8188/prompt", json=payload, timeout=5)
                print("[Batch Runner] Re-queued for next subject.")
            except Exception as exc:
                print(f"[Batch Runner] Re-queue failed: {exc}")

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Batch report
    # ------------------------------------------------------------------

    @staticmethod
    def _build_report(subjects: list, bids_root: str, completion_check: str,
                      idx: int, total: int, skipped: list) -> str:
        lines = [f"Batch progress: {idx}/{total}"]
        if skipped:
            lines.append(f"Skipped (already done): {', '.join(skipped)}")

        # On final pass: full summary
        if idx >= total and completion_check.strip():
            done, failed = [], []
            for sub in subjects:
                if SubjectBatchRunnerNode._is_done(bids_root, sub, completion_check):
                    done.append(sub)
                else:
                    failed.append(sub)
            lines += ["", "=== Batch complete ===",
                      f"Succeeded: {len(done)}/{total}"]
            if failed:
                lines.append(f"Missing output ({completion_check}):")
                for s in failed:
                    lines.append(f"  {s}")
        elif idx >= total:
            lines.append("=== Batch complete (no completion_check set) ===")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------

    def run_batch(
        self,
        bids_dataset: str = "",
        subject_list: str = "",
        completion_check: str = "",
        skip_completed: bool = True,
        auto_queue: bool = True,
        reset_batch: bool = False,
    ):
        bids_dataset = bids_dataset.strip()
        if isinstance(subject_list, list):
            subjects = [s.strip() for s in subject_list if str(s).strip()]
        else:
            subjects = [s.strip() for s in str(subject_list).split(",") if s.strip()]

        if not subjects:
            raise ValueError("[Batch Runner] subject_list is empty.")
        if not bids_dataset:
            raise ValueError("[Batch Runner] bids_dataset is empty.")

        total = len(subjects)
        subj_hash = self._hash(subjects)

        state = self._load_state()
        if reset_batch or state is None or state.get("subjects_hash") != subj_hash:
            idx = 0
            print(f"[Batch Runner] Starting new batch — {total} subjects.")
        else:
            idx = state.get("idx", 0)

        skipped: list[str] = []

        # Advance past already-completed subjects
        if skip_completed and completion_check.strip():
            while idx < total and self._is_done(bids_dataset, subjects[idx], completion_check):
                print(f"[Batch Runner] Skipping {subjects[idx]} (already done).")
                skipped.append(subjects[idx])
                idx += 1

        if idx >= total:
            report = self._build_report(subjects, bids_dataset, completion_check, idx, total, skipped)
            print(f"[Batch Runner] Batch complete ({total}/{total}).")
            last = subjects[-1]
            subject_data = build_bids_subject(bids_dataset, last)
            return {
                "ui": {"text": [report]},
                "result": (subject_data, last, total, total, report),
            }

        selected = subjects[idx]
        print(f"[Batch Runner] Subject {idx + 1}/{total}: {selected}")

        # Save next index before downstream starts
        self._save_state({
            "idx": idx + 1,
            "total": total,
            "subjects_hash": subj_hash,
            "current_subject": selected,
            "bids_dataset": bids_dataset,
            "completion_check": completion_check,
            "done": idx + 1 >= total,
        })

        # Build BIDS_SUBJECT bundle
        subject_data = build_bids_subject(bids_dataset, selected)

        # Re-queue for next subject (fires before downstream processing)
        next_idx = idx + 1
        # Peek ahead past completed subjects for re-queue decision
        if auto_queue:
            peek = next_idx
            if skip_completed and completion_check.strip():
                while peek < total and self._is_done(bids_dataset, subjects[peek], completion_check):
                    peek += 1
            if peek < total:
                self._requeue()
            else:
                print("[Batch Runner] All remaining subjects done — no re-queue.")
        elif next_idx < total:
            print(f"[Batch Runner] auto_queue=False; next subject is {subjects[next_idx]}.")
        else:
            print("[Batch Runner] Last subject — batch stops after this run.")

        report = self._build_report(subjects, bids_dataset, completion_check,
                                    idx + 1, total, skipped)
        status_line = f"Subject {idx + 1}/{total}: {selected}"

        return {
            "ui": {"text": [status_line]},
            "result": (subject_data, selected, idx + 1, total, report),
        }
