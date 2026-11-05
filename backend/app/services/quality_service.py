from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.filtering import matches_search, paginate


def _job_counts(repo: Any) -> Dict[str, int]:
    counts = {"queued": 0, "preparing_evidence": 0, "calling_model": 0, "validating_response": 0, "completed": 0, "failed": 0, "interrupted": 0}
    for job in (repo.state().get("ai_jobs") or {}).values():
        status = job.get("status") or "queued"
        counts[status] = counts.get(status, 0) + 1
    return counts


class QualityService:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def summary(self) -> Dict[str, Any]:
        records = self.repo.list_source_records()
        evidence = self.repo.list_evidence()
        reviews = self.repo.list_reviews()
        docs = {d["document_id"] for d in self.repo.list_documents()}

        source_completeness = []
        for source in self.repo.list_sources():
            src_records = [r for r in records if r.get("source_id") == source["source_id"]]
            fields = ("recorded_name", "specialty", "practice_name", "city", "state", "email")
            missing_counts = {f: 0 for f in fields}
            for r in src_records:
                for f in fields:
                    if not r.get(f):
                        missing_counts[f] += 1
            filled = sum(
                1 for r in src_records for f in fields if r.get(f)
            )
            total = len(src_records) * len(fields)
            source_completeness.append({
                "source_id": source["source_id"],
                "source_name": source["source_name"],
                "completeness": round(filled / total, 3) if total else 0,
                "row_count": len(src_records),
                "missing_counts": missing_counts,
            })

        missing_fields = []
        for f in ("specialty", "email", "practice_name", "city", "state"):
            rows = [r["source_record_id"] for r in records if not r.get(f)]
            missing_fields.append({"field": f, "count": len(rows), "sample_ids": rows[:10]})

        unresolved = sum(1 for r in records if r.get("resolution_status") == "unresolved")
        conflicting = sum(1 for r in reviews if r.get("case_type") == "identifier_conflict" and r.get("status") == "pending")
        pending = sum(1 for r in reviews if r.get("status") == "pending")

        inconsistent = 0
        evid_ids = {e["evidence_id"] for e in evidence}
        for e in evidence:
            if e.get("document_id") and e["document_id"] not in docs:
                inconsistent += 1
        for event in self.repo.list_events():
            if event.get("evidence_id") and event["evidence_id"] not in evid_ids:
                inconsistent += 1

        return {
            "snapshot_version": self.repo.snapshot_version(),
            "source_completeness": source_completeness,
            "missing_fields": missing_fields,
            "unresolved_records": unresolved,
            "conflicting_cases": conflicting,
            "pending_review_volume": pending,
            "inconsistent_evidence_refs": inconsistent,
            "matching_accuracy_note": (
                "Matching accuracy scores are hidden unless an answer-key scorecard is available. "
                "LLM output is a recommendation until a steward approves it."
            ),
            "ai_job_counts": _job_counts(self.repo),
            "audit_events": sorted(
                self.repo.list_audit(),
                key=lambda a: a.get("occurred_at") or a.get("created_at") or "",
                reverse=True,
            )[:50],
            "pipeline_runs": list(self.repo.state().get("demo_runs") or [])[:20],
            "upload_batches": list(self.repo.state().get("upload_batches") or [])[:20],
            "drilldowns": {
                "unresolved_href": "/sources?status=unresolved",
                "conflicts_href": "/reviews?case_type=identifier_conflict&status=pending",
                "pending_href": "/reviews?status=pending",
            },
        }

    def activity(
        self,
        *,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        doctors = {d["doctor_id"]: d for d in self.repo.list_doctors()}
        items = []
        for audit in self.repo.list_audit():
            d = doctors.get(audit.get("doctor_id") or "")
            row = {
                **audit,
                "entity": audit.get("doctor_id") or audit.get("review_id"),
                "doctor_name": d.get("preferred_name") if d else None,
                "reason": audit.get("summary"),
            }
            blob = " ".join([
                row.get("action") or "",
                row.get("summary") or "",
                row.get("actor_label") or "",
                row.get("doctor_name") or "",
                row.get("entity") or "",
            ])
            if search and not matches_search(blob, search):
                continue
            items.append(row)
        items.sort(key=lambda a: a.get("occurred_at") or "", reverse=True)
        page_items, total = paginate(items, page, page_size)
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "applied_filters": {"search": search},
            "snapshot_version": self.repo.snapshot_version(),
        }
