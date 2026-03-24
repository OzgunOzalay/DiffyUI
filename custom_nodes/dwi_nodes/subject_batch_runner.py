"""
Subject Batch Runner Node - Automatically processes all subjects sequentially.

Maintains state in ~/.diffyui/batch_state.json and re-queues the ComfyUI
workflow via the HTTP API after each subject completes, advancing the index
until all subjects are processed.
"""

import json
import hashlib
import threading
import time
from pathlib import Path
from typing import Optional


_STATE_DIR = Path.home() / ".diffyui"
_STATE_FILE = _STATE_DIR / "batch_state.json"


class SubjectBatchRunnerNode:
    """
    Batch runner that processes all subjects sequentially without manual intervention.

    Drop-in replacement for SubjectSelector/SubjectIterator when you want to run
    the full pipeline on every subject automatically.  On each workflow execution
    it outputs the files for the *current* subject, saves the incremented index to
    disk, then re-queues the same workflow so the next subject is picked up
    automatically.  The batch stops (no re-queue) after the last subject.

    State resets automatically when the subject list changes.  Toggle
    ``reset_batch`` to True to force a restart from subject 0.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "all_subject_ids": ("STRING", {
                    "default": "",
                    "tooltip": "Comma-separated subject IDs from BIDS Loader",
                }),
                "ap_phase_dwi":  ("STRING", {"default": ""}),
                "ap_phase_bvec": ("STRING", {"default": ""}),
                "ap_phase_bval": ("STRING", {"default": ""}),
                "pa_phase_dwi":  ("STRING", {"default": ""}),
                "pa_phase_bvec": ("STRING", {"default": ""}),
                "pa_phase_bval": ("STRING", {"default": ""}),
                "t1w_nii":       ("STRING", {"default": ""}),
            },
            "optional": {
                "auto_queue": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Re-queue workflow automatically after each subject",
                }),
                "reset_batch": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Toggle to True to restart the batch from subject 0",
                }),
            },
        }

    RETURN_TYPES = (
        "STRING",  # subject_id
        "STRING",  # ap_phase_dwi
        "STRING",  # ap_phase_bvec
        "STRING",  # ap_phase_bval
        "STRING",  # pa_phase_dwi
        "STRING",  # pa_phase_bvec
        "STRING",  # pa_phase_bval
        "STRING",  # t1w_nii
        "INT",     # current_index  (1-based, for display)
        "INT",     # total_subjects
    )
    RETURN_NAMES = (
        "subject_id",
        "ap_phase_dwi",
        "ap_phase_bvec",
        "ap_phase_bval",
        "pa_phase_dwi",
        "pa_phase_bvec",
        "pa_phase_bval",
        "t1w_nii",
        "current_index",
        "total_subjects",
    )
    FUNCTION = "run_batch"
    CATEGORY = "DiffyUI/Batch"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Sequentially processes all subjects. Saves state between executions and "
        "re-queues the workflow automatically until every subject is done."
    )

    # Always re-execute so ComfyUI never serves a cached result.
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _subjects_hash(subjects: list) -> str:
        return hashlib.md5(",".join(subjects).encode()).hexdigest()

    @staticmethod
    def _load_state() -> Optional[dict]:
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
    # File filtering (same logic as SubjectSelectorNode)
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_files(file_list, subject: str) -> str:
        if not file_list:
            return ""
        if isinstance(file_list, list):
            parts = [str(p).strip() for p in file_list if str(p).strip()]
        else:
            s = str(file_list).strip()
            if not s:
                return ""
            parts = [p.strip() for p in s.split(",") if p.strip()]
        filtered = [f for f in parts if subject in Path(f).name]
        return ",".join(filtered)

    # ------------------------------------------------------------------
    # Re-queue mechanism
    # ------------------------------------------------------------------

    def _requeue(self) -> None:
        """
        Grab the currently-running prompt from /queue and re-POST it so the
        workflow executes again once the current run finishes.  Reading from
        /queue (not /history) is critical — /history only has completed runs,
        so it won't contain the still-executing workflow.
        """
        def _do():
            time.sleep(1.0)
            try:
                import requests
                queue = requests.get(
                    "http://127.0.0.1:8188/queue", timeout=5
                ).json()
                running = queue.get("queue_running", [])
                if not running:
                    print("[Batch Runner] No running prompt found — cannot re-queue.")
                    return
                # Each entry: [number, prompt_id, prompt, extra_data, outputs_to_execute]
                entry = running[0]
                payload = {
                    "prompt": entry[2],
                    "extra_data": entry[3] if len(entry) > 3 else {},
                    "client_id": "",
                }
                requests.post(
                    "http://127.0.0.1:8188/prompt", json=payload, timeout=5
                )
                print("[Batch Runner] Re-queued workflow for next subject.")
            except Exception as exc:
                print(f"[Batch Runner] Re-queue failed: {exc}")

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------

    def run_batch(
        self,
        all_subject_ids: str,
        ap_phase_dwi: str = "",
        ap_phase_bvec: str = "",
        ap_phase_bval: str = "",
        pa_phase_dwi: str = "",
        pa_phase_bvec: str = "",
        pa_phase_bval: str = "",
        t1w_nii: str = "",
        auto_queue: bool = True,
        reset_batch: bool = False,
    ):
        # Parse subject list
        if isinstance(all_subject_ids, list):
            subjects = [str(s).strip() for s in all_subject_ids if str(s).strip()]
        else:
            subjects = [s.strip() for s in str(all_subject_ids).split(",") if s.strip()]

        if not subjects:
            raise ValueError("[Batch Runner] all_subject_ids is empty.")

        total = len(subjects)
        subj_hash = self._subjects_hash(subjects)

        # Determine current index
        state = self._load_state()
        if reset_batch or state is None or state.get("subjects_hash") != subj_hash:
            idx = 0
            print(f"[Batch Runner] Starting new batch — {total} subjects.")
        else:
            idx = state.get("idx", 0)

        # Batch already finished (e.g. workflow was manually re-run after completion)
        if idx >= total:
            print(f"[Batch Runner] Batch already complete ({total}/{total}). "
                  "Toggle reset_batch to restart.")
            selected = subjects[-1]
            return self._make_result(
                selected, ap_phase_dwi, ap_phase_bvec, ap_phase_bval,
                pa_phase_dwi, pa_phase_bvec, pa_phase_bval, t1w_nii,
                total, total,
            )

        selected = subjects[idx]
        print(f"[Batch Runner] Subject {idx + 1}/{total}: {selected}")

        # Persist next index before downstream processing starts
        self._save_state({
            "idx": idx + 1,
            "total": total,
            "subjects_hash": subj_hash,
            "current_subject": selected,
            "done": (idx + 1 >= total),
        })

        # Schedule re-queue unless this is the last subject
        if auto_queue and idx + 1 < total:
            self._requeue()
        elif idx + 1 >= total:
            print(f"[Batch Runner] Last subject — batch will stop after this run.")

        result = self._make_result(
            selected, ap_phase_dwi, ap_phase_bvec, ap_phase_bval,
            pa_phase_dwi, pa_phase_bvec, pa_phase_bval, t1w_nii,
            idx + 1, total,
        )

        status = f"Subject {idx + 1}/{total}: {selected}"
        return {"ui": {"text": [status]}, "result": result}

    def _make_result(
        self, selected,
        ap_phase_dwi, ap_phase_bvec, ap_phase_bval,
        pa_phase_dwi, pa_phase_bvec, pa_phase_bval,
        t1w_nii, current_index, total,
    ):
        f = self._filter_files
        return (
            selected,
            f(ap_phase_dwi,  selected),
            f(ap_phase_bvec, selected),
            f(ap_phase_bval, selected),
            f(pa_phase_dwi,  selected),
            f(pa_phase_bvec, selected),
            f(pa_phase_bval, selected),
            f(t1w_nii,       selected),
            current_index,
            total,
        )
