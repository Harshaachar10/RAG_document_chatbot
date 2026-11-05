from __future__ import annotations

from typing import Any, Dict, List

from app.identity.labels import source_label
from app.utils.links import is_linked_status


def enrich_source_metrics(repo: Any) -> List[Dict[str, Any]]:
    records = repo.list_source_records()
    links = {l["source_record_id"]: l for l in repo.list_links() if is_linked_status(l.get("link_status"))}
    reviews = repo.list_reviews()
    pending_by_record = {
        r.get("source_record_id")
        for r in reviews
        if r.get("status") == "pending" and r.get("source_record_id")
    }
    items = []
    for source in repo.list_sources():
        sid = source["source_id"]
        rows = [r for r in records if r.get("source_id") == sid]
        # NPPES rows live only as reference meta
        row_count = int(source.get("row_count") or len(rows))
        npi_present = sum(1 for r in rows if any((nf.get("digits") for nf in (r.get("npi_fields") or []))))
        npi_valid = sum(1 for r in rows if any(nf.get("valid") for nf in (r.get("npi_fields") or [])))
        npi_missing = sum(1 for r in rows if not any(nf.get("digits") for nf in (r.get("npi_fields") or [])))
        npi_wrong = 0
        npi_group = 0
        npi_deactivated = 0
        for r in rows:
            for lu in r.get("npi_lookups") or []:
                if lu.get("status") in {"luhn_fail", "invalid_format", "placeholder", "not_in_reference"}:
                    npi_wrong += 1
                if lu.get("status") == "deactivated":
                    npi_deactivated += 1
            for flag in r.get("record_flags") or []:
                if "GROUP" in (flag.get("code") or "").upper() or "ORG" in (flag.get("code") or "").upper():
                    npi_group += 1
        duplicates = sum(1 for r in rows if r.get("is_source_duplicate") or r.get("duplicate_of_record_id"))
        resolved = sum(1 for r in rows if r["source_record_id"] in links)
        in_review = sum(1 for r in rows if r["source_record_id"] in pending_by_record)
        unmatched = sum(
            1
            for r in rows
            if r["source_record_id"] not in links
            and r.get("resolution_status") in {"unresolved", "pending_review", None, ""}
            and r.get("resolution_status") != "informational"
        )
        latest = max((r.get("record_date") or "" for r in rows), default=None) or source.get("updated_at")
        items.append({
            **source,
            "source_name": source_label(sid),
            "row_count": row_count,
            "npi_present": npi_present,
            "npi_valid": npi_valid,
            "npi_missing": npi_missing,
            "npi_wrong": npi_wrong,
            "npi_group": npi_group,
            "npi_deactivated": npi_deactivated,
            "duplicates": duplicates,
            "resolved": resolved,
            "in_review": in_review,
            "unmatched": unmatched,
            "latest_valid_date": latest,
            "metric_links": {
                "rows": f"/sources?source_id={sid}",
                "npi_missing": f"/sources?source_id={sid}&status=unresolved",
                "in_review": f"/reviews?source_id={sid}&status=pending",
                "resolved": f"/sources?source_id={sid}&status=linked",
                "unmatched": f"/sources?source_id={sid}&status=unresolved",
            },
        })
    return items
