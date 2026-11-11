"""Template search plans. The matcher only accepts fields the source profile allows."""

from __future__ import annotations

from typing import Any, Dict, List

ALLOWED_FIELDS = {
    "state",
    "city",
    "zip3",
    "specialty_code",
    "last_name_phonetic",
    "first_initial",
    "former_name",
    "phone",
    "email",
    "license",
    "organization",
    "name",
}


def validate_search_plan(plan: Dict[str, Any]) -> List[str]:
    """Return errors. An invalid plan must not be executed."""
    errors: List[str] = []
    if not isinstance(plan, dict):
        return ["Search plan must be an object."]
    for bucket in ("filters", "match_any"):
        rows = plan.get(bucket) or []
        if not isinstance(rows, list):
            errors.append(f"{bucket} must be a list.")
            continue
        for row in rows:
            field = (row or {}).get("field")
            if field not in ALLOWED_FIELDS:
                errors.append(f"{bucket} field {field} is not in the source profile.")
    top_k = plan.get("top_k")
    if top_k is not None and (not isinstance(top_k, int) or top_k < 1 or top_k > 100):
        errors.append("top_k must be between 1 and 100.")
    if plan.get("sql") or plan.get("query"):
        errors.append("Free-form queries are not allowed.")
    return errors


def template_plan(standardized: Dict[str, Any] | None, *, reason: str) -> Dict[str, Any]:
    """Build a plan from standardized fields only. No free-form text query."""
    std = standardized or {}
    name = std.get("name") or {}
    filters: List[Dict[str, str]] = []
    match_any: List[Dict[str, str]] = []
    if std.get("state"):
        filters.append({"field": "state", "value": str(std["state"])})
    if std.get("city"):
        filters.append({"field": "city", "value": str(std["city"])})
    if std.get("zip3"):
        filters.append({"field": "zip3", "value": str(std["zip3"])})
    if name.get("last_norm"):
        match_any.append({"field": "name", "value": str(name.get("last_norm"))})
    if name.get("first_norm"):
        match_any.append({"field": "first_initial", "value": str(name.get("first_norm"))[:1]})
    for part in name.get("last_parts") or []:
        match_any.append({"field": "former_name", "value": str(part)})
    if std.get("organization"):
        match_any.append({"field": "organization", "value": str(std["organization"])})
    if std.get("phone"):
        match_any.append({"field": "phone", "value": str(std["phone"])})
    if std.get("email"):
        match_any.append({"field": "email", "value": str(std["email"])})
    if std.get("license_no"):
        match_any.append({"field": "license", "value": str(std["license_no"])})
    parts = [name.get("display") or "", std.get("specialty_label") or std.get("specialty") or "", std.get("organization") or "", std.get("city") or "", std.get("state") or ""]
    plan = {
        "mode": "template",
        "filters": filters,
        "match_any": match_any,
        "semantic_text": " ".join(part for part in parts if part).strip(),
        "top_k": 20,
        "reason": reason,
    }
    errors = validate_search_plan(plan)
    plan["valid"] = not errors
    plan["errors"] = errors
    return plan
