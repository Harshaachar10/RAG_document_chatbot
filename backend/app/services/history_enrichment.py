"""Enrich identity history events into a clear chronological evidence trail."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

EVENT_TYPE_FILTERS: Dict[str, Set[str]] = {
    "names": {
        "name_variation_observed",
        "name_change_documented",
        "name_update",
    },
    "addresses": {
        "address_update",
        "address_observed",
        "contact_update",
    },
    "affiliations": {
        "affiliation_observed",
        "affiliation_effective",
        "affiliation_update",
    },
    "identifiers": {
        "identifier_conflict",
        "identifier_missing",
        "npi_missing",
    },
    "duplicates": {
        "possible_duplicate",
        "duplicate_ingestion",
    },
    "issues": {
        "identifier_conflict",
        "identifier_missing",
        "npi_missing",
        "possible_duplicate",
        "duplicate_ingestion",
        "name_update",
        "affiliation_update",
        "contact_update",
        "address_update",
    },
    "record_entries": {"record_entry"},
    "review_decisions": {"review_decision", "preferred_name_approved"},
}

CATEGORY_BY_TYPE: Dict[str, Tuple[str, str]] = {
    "name_update": ("name_change", "Name change"),
    "name_variation_observed": ("name_change", "Name variation"),
    "name_change_documented": ("name_change", "Name change documented"),
    "affiliation_update": ("affiliation_change", "Affiliation / practice change"),
    "affiliation_observed": ("affiliation_change", "Affiliation observed"),
    "affiliation_effective": ("affiliation_change", "Affiliation effective"),
    "contact_update": ("contact_change", "Contact change"),
    "address_update": ("address_change", "Address change"),
    "address_observed": ("address_change", "Address observed"),
    "identifier_conflict": ("identifier_issue", "Identifier conflict"),
    "identifier_missing": ("missing_field", "Missing identifier"),
    "npi_missing": ("missing_field", "Missing NPI"),
    "possible_duplicate": ("duplicate_signal", "Possible duplicate / variation"),
    "duplicate_ingestion": ("duplicate_signal", "Duplicate ingestion"),
    "review_decision": ("review", "Review decision"),
    "preferred_name_approved": ("review", "Preferred name approved"),
    "record_entry": ("activity", "Source activity"),
}


def _blank(value: Optional[str]) -> bool:
    return not (value or "").strip()


def _missing_identifier(record: Optional[Dict[str, Any]]) -> bool:
    if not record:
        return False
    kind = (record.get("identifier_kind") or "").strip().lower()
    value = (record.get("provider_identifier") or "").strip()
    if kind in {"missing", "absent", "none", "n/a", "na"}:
        return True
    if not value:
        return True
    if value.lower() in {"missing", "none", "n/a", "na", "unknown"}:
        return True
    return False


def _record_gaps(record: Optional[Dict[str, Any]]) -> List[str]:
    if not record:
        return []
    gaps: List[str] = []
    if _missing_identifier(record):
        gaps.append("NPI / provider identifier missing")
    if _blank(record.get("address_line")) and _blank(record.get("city")):
        gaps.append("Address missing")
    if _blank(record.get("practice_name")):
        gaps.append("Practice / affiliation missing")
    return gaps


def _activity_label(record: Optional[Dict[str, Any]], event_type: str, title: str) -> str:
    if record:
        kind = (record.get("record_kind") or "").strip().lower()
        note = (record.get("note_text") or "").lower()
        submitted_to = (record.get("submitted_to") or "").lower()
        if "meeting" in note or "meeting" in submitted_to or kind in {"event_attendance", "meeting"}:
            return "Meeting / event attendance"
        if kind in {"identity_entry", "crm_entry"}:
            return "Identity document / CRM entry"
        if kind in {"supporting_transaction", "payment", "claim"}:
            return "Transaction / claim activity"
        if kind:
            return kind.replace("_", " ").title()
    if event_type in CATEGORY_BY_TYPE:
        return CATEGORY_BY_TYPE[event_type][1]
    return title or "Identity activity"


def _build_narrative(
    *,
    event: Dict[str, Any],
    record: Optional[Dict[str, Any]],
    source_name: Optional[str],
    gaps: Sequence[str],
    previous_address: Optional[str],
) -> Tuple[str, str, Optional[str], Optional[str]]:
    """Return title, description, previous_value, new_value."""
    event_type = event.get("event_type") or "record_entry"
    title = (event.get("title") or "").strip()
    description = (event.get("description") or "").strip()
    previous_value = event.get("previous_value")
    new_value = event.get("new_value")
    activity = _activity_label(record, event_type, title)
    source_bit = f" via {source_name}" if source_name else ""
    name = (record or {}).get("recorded_name") or new_value or "this person"
    date = event.get("document_date") or event.get("recorded_at") or (record or {}).get("record_date")

    if event_type == "record_entry" and (not title or title == "Source record observed"):
        if gaps:
            title = f"{activity}: {gaps[0]}"
            description = (
                f"On {date or 'an unknown date'}, {name} appeared in a source record{source_bit}. "
                f"Issue noted: {'; '.join(gaps)}. "
                "Keep this on the trail when mapping recent work back to one identity."
            )
        else:
            title = f"{activity} recorded"
            bits = []
            if (record or {}).get("practice_name"):
                bits.append(f"practice {(record or {}).get('practice_name')}")
            if (record or {}).get("address_line"):
                bits.append(f"address {(record or {}).get('address_line')}")
            if (record or {}).get("provider_identifier"):
                bits.append(f"identifier {(record or {}).get('provider_identifier')}")
            detail = (", ".join(bits) + ". ") if bits else ""
            description = (
                f"On {date or 'an unknown date'}, {name} was observed{source_bit}. {detail}"
                "Use this entry when reconstructing the person's recent activity."
            )
        if record and not new_value:
            new_value = record.get("recorded_name") or record.get("practice_name") or record.get("address_line")

    if event_type in {"affiliation_update", "address_update", "address_observed"} or (
        record and previous_address and (record.get("address_line") or "") != previous_address
    ):
        addr = (record or {}).get("address_line") or new_value
        if addr and previous_address and previous_address != addr and event_type in {
            "affiliation_update", "address_update", "record_entry", "address_observed"
        }:
            if event_type == "record_entry" and "Address" not in title:
                title = f"Address changed in source document"
            previous_value = previous_value or previous_address
            new_value = new_value or addr
            if "address" not in description.lower():
                description = (
                    f"Address changed from {previous_address} to {addr} on {date or 'this date'}"
                    f"{source_bit}. {description}"
                ).strip()

    if _missing_identifier(record) and event_type in {"record_entry", "possible_duplicate", "npi_missing"}:
        if "npi" not in title.lower() and "identifier" not in title.lower():
            title = f"{activity}: NPI missing"
        if "npi" not in description.lower():
            description = (
                f"{description} NPI/provider identifier was not supplied on this date — "
                "treat as a gap when backtracking identity evidence."
            ).strip()

    if not description:
        description = title
    return title, description, previous_value, new_value


def classify_event(event: Dict[str, Any], record: Optional[Dict[str, Any]] = None) -> Tuple[str, str, List[str]]:
    event_type = event.get("event_type") or "record_entry"
    gaps = _record_gaps(record)
    category, label = CATEGORY_BY_TYPE.get(event_type, ("activity", "Identity activity"))
    title_l = f"{event.get('title') or ''} {event.get('description') or ''}".lower()
    if gaps and "npi" in " ".join(gaps).lower():
        if category == "activity":
            category, label = "missing_field", "Missing NPI"
        elif "npi" in title_l or event_type == "possible_duplicate":
            category, label = "missing_field", "Missing NPI / identifier gap"
    if "address" in title_l and category == "activity":
        category, label = "address_change", "Address change"
    return category, label, gaps


def enrich_history_items(
    events: Sequence[Dict[str, Any]],
    *,
    evidence_by_id: Dict[str, Dict[str, Any]],
    records_by_id: Dict[str, Dict[str, Any]],
    sources_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Attach issue labels, gaps, and clearer narratives for identity backtracking."""
    # Chronological pass to detect address transitions across the trail.
    ordered = sorted(
        events,
        key=lambda e: (
            e.get("document_date") or e.get("effective_date") or e.get("recorded_at") or "",
            e.get("event_id") or "",
        ),
    )
    last_address: Optional[str] = None
    address_by_event: Dict[str, Optional[str]] = {}
    for event in ordered:
        evid = evidence_by_id.get(event.get("evidence_id") or "")
        record = None
        if evid and evid.get("source_record_id"):
            record = records_by_id.get(evid["source_record_id"])
        addr = (record or {}).get("address_line") or None
        address_by_event[event.get("event_id") or ""] = last_address
        if addr:
            last_address = addr

    enriched: List[Dict[str, Any]] = []
    for event in events:
        evid = evidence_by_id.get(event.get("evidence_id") or "")
        record = None
        source_name = None
        source_type = event.get("source_type")
        source_record_id = None
        if evid and evid.get("source_record_id"):
            source_record_id = evid["source_record_id"]
            record = records_by_id.get(source_record_id)
            if record:
                source = sources_by_id.get(record.get("source_id") or "")
                if source:
                    source_name = source.get("source_name")
                    source_type = source_type or source.get("source_type")

        category, label, gaps = classify_event(event, record)
        prev_addr = address_by_event.get(event.get("event_id") or "")
        title, description, previous_value, new_value = _build_narrative(
            event=event,
            record=record,
            source_name=source_name,
            gaps=gaps,
            previous_address=prev_addr,
        )
        # Re-classify if narrative elevated an address change.
        if title.lower().startswith("address changed"):
            category, label = "address_change", "Address change"

        date_label = (
            event.get("effective_date")
            or event.get("document_date")
            or (record or {}).get("record_date")
            or event.get("recorded_at")
        )
        if event.get("effective_date"):
            date_meaning = "effective_date"
        elif event.get("document_date") or (record or {}).get("record_date"):
            date_meaning = "document_date"
        else:
            date_meaning = "recorded_at"

        enriched.append({
            **event,
            "title": title,
            "description": description,
            "previous_value": previous_value,
            "new_value": new_value,
            "date_label": date_label,
            "date_meaning": date_meaning,
            "source_type": source_type,
            "source_record_id": source_record_id,
            "issue_category": category,
            "issue_label": label,
            "gaps": list(gaps),
            "activity_label": _activity_label(record, event.get("event_type") or "", title),
            "actor": event.get("actor"),
            "reason": description,
            "evidence_quotation": evid.get("quoted_text") if evid else event.get("evidence_quotation"),
        })
    return enriched


def matches_event_filter(event: Dict[str, Any], event_type: Optional[str]) -> bool:
    if not event_type or event_type == "all":
        return True
    allowed = EVENT_TYPE_FILTERS.get(event_type)
    if not allowed:
        return True
    if event.get("event_type") in allowed:
        return True
    # Also allow issue filter via enriched category / gaps.
    if event_type == "issues":
        category = event.get("issue_category")
        if category and category not in {"activity", "review"}:
            return True
        if event.get("gaps"):
            return True
    if event_type == "addresses":
        if event.get("issue_category") == "address_change":
            return True
        blob = f"{event.get('title')} {event.get('description')}".lower()
        if "address" in blob:
            return True
    if event_type == "identifiers":
        if event.get("issue_category") in {"identifier_issue", "missing_field"}:
            return True
        if any("npi" in g.lower() or "identifier" in g.lower() for g in (event.get("gaps") or [])):
            return True
    return False
