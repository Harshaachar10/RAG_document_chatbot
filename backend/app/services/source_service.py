from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationAppError
from app.repositories.csv_repository import CsvDemoRepository
from app.services.filtering import matches_search, paginate, sort_items
from app.utils.csv_io import assert_safe_id


class SourceService:
    def __init__(self, repo: CsvDemoRepository) -> None:
        self.repo = repo

    def list_sources(self) -> Dict[str, Any]:
        records = self.repo.list_source_records()
        items = []
        for source in self.repo.list_sources():
            src_records = [r for r in records if r.get("source_id") == source["source_id"]]
            counts = {
                "linked": 0,
                "pending": 0,
                "unresolved": 0,
                "review_required": 0,
                "identifier_conflict": 0,
            }
            for r in src_records:
                status = r.get("resolution_status") or ""
                if status == "linked":
                    counts["linked"] += 1
                elif status == "unresolved":
                    counts["unresolved"] += 1
                elif status == "review_required":
                    counts["review_required"] += 1
                    counts["pending"] += 1
                elif status == "identifier_conflict":
                    counts["identifier_conflict"] += 1
                    counts["pending"] += 1
            filled = 0
            total_fields = 0
            for r in src_records:
                for field in ("recorded_name", "specialty", "practice_name", "city", "state"):
                    total_fields += 1
                    if r.get(field):
                        filled += 1
            latest = max((r.get("record_date") or "" for r in src_records), default=None)
            items.append({
                **source,
                "row_count": len(src_records),
                "linked_count": counts["linked"],
                "pending_count": counts["pending"],
                "unresolved_count": counts["unresolved"],
                "review_required_count": counts["review_required"],
                "identifier_conflict_count": counts["identifier_conflict"],
                "completeness": round(filled / total_fields, 3) if total_fields else None,
                "latest_data_date": latest or source.get("updated_at"),
            })
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
