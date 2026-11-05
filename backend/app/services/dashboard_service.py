from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.identity.labels import case_label, risk_rank, source_label
from app.utils.links import is_linked_status

# NPPES + legacy master are reference/master baselines — not "source doctor entries"
NON_SOURCE_ENTRY_KEYS = frozenset({"nppes", "legacy_master"})


class DashboardService:
    def __init__(self, repo: Any) -> None:
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

    def _npi_issue_buckets(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        buckets = {"group": 0, "invalid": 0, "deactivated": 0, "mismatch": 0}
        for rec in records:
            for lookup in rec.get("npi_lookups") or []:
                status = lookup.get("status") or ""
                if status in {"luhn_fail", "invalid_format", "placeholder"}:
                    buckets["invalid"] += 1
                elif status == "deactivated":
                    buckets["deactivated"] += 1
                elif status == "not_in_reference":
                    buckets["mismatch"] += 1
            for flag in rec.get("record_flags") or []:
                code = (flag.get("code") or "").upper()
                if "GROUP" in code or "ORG_ENTITY" in code:
                    buckets["group"] += 1
            for nf in rec.get("npi_fields") or []:
                # Entity-type group NPIs are surfaced via hard stops on NPPES entity 2
                if nf.get("status") == "valid" and (rec.get("raw") or {}).get("Entity_Type_Code") == "2":
                    buckets["group"] += 1
        return buckets

    def summary(
        self,
        *,
        source_id: Optional[str] = None,
        specialty: Optional[str] = None,
        state: Optional[str] = None,
        review_state: Optional[str] = None,
        view: Optional[str] = None,
    ) -> Dict[str, Any]:
        view = view or "historical"
        doctor_ids = self._scoped_doctor_ids(
            source_id=source_id, specialty=specialty, state=state, review_state=review_state
        )
        records = self.repo.list_source_records()
        links = self.repo.list_links()
        reviews = self.repo.list_reviews()
        doctors = {d["doctor_id"]: d for d in self.repo.list_doctors()}
        state_snap = self.repo.state()
        pipeline_counts = state_snap.get("pipeline_counts") or {}
        actions = pipeline_counts.get("actions") or {}

        # Incoming/upload batches only when view=incoming; historical = source CSVs
        upload_batches = state_snap.get("upload_batches") or []
        if view == "incoming":
            scoped_records = [
                r for r in records if (r.get("source_id") or "").startswith("upload")
            ]
        elif view == "all":
            scoped_records = list(records)
        else:
            scoped_records = [
                r
                for r in records
                if not (r.get("source_id") or "").startswith("upload")
            ]

        if source_id:
            scoped_records = [r for r in scoped_records if r.get("source_id") == source_id]

        # Exclude NPPES + legacy master from "source records processed" denominator narrative
        processable = [
            r for r in scoped_records if r.get("source_id") not in NON_SOURCE_ENTRY_KEYS
        ]

        accepted_links = {
            l["source_record_id"]: l
            for l in links
            if is_linked_status(l.get("link_status"))
        }
        resolved = [r for r in processable if r["source_record_id"] in accepted_links]
        gained_npi = sum(
            1
            for r in resolved
            if r.get("provider_identifier")
            and not any(
                nf.get("valid") and nf.get("digits") == r.get("provider_identifier")
                for nf in (r.get("npi_fields") or [])
                if nf.get("field")  # had a stated NPI field that was empty/invalid originally
            )
            # simpler: linked record whose source NPI was missing
            or (
                not any(nf.get("valid") for nf in (r.get("npi_fields") or []))
                and r.get("provider_identifier")
            )
        )
        # recount gained missing NPI properly
        gained_npi = 0
        for r in resolved:
            had_valid = any(nf.get("valid") for nf in (r.get("npi_fields") or []))
            link = accepted_links.get(r["source_record_id"])
            if link and not had_valid:
                gained_npi += 1

        npi_issues = self._npi_issue_buckets(processable)
        wrong_total = sum(npi_issues.values())

        metrics = state_snap.get("pipeline_metrics") or pipeline_counts.get("metrics") or {}
        masters_after = int(metrics.get("doctors") or len(doctors))
        masters_before = int(metrics.get("legacy_rows") or 0)
        merges = int(metrics.get("merges") or 0)
        splits = int(metrics.get("splits") or 0)
        new_masters = int(metrics.get("new_masters") or 0)

        same_name_kept = sum(
            1
            for r in reviews
            if r.get("case_type") == "same_name_ambiguity" and r.get("status") in {"pending", "completed", "approved"}
        )
        # also count distinct family names with 2+ goldens
        by_family: Dict[str, int] = {}
        for d in doctors.values():
            fam = (d.get("family_name") or "").lower()
            if fam:
                by_family[fam] = by_family.get(fam, 0) + 1
        same_name_doctors = sum(1 for c in by_family.values() if c > 1)

        pending_reviews = [r for r in reviews if r.get("status") == "pending"]
        compliance = [
            r
            for r in pending_reviews
            if r.get("case_type") == "compliance_review" or r.get("pipeline_action") == "COMPLIANCE_REVIEW"
        ]
        unmatched = [r for r in processable if (r.get("resolution_status") or "") in {"unresolved", "pending_review"} and r["source_record_id"] not in accepted_links]
        provisional = [
            d
            for d in doctors.values()
            if (d.get("npi_status") in {"unassigned", "provisional"} or not d.get("official_npi"))
            and d.get("identity_status") != "reference"
        ]

        filters = {
            "source_id": source_id,
            "specialty": specialty,
            "state": state,
            "review_state": review_state,
            "view": view,
        }

        def kpi(key, label, value, href, tooltip, secondary=None, display=None, extra_filters=None):
            return {
                "key": key,
                "label": label,
                "value": value,
                "secondary_value": secondary,
                "display": display if display is not None else str(value),
                "tooltip": tooltip,
                "href": href,
                "filters": {**(extra_filters or {}), **{k: v for k, v in filters.items() if v}},
            }

        kpis = [
            kpi(
                "source_records_processed",
                "Source records processed",
                len(processable),
                "/sources",
                "All non-reference source rows in scope (excludes NPPES and Legacy Master baselines).",
            ),
            kpi(
                "resolved_to_npi",
                "Records resolved to an NPI",
                len(resolved),
                "/golden-records",
                f"{gained_npi} of these gained a missing NPI via match.",
                secondary=gained_npi,
                display=f"{len(resolved)} ({gained_npi} gained NPI)",
            ),
            kpi(
                "wrong_npis_flagged",
                "Wrong NPIs flagged",
                wrong_total,
                "/reviews",
                "Group / invalid / deactivated / mismatch buckets.",
                display=f"{wrong_total} (G{npi_issues['group']} I{npi_issues['invalid']} D{npi_issues['deactivated']} M{npi_issues['mismatch']})",
                extra_filters={"issue": "npi"},
            ),
            kpi(
                "master_cleanup",
                "Master records before → after",
                masters_after,
                "/golden-records",
                f"Legacy master rows {masters_before}. Merges {merges}. Splits {splits}. New masters {new_masters}.",
                secondary=masters_before,
                display=f"{masters_before} → {masters_after}",
            ),
            kpi(
                "same_name_separate",
                "Same-name doctors kept separate",
                same_name_doctors or same_name_kept,
                "/reviews",
                "Golden profiles sharing a family name, plus same-name ambiguity cases.",
                extra_filters={"case_type": "same_name_ambiguity"},
            ),
            kpi(
                "pending_human_review",
                "Pending human review",
                len(pending_reviews),
                "/reviews",
                "Open review-center cases.",
                extra_filters={"status": "pending"},
            ),
            kpi(
                "payment_compliance",
                "Payment records needing compliance review",
                len(compliance),
                "/payment-compliance",
                "Transparency / payment rows that must not auto-correct filed values.",
            ),
            kpi(
                "unmatched_provisional",
                "Unmatched / provisional (no NPI)",
                len(unmatched) + len(provisional),
                "/golden-records",
                f"{len(unmatched)} unmatched source rows; {len(provisional)} provisional masters.",
                display=f"{len(unmatched)} unmatched · {len(provisional)} provisional",
            ),
        ]

        # Priority list by business risk
        priority = sorted(
            pending_reviews,
            key=lambda r: (
                *risk_rank(r.get("case_type"), r.get("severity"), r.get("pipeline_action")),
                r.get("created_at") or "",
            ),
        )[:12]
        priority_rows = []
        for r in priority:
            d = doctors.get(r.get("doctor_id") or "")
            rec = next((x for x in records if x.get("source_record_id") == r.get("source_record_id")), None)
            priority_rows.append({
                "review_id": r["review_id"],
                "title": r.get("title"),
                "doctor_id": r.get("doctor_id"),
                "doctor_name": (d.get("preferred_name") if d else None)
                or (rec.get("recorded_name") if rec else None)
                or "Unassigned candidate",
                "issue": case_label(r.get("case_type")),
                "reason": r.get("pipeline_reason") or case_label(r.get("case_type")),
                "source": source_label((rec or {}).get("source_id")),
                "source_id": (rec or {}).get("source_id"),
                "severity": r.get("severity"),
                "status": r.get("status"),
                "created_at": r.get("created_at"),
                "href": f"/reviews/{r['review_id']}",
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
            source_coverage.append({
                "source_id": source["source_id"],
                "source_name": source_label(source["source_id"]),
                "row_count": source.get("row_count") or len(src_records),
                "latest_data_date": latest,
            })

        audits = sorted(
            self.repo.list_audit(),
            key=lambda a: a.get("occurred_at") or a.get("created_at") or "",
            reverse=True,
        )[:8]
        recent_decisions = []
        for a in audits:
            d = doctors.get(a.get("doctor_id") or "")
            recent_decisions.append({
                "audit_id": a.get("audit_id"),
                "actor_label": a.get("actor_label") or a.get("actor") or "System",
                "action": a.get("action"),
                "doctor_id": a.get("doctor_id"),
                "doctor_name": d.get("preferred_name") if d else None,
                "occurred_at": a.get("occurred_at") or a.get("created_at"),
                "review_id": a.get("review_id"),
            })

        run_meta = state_snap.get("pipeline_run") or {}
        runs = state_snap.get("pipeline_runs") or state_snap.get("demo_runs") or []
        last_run = None
        if runs:
            last_run = max(runs, key=lambda r: r.get("updated_at") or r.get("finished_at") or "")
        last_run_at = (last_run or {}).get("updated_at") or run_meta.get("finished_at")
        last_run_status = (last_run or {}).get("status") or ("completed" if run_meta.get("finished_at") else None)

        return {
            "dataset_updated_at": run_meta.get("finished_at") or last_run_at,
            "last_simulated_run_at": last_run_at,
            "last_run_status": last_run_status,
            "view": view,
            "snapshot_version": self.repo.snapshot_version(),
            "applied_filters": filters,
            "kpis": kpis,
            "npi_issue_buckets": npi_issues,
            "action_counts": actions,
            "scorecard_available": False,
            "priority_reviews": priority_rows,
            "recent_changes": recent_changes,
            "source_coverage": source_coverage,
            "recent_decisions": recent_decisions,
            "upload_batch_count": len(upload_batches),
        }

    def source_breakdown(
        self,
        *,
        source_id: Optional[str] = None,
        specialty: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Final pipeline action counts by source (business labels)."""
        state_snap = self.repo.state()
        decisions = []
        # Reconstruct from reviews + linked records
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        action_by_uid: Dict[str, str] = {}
        for review in self.repo.list_reviews():
            uid = review.get("source_record_id")
            if uid and review.get("pipeline_action"):
                action_by_uid[uid] = review["pipeline_action"]
        for link in self.repo.list_links():
            uid = link.get("source_record_id")
            if uid and uid not in action_by_uid and is_linked_status(link.get("link_status")):
                action_by_uid[uid] = "AUTO_LINK"

        action_keys = ["AUTO_LINK", "REVIEW", "COMPLIANCE_REVIEW", "DEDUPE_REVIEW", "ASSIGN_NPI", "NOT_A_PERSON"]
        rows = []
        for source in self.repo.list_sources():
            if source_id and source["source_id"] != source_id:
                continue
            if source["source_id"] == "nppes":
                continue
            src_records = [r for r in records.values() if r.get("source_id") == source["source_id"]]
            if specialty:
                src_records = [r for r in src_records if r.get("specialty") == specialty]
            if state:
                src_records = [r for r in src_records if r.get("state") == state]
            segments = []
            for action in action_keys:
                count = sum(1 for r in src_records if action_by_uid.get(r["source_record_id"]) == action)
                # pending_review without pipeline_action → REVIEW
                if action == "REVIEW":
                    count = sum(
                        1
                        for r in src_records
                        if action_by_uid.get(r["source_record_id"]) in {None, "REVIEW"}
                        and r.get("resolution_status") == "pending_review"
                    ) + sum(1 for r in src_records if action_by_uid.get(r["source_record_id"]) == "REVIEW")
                    # avoid double count — recompute cleanly
                    count = sum(1 for r in src_records if (action_by_uid.get(r["source_record_id"]) or (
                        "REVIEW" if r.get("resolution_status") == "pending_review" else None
                    )) == "REVIEW")
                segments.append({"status": action, "label": action.replace("_", " ").title(), "count": count})
            rows.append({
                "source_id": source["source_id"],
                "source_name": source_label(source["source_id"]),
                "segments": segments,
            })
        total = sum(seg["count"] for row in rows for seg in row["segments"])
        return {
            "rows": rows,
            "applied_filters": {"source_id": source_id, "specialty": specialty, "state": state},
            "text_summary": f"Final actions across {len(rows)} sources ({total} counted decisions).",
            "legend": [{"key": a, "label": a.replace("_", " ").title()} for a in action_keys],
        }
