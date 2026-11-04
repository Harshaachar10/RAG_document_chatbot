from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.repositories.csv_repository import CsvDemoRepository
from app.utils.links import is_linked_status


class DashboardService:
    def __init__(self, repo: CsvDemoRepository) -> None:
        self.repo = repo

    def _scoped_doctor_ids(
        self,
        *,
        source_id: Optional[str],
        specialty: Optional[str],
        state: Optional[str],
        review_state: Optional[str],
    ) -> Set[str]:
        doctors = self.repo.list_doctors()
        pending_doctors = {
            r.get("doctor_id")
            for r in self.repo.list_reviews()
            if r.get("status") == "pending" and r.get("doctor_id")
        }
        deferred_doctors = {
            r.get("doctor_id")
            for r in self.repo.list_reviews()
            if r.get("status") == "deferred" and r.get("doctor_id")
        }
        source_doctor_ids = None
        if source_id:
            records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
            source_doctor_ids = set()
            for link in self.repo.list_links():
                if not link.get("doctor_id"):
                    continue
                rec = records.get(link.get("source_record_id"))
                if rec and rec.get("source_id") == source_id:
                    source_doctor_ids.add(link["doctor_id"])

        ids: Set[str] = set()
        for d in doctors:
            did = d["doctor_id"]
            if specialty and d.get("specialty") != specialty:
                continue
            if state and d.get("state") != state:
                continue
            if source_doctor_ids is not None and did not in source_doctor_ids:
                continue
            if review_state == "pending" and did not in pending_doctors:
                continue
            if review_state == "deferred" and did not in deferred_doctors:
                continue
            ids.add(did)
        return ids

    def summary(
        self,
        *,
        source_id: Optional[str] = None,
        specialty: Optional[str] = None,
        state: Optional[str] = None,
        review_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        doctor_ids = self._scoped_doctor_ids(
            source_id=source_id, specialty=specialty, state=state, review_state=review_state
        )
        records = self.repo.list_source_records()
        links = self.repo.list_links()
        reviews = self.repo.list_reviews()
        sources = {s["source_id"]: s for s in self.repo.list_sources()}

        # Source filter for record KPIs counts only records from that source
        scoped_records = [
            r for r in records
            if (not source_id or r.get("source_id") == source_id)
        ]
        identity_entries = [r for r in scoped_records if r.get("record_kind") == "identity_entry"]
        eligible = identity_entries  # denominator for linked/all eligible
        accepted_links = {
            l["source_record_id"]: l
            for l in links
            if is_linked_status(l.get("link_status")) and l.get("doctor_id") in doctor_ids
        }
        linked_identity = [
            r for r in identity_entries
            if r["source_record_id"] in accepted_links
        ]

        # Consolidated duplicates: sum(max(linked identity_entry count for doctor - 1, 0))
        per_doctor_identity: Dict[str, int] = {}
        records_by_id = {r["source_record_id"]: r for r in records}
        for link in links:
            did = link.get("doctor_id")
            if not did or did not in doctor_ids or not is_linked_status(link.get("link_status")):
                continue
            rec = records_by_id.get(link.get("source_record_id"))
            if not rec or rec.get("record_kind") != "identity_entry":
                continue
            if source_id and rec.get("source_id") != source_id:
                continue
            per_doctor_identity[did] = per_doctor_identity.get(did, 0) + 1
        consolidated = sum(max(count - 1, 0) for count in per_doctor_identity.values())

        pending_reviews = [
            r for r in reviews
            if r.get("status") == "pending"
            and (not r.get("doctor_id") or r.get("doctor_id") in doctor_ids)
        ]
        deferred_reviews = [r for r in reviews if r.get("status") == "deferred"]
        proposed_change_doctors = {
            r.get("doctor_id")
            for r in reviews
            if r.get("status") == "pending"
            and r.get("case_type") in {"name_update", "address_update", "affiliation_update", "contact_update"}
            and r.get("doctor_id") in doctor_ids
        }

        filters = {
            "source_id": source_id,
            "specialty": specialty,
            "state": state,
            "review_state": review_state,
        }
        kpis = [
            {
                "key": "source_doctor_entries",
                "label": "Source Doctor Entries",
                "value": len(identity_entries),
                "secondary_value": None,
                "display": str(len(identity_entries)),
                "tooltip": "Count of source records classified as identity_entry in the selected source scope.",
                "href": "/sources",
                "filters": {"record_kind": "identity_entry", **{k: v for k, v in filters.items() if v}},
            },
            {
                "key": "golden_profiles",
                "label": "Golden Doctor Profiles",
                "value": len(doctor_ids),
                "secondary_value": None,
                "display": str(len(doctor_ids)),
                "tooltip": "Distinct active doctor IDs in the selected cohort (source filter selects doctors linked to that source).",
                "href": "/golden-records",
                "filters": {k: v for k, v in filters.items() if v},
            },
            {
                "key": "linked_records",
                "label": "Linked Records",
                "value": len(linked_identity),
                "secondary_value": len(eligible),
                "display": f"{len(linked_identity)}/{len(eligible)}",
                "tooltip": "Linked identity_entry records over all eligible identity_entry records in source scope.",
                "href": "/sources",
                "filters": {"resolution_status": "linked", **{k: v for k, v in filters.items() if v}},
            },
            {
                "key": "consolidated_duplicates",
                "label": "Consolidated Duplicate Entries",
                "value": consolidated,
                "secondary_value": None,
                "display": str(consolidated),
                "tooltip": "Additional identity entries consolidated into an existing profile in this demo. Claims, invoices and other transactions are excluded.",
                "href": "/golden-records",
                "filters": {k: v for k, v in filters.items() if v},
            },
            {
                "key": "pending_reviews",
                "label": "Pending Reviews",
                "value": len(pending_reviews),
                "secondary_value": len(deferred_reviews),
                "display": str(len(pending_reviews)),
                "tooltip": f"Pending cases in scope. Deferred counted separately ({len(deferred_reviews)}).",
                "href": "/reviews",
                "filters": {"status": "pending"},
            },
            {
                "key": "profiles_with_proposals",
                "label": "Profiles with Proposed Changes",
                "value": len(proposed_change_doctors),
                "secondary_value": None,
                "display": str(len(proposed_change_doctors)),
                "tooltip": "Distinct doctors with pending name/address/affiliation proposals.",
                "href": "/reviews",
                "filters": {"status": "pending", "case_type": "affiliation_update"},
            },
        ]

        # Priority reviews
        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        priority = sorted(
            [r for r in reviews if r.get("status") == "pending"],
            key=lambda r: (severity_rank.get(r.get("severity") or "low", 9), r.get("created_at") or ""),
        )[:8]
        doctors = {d["doctor_id"]: d for d in self.repo.list_doctors()}
        priority_rows = []
        for r in priority:
            d = doctors.get(r.get("doctor_id") or "")
            priority_rows.append({
                "review_id": r["review_id"],
                "title": r.get("title"),
                "doctor_id": r.get("doctor_id"),
                "doctor_name": d.get("preferred_name") if d else r.get("candidate_doctor_id"),
                "reason": r.get("case_type"),
                "severity": r.get("severity"),
                "status": r.get("status"),
                "created_at": r.get("created_at"),
            })

        events = sorted(self.repo.list_events(), key=lambda e: e.get("recorded_at") or "", reverse=True)[:8]
        recent_changes = []
        for e in events:
            d = doctors.get(e.get("doctor_id") or "")
            recent_changes.append({
                "event_id": e["event_id"],
                "doctor_id": e.get("doctor_id"),
                "doctor_name": d.get("preferred_name") if d else None,
                "title": e.get("title"),
                "previous_value": e.get("previous_value"),
                "new_value": e.get("new_value"),
                "date": e.get("effective_date") or e.get("document_date") or e.get("recorded_at"),
                "evidence_id": e.get("evidence_id"),
            })

        source_coverage = []
        for source in self.repo.list_sources():
            src_records = [r for r in records if r.get("source_id") == source["source_id"]]
            latest = max((r.get("record_date") or "" for r in src_records), default=None) or source.get("updated_at")
            filled = 0
            total_fields = 0
            for r in src_records:
                for field in ("recorded_name", "specialty", "practice_name", "city", "state", "email"):
                    total_fields += 1
                    if r.get(field):
                        filled += 1
            completeness = round(filled / total_fields, 3) if total_fields else 0
            source_coverage.append({
                "source_id": source["source_id"],
                "source_name": source["source_name"],
                "row_count": len(src_records),
                "latest_data_date": latest,
                "completeness": completeness,
            })

        audits = sorted(self.repo.list_audit(), key=lambda a: a.get("occurred_at") or "", reverse=True)[:8]
        recent_decisions = []
        for a in audits:
            d = doctors.get(a.get("doctor_id") or "")
            recent_decisions.append({
                "audit_id": a["audit_id"],
                "actor_label": a.get("actor_label"),
                "action": a.get("action"),
                "doctor_id": a.get("doctor_id"),
                "doctor_name": d.get("preferred_name") if d else None,
                "occurred_at": a.get("occurred_at"),
                "review_id": a.get("review_id"),
                "is_seeded": a.get("is_seeded"),
            })

        manifest = self.repo.manifest()
        dataset_updated_at = manifest.get("generated_at")
        if not dataset_updated_at:
            dated = [s.get("updated_at") for s in self.repo.list_sources() if s.get("updated_at")]
            dataset_updated_at = max(dated) if dated else None
        runs = self.repo.state().get("demo_runs") or []
        last_run = None
        completed = [r for r in runs if r.get("status") == "completed"]
        if completed:
            last_run = max(completed, key=lambda r: r.get("updated_at") or "")
        return {
            "dataset_updated_at": dataset_updated_at,
            "last_simulated_run_at": (last_run or {}).get("updated_at"),
            "snapshot_version": self.repo.snapshot_version(),
            "applied_filters": filters,
            "kpis": kpis,
            "priority_reviews": priority_rows,
            "recent_changes": recent_changes,
            "source_coverage": source_coverage,
            "recent_decisions": recent_decisions,
        }

    def source_breakdown(
        self,
        *,
        source_id: Optional[str] = None,
        specialty: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        records = self.repo.list_source_records()
        rows = []
        statuses = ["linked", "review_required", "unresolved", "identifier_conflict", "duplicate_ingestion"]
        for source in self.repo.list_sources():
            if source_id and source["source_id"] != source_id:
                continue
            src_records = [r for r in records if r.get("source_id") == source["source_id"]]
            # specialty/state filter applies to records themselves for chart drill coherence
            if specialty:
                src_records = [r for r in src_records if r.get("specialty") == specialty]
            if state:
                src_records = [r for r in src_records if r.get("state") == state]
            segments = []
            for status in statuses:
                segments.append({
                    "status": status,
                    "count": sum(1 for r in src_records if (r.get("resolution_status") or "") == status),
                })
            rows.append({
                "source_id": source["source_id"],
                "source_name": source["source_name"],
                "segments": segments,
            })
        total = sum(seg["count"] for row in rows for seg in row["segments"])
        return {
            "rows": rows,
            "applied_filters": {"source_id": source_id, "specialty": specialty, "state": state},
            "text_summary": f"Resolution status counts across {len(rows)} sources ({total} scoped source records).",
        }
