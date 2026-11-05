from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.settings import Settings
from app.utils.dates import utc_now_iso
from app.utils.links import is_linked_status


STEPS = [
    ("ingest", "Ingest heterogeneous source CSVs"),
    ("standardize", "Standardize names, phones, dates, specialties"),
    ("npi_check", "Validate NPIs and look up NPPES reference"),
    ("candidates", "Block candidate pairs"),
    ("score", "Score candidates with explainable weights"),
    ("route", "Apply hard stops and route decisions"),
    ("golden", "Assemble golden records"),
    ("complete", "Complete"),
]


class RunService:
    def __init__(self, repo: Any, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings
        self._threads: Dict[str, threading.Thread] = {}

    def list_runs(self) -> Dict[str, Any]:
        runs = list(self.repo.state().get("demo_runs") or [])
        runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
        return {
            "items": runs,
            "total": len(runs),
            "page": 1,
            "page_size": len(runs) or 25,
            "applied_filters": {},
            "snapshot_version": self.repo.snapshot_version(),
        }

    def get_run(self, run_id: str) -> Dict[str, Any]:
        for run in self.repo.state().get("demo_runs") or []:
            if run.get("run_id") == run_id:
                return run
        raise NotFoundError(f"Pipeline run {run_id} not found")

    def start_run(self) -> Dict[str, Any]:
        counts = {
            "doctors": len(self.repo.list_doctors()),
            "source_records": len(self.repo.list_source_records()),
            "reviews": len(self.repo.list_reviews()),
            "linked_records": sum(
                1 for l in self.repo.list_links() if is_linked_status(l.get("link_status"))
            ),
            "pending_reviews": sum(1 for r in self.repo.list_reviews() if r.get("status") == "pending"),
        }
        run_id = f"ID-RUN-{uuid.uuid4().hex[:6].upper()}"
        now = utc_now_iso()
        run = {
            "run_id": run_id,
            "mode": "identity_pipeline",
            "status": "running",
            "current_step": STEPS[0][0],
            "completed_steps": 0,
            "total_steps": len(STEPS),
            "progress_percent": 0,
            "message": "Running historical identity resolution pipeline on source CSVs.",
            "started_at": now,
            "updated_at": now,
            "result_url": None,
            "errors": [],
            "step_labels": [label for _, label in STEPS],
            "result_counts": counts,
        }

        def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
            state.setdefault("demo_runs", []).append(run)
            return run

        created = self.repo.runtime.mutate(mutator)
        thread = threading.Thread(target=self._advance, args=(run_id,), daemon=True)
        self._threads[run_id] = thread
        thread.start()
        return created

    def _advance(self, run_id: str) -> None:
        delay = max(0, int(self.settings.demo_run_step_delay_ms)) / 1000.0
        pipeline_counts: Dict[str, Any] = {}
        for idx, (step_key, label) in enumerate(STEPS):
            time.sleep(delay)
            if step_key == "golden":
                try:
                    if hasattr(self.repo, "rerun_pipeline"):
                        pipeline_counts = self.repo.rerun_pipeline() or {}
                except Exception as exc:  # noqa: BLE001
                    def fail(state: Dict[str, Any], err=str(exc)) -> None:
                        for run in state.get("demo_runs") or []:
                            if run.get("run_id") == run_id:
                                run["status"] = "failed"
                                run["errors"] = [err]
                                run["updated_at"] = utc_now_iso()
                                break
                    self.repo.runtime.mutate(fail)
                    return

            def mutator(state: Dict[str, Any], i=idx, key=step_key, lbl=label) -> None:
                for run in state.get("demo_runs") or []:
                    if run.get("run_id") != run_id:
                        continue
                    if run.get("status") == "interrupted":
                        return
                    run["current_step"] = key
                    run["completed_steps"] = i + 1
                    run["progress_percent"] = int(round(100 * (i + 1) / len(STEPS)))
                    run["message"] = f"{lbl}."
                    run["updated_at"] = utc_now_iso()
                    if pipeline_counts:
                        run["result_counts"] = {
                            **(run.get("result_counts") or {}),
                            **{k: v for k, v in pipeline_counts.items() if isinstance(v, (int, float))},
                        }
                    if i == len(STEPS) - 1:
                        run["status"] = "completed"
                        run["result_url"] = "/golden-records"
                        run["message"] = "Identity pipeline complete. Golden records and review queues refreshed."
                    break

            try:
                self.repo.runtime.mutate(mutator)
            except Exception as exc:  # noqa: BLE001
                def fail(state: Dict[str, Any], err=str(exc)) -> None:
                    for run in state.get("demo_runs") or []:
                        if run.get("run_id") == run_id:
                            run["status"] = "failed"
                            run["errors"] = [err]
                            run["updated_at"] = utc_now_iso()
                            break
                self.repo.runtime.mutate(fail)
                return
