from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.identity.labels import source_label
from app.services.filtering import matches_search, paginate, sort_items


class PaymentService:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def list_cases(
        self,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        doctors = {d["doctor_id"]: d for d in self.repo.list_doctors()}
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        items: List[Dict[str, Any]] = []
        for review in self.repo.list_reviews():
            if review.get("case_type") != "compliance_review" and review.get("pipeline_action") != "COMPLIANCE_REVIEW":
                continue
            if status and review.get("status") != status:
                continue
            rec = records.get(review.get("source_record_id") or "") or {}
            raw = rec.get("raw") or {}
            doctor = doctors.get(review.get("doctor_id") or review.get("candidate_doctor_id") or "")
            stated_npi = None
            for nf in rec.get("npi_fields") or []:
                if nf.get("digits"):
                    stated_npi = nf.get("digits")
                    break
            row = {
                "review_id": review["review_id"],
                "payment_id": rec.get("original_transaction_id") or raw.get("payment_id"),
                "stated_npi": stated_npi or raw.get("recipient_npi"),
                "recipient_first": raw.get("recipient_first"),
                "recipient_last": raw.get("recipient_last"),
                "recipient_name": rec.get("recorded_name"),
                "proposed_doctor_id": review.get("doctor_id") or review.get("candidate_doctor_id"),
                "proposed_doctor_name": doctor.get("preferred_name") if doctor else None,
                "reason": review.get("pipeline_reason") or review.get("title"),
                "amount_usd": raw.get("amount_usd"),
                "payment_date": raw.get("payment_date") or rec.get("record_date"),
                "filed_status": raw.get("filed_status"),
                "nature_of_payment": raw.get("nature_of_payment"),
                "review_status": review.get("status"),
                "source_label": source_label("payments"),
                "evidence_ids": [f"EV-{rec.get('source_record_id')}"] if rec else [],
                "note": "Filed and reportable payment values are never changed automatically.",
            }
            blob = " ".join(str(v or "") for v in row.values())
            if search and not matches_search(blob, search):
                continue
            items.append(row)
        items = sort_items(items, "payment_date", "desc", {"payment_date", "review_id", "amount_usd"}, "review_id")
        page_items, total = paginate(items, page, page_size)
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "snapshot_version": self.repo.snapshot_version(),
            "policy": "Compliance reviewers must approve any proposed correction. Filed values are never auto-updated.",
        }
