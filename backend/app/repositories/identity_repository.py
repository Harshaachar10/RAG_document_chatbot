from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import Settings
from app.identity.pipeline import run_identity_pipeline
from app.identity.project import project_pipeline
from app.repositories.runtime_store import RuntimeStore
from app.utils.csv_io import resolve_under


class IdentityRepository:
    """Identity-resolution repository. Source CSVs stay immutable; overlays in RuntimeStore."""

    def __init__(self, settings: Settings, runtime: RuntimeStore) -> None:
        self.settings = settings
        self.runtime = runtime
        self._documents_cache: Dict[str, Dict[str, Any]] = {}
        self._document_blocks: Dict[str, List[Dict[str, Any]]] = {}
        self._recommendations: Dict[str, Any] = {}
        self._baseline_run: Dict[str, Any] = {}
        self._manifest: Dict[str, Any] = {
            "name": "historical-identity-resolution",
            "schema": "identity_v1",
            "sources": sorted(p.name for p in self.data_path.glob("*.csv")),
        }
        self._fingerprint = self._compute_fingerprint()
        self._pipeline_result = run_identity_pipeline(self.data_path)
        self._projected = project_pipeline(self._pipeline_result)
        self._sources = list(self._projected.get("sources_meta") or [])
        self.runtime.ensure_initialized(
            self.build_seed_state,
            dataset_fingerprint=self._fingerprint,
        )

    @property
    def data_path(self) -> Path:
        # Prefer settings.csv_path; fall back to backend/data
        path = self.settings.csv_path
        if path.exists() and any(path.glob("0*.csv")):
            return path
        fallback = self.settings.backend_root / "data"
        return fallback

    def _compute_fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(b"identity-schema-v4")
        root = self.data_path
        if not root.exists():
            return "empty"
        for path in sorted(root.glob("*.csv")):
            h.update(path.name.encode("utf-8"))
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0")
        return h.hexdigest()[:32]

    def build_seed_state(self) -> Dict[str, Any]:
        state = dict(self._projected)
        state["dataset_fingerprint"] = self._fingerprint
        return state

    def pipeline_result(self) -> Dict[str, Any]:
        return self._pipeline_result

    def dataset_fingerprint(self) -> str:
        return self._fingerprint

    def row_counts(self) -> Dict[str, int]:
        counts = dict((self._pipeline_result.get("counts") or {}))
        # flatten nested actions
        actions = counts.pop("actions", None)
        if isinstance(actions, dict):
            for k, v in actions.items():
                counts[f"action_{k}"] = v
        return {k: int(v) for k, v in counts.items() if isinstance(v, (int, float))}

    def state(self) -> Dict[str, Any]:
        return self.runtime.get()

    def snapshot_version(self) -> int:
        return int(self.state().get("snapshot_version") or 1)

    def manifest(self) -> Dict[str, Any]:
        return dict(self._manifest)

    def list_sources(self) -> List[Dict[str, Any]]:
        # Prefer live projected sources; allow runtime overlay later
        meta = self.state().get("sources_meta")
        if meta:
            return [dict(s) for s in meta]
        return [dict(s) for s in self._sources]

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        return next((dict(s) for s in self.list_sources() if s["source_id"] == source_id), None)

    def list_doctors(self) -> List[Dict[str, Any]]:
        return list(self.state()["doctors"].values())

    def get_doctor(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        return self.state()["doctors"].get(doctor_id)

    def list_aliases(self, doctor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self.state()["aliases"].values())
        if doctor_id:
            rows = [r for r in rows if r.get("doctor_id") == doctor_id]
        return rows

    def list_affiliations(self, doctor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self.state()["affiliations"].values())
        if doctor_id:
            rows = [r for r in rows if r.get("doctor_id") == doctor_id]
        return rows

    def list_events(self, doctor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self.state()["events"].values())
        if doctor_id:
            rows = [r for r in rows if r.get("doctor_id") == doctor_id]
        return rows

    def list_link_history(self, doctor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self.state().get("link_history", {}).values())
        if doctor_id:
            rows = [r for r in rows if r.get("doctor_id") == doctor_id]
        return rows

    def list_constraints(self) -> List[Dict[str, Any]]:
        return list(self.state().get("identity_constraints", {}).values())

    def list_source_records(self) -> List[Dict[str, Any]]:
        return list(self.state()["source_records"].values())

    def get_source_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        return self.state()["source_records"].get(record_id)

    def list_links(self) -> List[Dict[str, Any]]:
        return list(self.state()["source_links"].values())

    def list_reviews(self) -> List[Dict[str, Any]]:
        return list(self.state()["reviews"].values())

    def get_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        return self.state()["reviews"].get(review_id)

    def list_candidates(self, review_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self.state().get("review_candidates") or [])
        if review_id:
            rows = [r for r in rows if r.get("review_id") == review_id]
        return rows

    def list_evidence(self) -> List[Dict[str, Any]]:
        return list(self.state()["evidence"].values())

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        return self.state()["evidence"].get(evidence_id)

    def list_documents(self) -> List[Dict[str, Any]]:
        return list(self.state().get("documents") or [])

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        return next((dict(d) for d in self.list_documents() if d.get("document_id") == document_id), None)

    def document_pages(self, document_id: str, version: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def get_document_content(self, document_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None

    def list_observations(self, doctor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self.state()["observations"].values())
        if doctor_id:
            rows = [r for r in rows if r.get("doctor_id") == doctor_id]
        return rows

    def list_provenance(self, doctor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self.state()["field_provenance"].values())
        if doctor_id:
            rows = [r for r in rows if r.get("doctor_id") == doctor_id]
        return rows

    def list_audit(self) -> List[Dict[str, Any]]:
        return list(self.state()["audit_events"].values())

    def get_recommendation(self, key: str) -> Optional[Dict[str, Any]]:
        return self._recommendations.get(key)

    def baseline_run(self) -> Dict[str, Any]:
        return dict(self._baseline_run)

    def resolve_data_file(self, relative: str) -> Path:
        return resolve_under(self.data_path, relative)

    def rerun_pipeline(self) -> Dict[str, Any]:
        """Force a fresh pipeline run and replace entity tables; preserve runs/AI overlays."""
        previous = self.runtime.get()
        preserve_keys = ("demo_runs", "ai_jobs", "ai_analyses", "ai_cache", "idempotency", "decision_log")
        preserved = {k: previous.get(k) for k in preserve_keys if k in previous}

        self._fingerprint = self._compute_fingerprint()
        self._pipeline_result = run_identity_pipeline(self.data_path)
        self._projected = project_pipeline(self._pipeline_result)
        self._sources = list(self._projected.get("sources_meta") or [])
        seed = self.build_seed_state()
        seed["initialized_at"] = seed.get("pipeline_run", {}).get("finished_at")
        seed["snapshot_version"] = int(previous.get("snapshot_version") or 1) + 1
        for k, v in preserved.items():
            seed[k] = v
        if previous.get("source_profiles"):
            seed["source_profiles"] = previous.get("source_profiles")
        seed["pipeline_cleared"] = False
        self.runtime.replace(seed)
        return self._pipeline_result.get("counts") or {}

    def reset_demo(self) -> Dict[str, Any]:
        """Clear pipeline output. Source files and approved profiles stay."""
        previous = self.runtime.get()
        profiles = previous.get("source_profiles") or []
        sources = previous.get("sources_meta") or []

        def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in list(state.items()):
                if key in {"source_profiles", "sources_meta", "dataset_fingerprint", "idempotency"}:
                    continue
                if isinstance(value, dict):
                    state[key] = {}
                elif isinstance(value, list):
                    state[key] = []
            state["source_profiles"] = profiles
            state["sources_meta"] = sources
            state["pipeline_cleared"] = True
            state["doctors"] = {}
            state["source_records"] = {}
            state["reviews"] = {}
            state["match_decisions"] = []
            state["pipeline_metrics"] = {}
            state["pipeline_counts"] = {}
            state["search_quality"] = {}
            state["cleanup_rounds"] = []
            return {"cleared": True, "profiles_kept": len(profiles)}

        result = self.runtime.mutate(mutator)
        cache = self.settings.runtime_path / "embedding_cache.json"
        if cache.exists():
            cache.unlink()
        return result
