from __future__ import annotations

"""Plain-English labels for identity UI (never expose raw enum jargon)."""

SOURCE_LABELS = {
    "nppes": "NPPES",
    "legacy_master": "Legacy Master",
    "crm": "CRM",
    "claims": "Claims",
    "events": "Events",
    "payments": "Payments",
    "hub": "Hub",
    "notes": "Notes",
}

CASE_TYPE_LABELS = {
    "probable_match": "Possible match",
    "compliance_review": "Payment compliance",
    "possible_duplicate": "Possible duplicate",
    "same_name_ambiguity": "Same-name ambiguity",
    "identifier_conflict": "Identifier conflict",
    "npi_assignment": "Needs NPI assignment",
    "unmatched": "Unmatched",
    "not_a_person": "Not a person",
    "auto_link": "Auto-linked",
}

ACTION_LABELS = {
    "AUTO_LINK": "Auto-linked to NPI",
    "REVIEW": "Needs human review",
    "COMPLIANCE_REVIEW": "Needs compliance review",
    "DEDUPE_REVIEW": "Possible duplicate",
    "ASSIGN_NPI": "Assign or create NPI",
    "NOT_A_PERSON": "Not a person record",
}

NPI_STATUS_LABELS = {
    "verified": "Verified",
    "reference": "Reference",
    "unassigned": "Provisional",
    "provisional": "Provisional",
    "deactivated": "Deactivated",
    "needs_review": "Needs review",
}

RESOLUTION_LABELS = {
    "linked": "Resolved",
    "pending_review": "In review",
    "unresolved": "Unmatched",
    "rejected": "Rejected",
    "informational": "Informational",
}


def source_label(key: str | None) -> str:
    if not key:
        return "Unknown source"
    return SOURCE_LABELS.get(key, key.replace("_", " ").title())


def case_label(case_type: str | None) -> str:
    if not case_type:
        return "Review"
    return CASE_TYPE_LABELS.get(case_type, case_type.replace("_", " ").title())


def review_question(
    *,
    source_key: str | None,
    display_name: str | None,
    candidate_name: str | None,
    action: str | None,
    case_type: str | None,
) -> str:
    name = (display_name or "this record").strip() or "this record"
    src = source_label(source_key)
    cand = (candidate_name or "").strip()
    action = action or ""
    if action == "COMPLIANCE_REVIEW" or case_type == "compliance_review":
        return f"Does this {src} payment correctly identify {name}?"
    if action == "NOT_A_PERSON" or case_type == "not_a_person":
        return f"Is this {src} row a person, or office/staff text?"
    if action == "DEDUPE_REVIEW" or case_type == "possible_duplicate":
        return f"Are these {src} rows duplicates of the same doctor?"
    if action == "ASSIGN_NPI" or case_type == "npi_assignment":
        return f"Should we assign or create an NPI for {name} from {src}?"
    if cand:
        return f"Is this {src} record the same doctor as {cand}?"
    return f"Who does this {src} record for {name} belong to?"


def risk_rank(case_type: str | None, severity: str | None, action: str | None = None) -> tuple:
    """Lower = higher business risk. Payments outrank routine updates."""
    if action == "COMPLIANCE_REVIEW" or case_type == "compliance_review":
        tier = 0
    elif case_type in {"identifier_conflict", "same_name_ambiguity"} or action == "REVIEW" and severity == "high":
        tier = 1
    elif case_type in {"possible_duplicate", "probable_match"}:
        tier = 2
    elif case_type in {"npi_assignment", "unmatched"}:
        tier = 3
    else:
        tier = 4
    sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity or "low", 4)
    return (tier, sev)
