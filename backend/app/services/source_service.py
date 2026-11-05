from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationAppError
from app.services.filtering import matches_search, paginate, sort_items
from app.utils.csv_io import assert_safe_id


class SourceService:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def list_sources(self) -> Dict[str, Any]:
        from app.services.source_metrics import enrich_source_metrics

        items = enrich_source_metrics(self.repo)
        for item in items:
            item["linked_count"] = item.get("resolved") or 0
            item["pending_count"] = item.get("in_review") or 0
            item["unresolved_count"] = item.get("unmatched") or 0
            item["review_required_count"] = item.get("in_review") or 0
            item["identifier_conflict_count"] = item.get("npi_wrong") or 0
            item["latest_data_date"] = item.get("latest_valid_date")
        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "page_size": len(items) or 25,
            "applied_filters": {},
            "snapshot_version": self.repo.snapshot_version(),
        }

    def list_records(
        self,
        source_id: str,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        record_kind: Optional[str] = None,
        sort_by: str = "record_date",
        sort_direction: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        assert_safe_id(source_id, "source_id")
        if not self.repo.get_source(source_id):
            raise NotFoundError(f"Source {source_id} not found")
        links = {l["source_record_id"]: l for l in self.repo.list_links()}
        doctors = {d["doctor_id"]: d for d in self.repo.list_doctors()}
        items = []
        for rec in self.repo.list_source_records():
            if rec.get("source_id") != source_id:
                continue
            if status and rec.get("resolution_status") != status:
                continue
            if record_kind and rec.get("record_kind") != record_kind:
                continue
            blob = " ".join([
                rec.get("recorded_name") or "",
                rec.get("source_record_id") or "",
                rec.get("practice_name") or "",
            ])
            if search and not matches_search(blob, search):
                continue
            link = links.get(rec["source_record_id"])
            did = link.get("doctor_id") if link else None
            items.append({
                **rec,
                "link_status": link.get("link_status") if link else None,
                "doctor_id": did,
                "doctor_name": doctors.get(did or "", {}).get("preferred_name"),
            })
        allow = {"record_date", "recorded_name", "resolution_status", "source_record_id", "practice_name"}
        items = sort_items(items, sort_by, sort_direction, allow, "source_record_id")
        page_items, total = paginate(items, page, page_size)
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "applied_filters": {
                "source_id": source_id, "search": search, "status": status,
                "record_kind": record_kind, "sort_by": sort_by, "sort_direction": sort_direction,
            },
            "snapshot_version": self.repo.snapshot_version(),
        }

    def get_record(self, record_id: str) -> Dict[str, Any]:
        assert_safe_id(record_id, "record_id")
        rec = self.repo.get_source_record(record_id)
        if not rec:
            raise NotFoundError(f"Source record {record_id} not found")
        link = next((l for l in self.repo.list_links() if l.get("source_record_id") == record_id), None)
        evid = [e for e in self.repo.list_evidence() if e.get("source_record_id") == record_id]
        source = self.repo.get_source(rec.get("source_id") or "")
        return {
            **rec,
            "source_name": source.get("source_name") if source else None,
            "link": link,
            "evidence": evid,
            "submitted_by": rec.get("submitted_by") or "Not recorded",
            "submitted_to": rec.get("submitted_to") or "Not recorded",
        }
