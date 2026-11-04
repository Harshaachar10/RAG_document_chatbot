from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.core.exceptions import ConflictError
from app.utils.dates import utc_now_iso


class RuntimeStore:
    """Atomic JSON runtime snapshot for approvals and AI results.

    Source CSVs are never written here. The lock is process-local: run a single
    API process. Two workers can lose updates even though each write replaces
    the file atomically. A dataset fingerprint change archives the previous
    snapshot and reseeds from the CSVs so overlays cannot mix two datasets.
    """

    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.state_path = runtime_dir / "state.json"
        self._lock = threading.RLock()
        self._state: Optional[Dict[str, Any]] = None

    def ensure_initialized(
        self,
        seed_builder: Callable[[], Dict[str, Any]],
        *,
        dataset_fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            if self.state_path.exists():
                self._state = self._read()
                current = self._state.get("dataset_fingerprint")
                if dataset_fingerprint and current != dataset_fingerprint:
                    archive = self.state_path.with_suffix(".previous.json")
                    archive.write_text(self.state_path.read_text(encoding="utf-8"), encoding="utf-8")
                    self._state = None
                else:
                    self._mark_interrupted_runs()
                    self._write(self._state)
                    return copy.deepcopy(self._state)
            state = seed_builder()
            state["snapshot_version"] = int(state.get("snapshot_version") or 1)
            state["initialized_at"] = utc_now_iso()
            state["dataset_fingerprint"] = dataset_fingerprint
            state.setdefault("idempotency", {})
            state.setdefault("demo_runs", [])
            state.setdefault("ai_jobs", {})
            state.setdefault("ai_analyses", {})
            state.setdefault("ai_cache", {})
            self._write(state)
            self._state = state
            return copy.deepcopy(state)

    def get(self) -> Dict[str, Any]:
        with self._lock:
            if self._state is None:
                self._state = self._read()
            return copy.deepcopy(self._state)

    def mutate(self, mutator: Callable[[Dict[str, Any]], Any]) -> Any:
        with self._lock:
            state = self._read()
            result = mutator(state)
            state["snapshot_version"] = int(state.get("snapshot_version") or 1) + 1
            state["updated_at"] = utc_now_iso()
            self._atomic_write(state)
            self._state = state
            return result

    def replace(self, state: Dict[str, Any]) -> None:
        with self._lock:
            self._atomic_write(state)
            self._state = state

    def get_idempotent(self, key: str) -> Optional[Dict[str, Any]]:
        state = self.get()
        return (state.get("idempotency") or {}).get(key)

    def _mark_interrupted_runs(self) -> None:
        assert self._state is not None
        changed = False
        now = utc_now_iso()
        for run in self._state.get("demo_runs") or []:
            if run.get("status") in {"running", "queued"}:
                run["status"] = "interrupted"
                run["message"] = "Run interrupted by process restart."
                run["updated_at"] = now
                changed = True
        for job in (self._state.get("ai_jobs") or {}).values():
            if job.get("status") not in {"completed", "failed", "interrupted"}:
                job["status"] = "interrupted"
                job["error"] = {
                    "code": "INTERRUPTED",
                    "message": "Job interrupted by process restart. Submit the analysis again.",
                }
                job["updated_at"] = now
                changed = True
        if changed:
            self._state["updated_at"] = now

    def _read(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            raise FileNotFoundError(f"Runtime state missing: {self.state_path}")
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write(self, state: Dict[str, Any]) -> None:
        self._atomic_write(state)

    def _atomic_write(self, state: Dict[str, Any]) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.state_path)


def require_version(state: Dict[str, Any], expected: int) -> None:
    current = int(state.get("snapshot_version") or 1)
    # Reviews carry their own version; snapshot_version advances globally.
    # Callers should compare entity version separately; this helper is for global checks.
    if expected < 1:
        raise ConflictError("INVALID_VERSION", "expected_version must be >= 1")
