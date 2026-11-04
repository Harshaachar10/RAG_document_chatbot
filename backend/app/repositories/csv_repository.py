from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import Settings
from app.repositories.dataset_loader import LoadedDataset, load_dataset
from app.repositories.runtime_store import RuntimeStore
from app.utils.csv_io import resolve_under


class CsvDemoRepository:
    """CSV-backed repository. Source files stay immutable; overlays live in RuntimeStore."""

    def __init__(self, settings: Settings, runtime: RuntimeStore) -> None:
        self.settings = settings
        self.runtime = runtime
        self._documents_cache: Dict[str, Dict[str, Any]] = {}
        self._recommendations: Dict[str, Any] = {}
        self._baseline_run: Dict[str, Any] = {}
        self._manifest: Dict[str, Any] = {}
        self._loaded: LoadedDataset = load_dataset(settings.csv_path)
        self._immutable: Dict[str, List[Dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in self._loaded.tables.items()
        }
        self._index_documents()
        self._load_optional_mocks()
        self.runtime.ensure_initialized(
            self.build_seed_state,
            dataset_fingerprint=self._loaded.fingerprint,
        )

    def _index_documents(self) -> None:
        blocks = self._immutable.get("document_content") or []
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for block in blocks:
            grouped.setdefault(str(block["document_id"]), []).append(dict(block))
        self._document_blocks = grouped

    def _load_optional_mocks(self) -> None:
        """Legacy mock files are not model inputs. They only back the processing replay."""
        rec_path = self.settings.mock_path / "recommendations.json"
        if rec_path.exists():
            self._recommendations = json.loads(rec_path.read_text(encoding="utf-8"))
        baseline_path = self.settings.mock_path / "processing_baseline.json"
        if baseline_path.exists():
            self._baseline_run = json.loads(baseline_path.read_text(encoding="utf-8"))
        if self.settings.manifest_path.exists():
            self._manifest = json.loads(self.settings.manifest_path.read_text(encoding="utf-8"))

    def build_seed_state(self) -> Dict[str, Any]:
        def keyed(table: str, key: str) -> Dict[str, Dict[str, Any]]:
            return {str(row[key]): dict(row) for row in self._immutable.get(table, [])}

        return {
            "snapshot_version": 1,
            "dataset_fingerprint": self._loaded.fingerprint,
            "dataset_directory": self._loaded.csv_directory,
            "doctors": keyed("doctors", "doctor_id"),
            "affiliations": keyed("affiliations", "affiliation_id"),
            "aliases": keyed("aliases", "alias_id"),
            "source_records": keyed("source_records", "source_record_id"),
            "source_links": keyed("source_links", "link_id"),
            "reviews": keyed("reviews", "review_id"),
            "review_candidates": [dict(row) for row in self._immutable.get("review_candidates", [])],
            "events": keyed("events", "event_id"),
            "observations": keyed("observations", "observation_id"),
            "field_provenance": keyed("field_provenance", "provenance_id"),
            "audit_events": keyed("audit_events", "audit_id"),
            "evidence": keyed("evidence", "evidence_id"),
            "link_history": keyed("link_history", "change_id"),
            "identity_constraints": keyed("identity_constraints", "constraint_id"),
            "idempotency": {},
            "demo_runs": [dict(self._baseline_run)] if self._baseline_run else [],
            "decision_log": [],
            "ai_jobs": {},
            "ai_analyses": {},
            "ai_cache": {},
        }

    def dataset_fingerprint(self) -> str:
        return self._loaded.fingerprint

    def row_counts(self) -> Dict[str, int]:
        return dict(self._loaded.row_counts)

    def state(self) -> Dict[str, Any]:
        return self.runtime.get()

    def snapshot_version(self) -> int:
        return int(self.state().get("snapshot_version") or 1)

    def manifest(self) -> Dict[str, Any]:
        return dict(self._manifest)

    def list_sources(self) -> List[Dict[str, Any]]:
        return [dict(s) for s in self._immutable.get("sources", [])]

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        return next((dict(s) for s in self._immutable.get("sources", []) if s["source_id"] == source_id), None)

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
        return [dict(d) for d in self._immutable.get("documents", [])]

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        return next(
            (dict(d) for d in self._immutable.get("documents", []) if d["document_id"] == document_id),
            None,
        )

    def document_pages(self, document_id: str, version: Optional[str] = None) -> List[Dict[str, Any]]:
        meta = self.get_document(document_id)
        if not meta:
            return []
        selected = str(version if version is not None else meta.get("version"))
        blocks = [
            block for block in self._document_blocks.get(document_id, [])
            if str(block.get("document_version")) == selected
        ]
        blocks.sort(key=lambda block: (int(block.get("page_number") or 0), int(block.get("block_order") or 0)))
        pages: List[Dict[str, Any]] = []
        for block in blocks:
            page_number = int(block.get("page_number") or 0)
            if not pages or pages[-1]["page_number"] != page_number:
                pages.append({
                    "page_number": page_number,
                    "label": f"Page {page_number}",
                    "blocks": [],
                })
            pages[-1]["blocks"].append({
                "block_id": block.get("block_id"),
                "kind": block.get("block_type") or "paragraph",
                "text": block.get("text") or "",
                "highlightable": True,
            })
        return pages

    def get_document_content(self, document_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.get_document(document_id):
            return None
        pages = self.document_pages(document_id, version)
        if version is not None and not pages:
            return None
        return {"document_id": document_id, "version": str(version or ""), "pages": pages}

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
        """Legacy prepared text. Not used as a live model result."""
        return self._recommendations.get(key)

    def baseline_run(self) -> Dict[str, Any]:
        return dict(self._baseline_run)

    def resolve_data_file(self, relative: str) -> Path:
        return resolve_under(self.settings.csv_path, relative)
