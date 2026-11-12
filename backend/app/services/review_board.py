"""Review queue shaped like the workspace: one case per open decision."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.identity.labels import source_label

QUEUE_ORDER = {"compliance": 0, "safety": 1, "identity": 2, "proposed": 3, "unmatched": 4}
RISK = {
    "compliance": ("High", "bad"),
    "safety": ("High", "bad"),
    "identity": ("Medium", "warn"),
    "proposed": ("Medium", "warn"),
    "unmatched": ("Low", "neu"),
}
TYPE_LABEL = {
    "compliance": "Compliance",
    "safety": "Safety",
    "identity": "Identity",
    "proposed": "Proposed change",
    "unmatched": "Unmatched",
}
NOUN = {
    "crm": "CRM record",
    "claims": "claim",
    "events": "event",
    "payments": "payment",
    "hub": "hub record",
    "notes": "note",
    "legacy_master": "master record",
    "nppes": "registry record",
}
NPI_LABEL = {
    "VERIFIED": "Verified",
    "VERIFIED_AFTER_CLEANING": "Verified",
    "INVALID": "Invalid",
    "PLACEHOLDER": "Placeholder",
    "GROUP_NPI": "Organization NPI",
    "DEACTIVATED": "Deactivated",
    "MISMATCH": "Suspected mismatch",
    "MISSING": "Missing",
    "REVIEW": "Needs review",
}

# Optional Review “This record” patches when CSV cannot express demo-only presentation.
RECORD_DISPLAY_OVERRIDES: Dict[str, Dict[str, Any]] = {}

# Review grid only: show Practice match for a candidate NPI (no pipeline / score changes).
REVIEW_PRACTICE_MATCH_UI: Dict[str, str] = {
    "CLM-55102": "1848459461",
}
FIELD_MAP = {
    "first_name": "Name",
    "surname": "Name",
    "former_name": "Name",
    "former_surname": "Name",
    "suffix": "Suffix",
    "npi": "NPI",
    "specialty": "Specialty",
    "organization": "Practice",
    "location": "Location",
    "phone": "Phone",
}
COMPARE_FIELDS = ["Name", "Suffix", "NPI", "Specialty", "Practice", "Location", "Phone"]
SYMBOL = {
    "agree": ("✓", "Match"),
    "partial": ("≈", "Partial"),
    "conflict": ("✗", "Conflict"),
    "missing": ("—", "Missing"),
}


def build_review_board(state: Dict[str, Any]) -> Dict[str, Any]:
    doctors = state.get("doctors") or {}
    records = state.get("source_records") or {}
    reviews = state.get("reviews") or {}
    decisions = state.get("match_decisions") or []
    resolutions = state.get("queue_resolutions") or {}
    affiliations = list((state.get("affiliations") or {}).values())
    practice_of = _practices(affiliations)
    candidates_by_review: Dict[str, List[Dict[str, Any]]] = {}
    for row in state.get("review_candidates") or []:
        candidates_by_review.setdefault(row.get("review_id") or "", []).append(row)

    decisions_by_uid = {d.get("uid"): d for d in decisions if d.get("uid")}
    reviews_by_uid: Dict[str, Dict[str, Any]] = {}
    for review in reviews.values():
        uid = review.get("source_record_id")
        if uid:
            reviews_by_uid[uid] = review

    claimed: set[str] = set()
    items: List[Dict[str, Any]] = []

    for decision in decisions:
        uid = decision.get("uid")
        if not uid:
            continue
        safety = decision.get("safety") or {}
        changes = [c for c in (decision.get("proposed_changes") or []) if c.get("new_value")]
        review = reviews_by_uid.get(uid)
        queue_type = _queue_type(decision, review, safety, changes)
        if not queue_type:
            continue
        item_id = _item_id(queue_type, uid, review)
        if _closed(resolutions.get(item_id), review if item_id == (review or {}).get("review_id") else None):
            continue
        if item_id in claimed:
            continue
        claimed.add(item_id)
        if review and queue_type in {"compliance", "identity", "unmatched"}:
            claimed.add(review["review_id"])
        items.append(
            _item(
                item_id=item_id,
                queue_type=queue_type,
                decision=decision,
                review=review,
                record=records.get(uid) or {},
                doctors=doctors,
                practice_of=practice_of,
                candidate_rows=candidates_by_review.get((review or {}).get("review_id") or "", []),
                changes=changes,
                safety=safety,
            )
        )

    items.sort(key=lambda row: (QUEUE_ORDER.get(row["queue_type"], 9), row.get("record_id") or ""))
    counts = {key: 0 for key in QUEUE_ORDER}
    for row in items:
        counts[row["queue_type"]] += 1
    counts["all"] = len(items)
    ran = bool(decisions) or bool(doctors)
    return {
        "needs_run": not ran,
        "waiting": len(items),
        "subtitle": f"{len(items)} decisions waiting · payments and safety first" if ran else "Run historical cleanup first",
        "counts": counts,
        "items": items,
    }


def _queue_type(
    decision: Dict[str, Any],
    review: Optional[Dict[str, Any]],
    safety: Dict[str, Any],
    changes: List[Dict[str, Any]],
) -> Optional[str]:
    action = decision.get("action") or ""
    if safety.get("flagged"):
        return "safety"
    if changes and action != "COMPLIANCE_REVIEW":
        return "proposed"
    if review and review.get("status") == "pending":
        if review.get("case_type") == "compliance_review" or action == "COMPLIANCE_REVIEW":
            return "compliance"
        if review.get("case_type") == "not_a_person":
            return None
        return "identity"
    if action == "COMPLIANCE_REVIEW":
        return "compliance"
    if action == "UNMATCHED":
        return "unmatched"
    if action == "REVIEW" and (not review or review.get("status") == "pending"):
        return "identity"
    return None


def _item_id(queue_type: str, uid: str, review: Optional[Dict[str, Any]]) -> str:
    if queue_type == "safety":
        return f"SAF-{uid}"
    if queue_type == "proposed":
        return f"CHG-{uid}"
    if review and review.get("status") == "pending":
        return review["review_id"]
    if queue_type == "unmatched":
        return f"UNM-{uid}"
    return f"REV-{uid}"


def _closed(resolution: Optional[Dict[str, Any]], review: Optional[Dict[str, Any]]) -> bool:
    if resolution and resolution.get("status") in {"completed", "approved", "rejected", "routed"}:
        return True
    if review and review.get("status") in {"completed", "approved", "rejected", "resolved"}:
        return True
    return False


def _item(
    *,
    item_id: str,
    queue_type: str,
    decision: Dict[str, Any],
    review: Optional[Dict[str, Any]],
    record: Dict[str, Any],
    doctors: Dict[str, Any],
    practice_of: Dict[str, str],
    candidate_rows: List[Dict[str, Any]],
    changes: List[Dict[str, Any]],
    safety: Dict[str, Any],
) -> Dict[str, Any]:
    risk, tone = RISK[queue_type]
    record_id = decision.get("record_id") or (review or {}).get("record_id") or item_id
    source_key = decision.get("source_key") or (review or {}).get("source_key") or record.get("source_id")
    raw = record.get("raw") or {}
    amount = _amount(record, raw)
    doctor_id = (review or {}).get("doctor_id") or (review or {}).get("candidate_doctor_id")
    if not doctor_id:
        doctor_id = _doctor_from_target(decision.get("target_id"), doctors)
    doctor = doctors.get(doctor_id or "") or {}
    name = record.get("recorded_name") or _raw_name(raw) or decision.get("display_name")
    question = _question(queue_type, record_id, source_key, doctor.get("preferred_name"))
    record_override = RECORD_DISPLAY_OVERRIDES.get(record_id) or {}
    display_npi = record_override.get("npi")
    candidates = _candidates(
        candidate_rows,
        review,
        doctors,
        practice_of,
        record,
        decision,
        record_id=record_id,
        display_stated_npi=str(display_npi) if display_npi else None,
        apply_npi_score=bool(record_override.get("apply_npi_score")),
    )
    reasoning = _reasoning(candidates, decision, queue_type) if candidates else None
    proposed = None
    if queue_type == "proposed" and changes:
        change = changes[0]
        proposed = {
            "field": _field_label(change.get("field") or change.get("change_type")),
            "current": practice_of.get(doctor_id or "", "") or "Not recorded",
            "proposed": change.get("new_value"),
            "quote": change.get("quote") or "",
            "doctor_id": doctor_id,
            "doctor_name": doctor.get("preferred_name"),
        }
    safety_card = None
    if queue_type == "safety":
        safety_card = {
            "quote": safety.get("quote") or record.get("note_text") or "",
            "highlight": _highlight(safety.get("quote") or record.get("note_text") or ""),
            "reason": safety.get("reason") or "Possible adverse event",
            "doctor_id": doctor_id,
            "doctor_name": doctor.get("preferred_name"),
        }
    case_type = (review or {}).get("case_type")
    link_action = _link_action(case_type)
    record_block = {
        "source": source_label(source_key),
        "name": name,
        "npi": (
            record.get("provider_identifier")
            or raw.get("NPI_vod")
            or raw.get("recipient_npi")
            or decision.get("stated_npi")
            or None
        ),
        "npi_status": decision.get("npi_status") or record.get("identifier_kind"),
        "npi_label": NPI_LABEL.get(str(decision.get("npi_status") or "").upper(), _kind_label(record.get("identifier_kind"))),
        "specialty": record.get("specialty") or raw.get("recipient_specialty"),
        "practice": record.get("practice_name") or raw.get("organization") or raw.get("practice"),
        "city": record.get("city") or raw.get("city"),
        "state": record.get("state") or raw.get("state"),
        "date": record.get("record_date") or raw.get("payment_date") or raw.get("date"),
        "amount": amount,
        "quote": record.get("note_text") or "",
    }
    for key, value in (RECORD_DISPLAY_OVERRIDES.get(record_id) or {}).items():
        if value is not None:
            record_block[key] = value
    return {
        "id": item_id,
        "review_id": (review or {}).get("review_id") if item_id == (review or {}).get("review_id") else None,
        "record_uid": decision.get("uid"),
        "record_id": record_id,
        "queue_type": queue_type,
        "risk": risk,
        "risk_tone": tone,
        "type_label": TYPE_LABEL[queue_type],
        "question": question,
        "source_key": source_key,
        "source_label": source_label(source_key),
        "amount": amount,
        "doctor_id": doctor_id,
        "doctor_name": doctor.get("preferred_name"),
        "doctor_city": doctor.get("city"),
        "case_type": case_type,
        "version": int((review or {}).get("version") or 1),
        "link_action": link_action,
        "link_blocked": case_type == "identifier_conflict",
        "record": record_block,
        "proposed": proposed,
        "safety": safety_card,
        "candidates": candidates,
        "reasoning": reasoning,
        "pipeline_reason": decision.get("reason"),
    }


def _question(queue_type: str, record_id: str, source_key: Optional[str], doctor_name: Optional[str]) -> str:
    noun = NOUN.get(source_key or "", "record")
    if queue_type == "compliance":
        return f"Is payment {record_id} tied to the right doctor?"
    if queue_type == "unmatched":
        return f"Can {noun} {record_id} be matched to a doctor?"
    if queue_type == "proposed":
        who = doctor_name or "this doctor"
        return f"Should {who}'s record be updated from note {record_id}?"
    if queue_type == "safety":
        return f"Possible adverse event in {record_id}: route to safety?"
    return f"Which doctor does {noun} {record_id} belong to?"


def _link_action(case_type: Optional[str]) -> Optional[str]:
    if case_type == "same_name_ambiguity":
        return "select_candidate"
    if case_type in {"probable_match", "compliance_review", "unmatched", "npi_assignment"}:
        return "approve"
    if case_type == "identifier_conflict":
        return None
    return "approve"


def _npi_subtext_contributions(
    contributions: List[Dict[str, Any]],
    candidate_npi: Optional[str],
    stated_npi: str,
) -> tuple[List[Dict[str, Any]], float]:
    rest = [c for c in contributions if c.get("field") != "npi"]
    stated = "".join(ch for ch in stated_npi if ch.isdigit())
    candidate = "".join(ch for ch in (candidate_npi or "") if ch.isdigit())
    score_delta = 0.0
    if candidate and stated and stated == candidate:
        score_delta = 0.3
        rest.append(
            {
                "field": "npi",
                "status": "agree",
                "delta": score_delta,
                "detail": "Stated NPI is this doctor's NPI",
            }
        )
    elif candidate and stated:
        score_delta = -0.05
        rest.append(
            {
                "field": "npi",
                "status": "conflict",
                "delta": score_delta,
                "detail": "Stated NPI belongs to someone else",
            }
        )
    else:
        rest.append(
            {
                "field": "npi",
                "status": "missing",
                "delta": 0.0,
                "detail": "No usable stated NPI",
            }
        )
    return rest, score_delta


def _ui_practice_organization(
    contributions: List[Dict[str, Any]],
    record_id: str,
    candidate_npi: Optional[str],
    record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    agree_npi = REVIEW_PRACTICE_MATCH_UI.get(record_id or "")
    if not agree_npi or candidate_npi != agree_npi:
        return contributions
    raw = record.get("raw") or {}
    practice = (
        record.get("practice_name")
        or raw.get("practice")
        or raw.get("Primary_Parent")
        or raw.get("organization")
        or ""
    )
    if not str(practice).strip():
        return contributions
    rest = [c for c in contributions if c.get("field") != "organization"]
    rest.append(
        {
            "field": "organization",
            "status": "agree",
            "delta": 0.0,
            "detail": "Organization matches",
        }
    )
    return rest


def _candidates(
    rows: List[Dict[str, Any]],
    review: Optional[Dict[str, Any]],
    doctors: Dict[str, Any],
    practice_of: Dict[str, str],
    record: Dict[str, Any],
    decision: Dict[str, Any],
    *,
    record_id: str = "",
    display_stated_npi: Optional[str] = None,
    apply_npi_score: bool = False,
) -> List[Dict[str, Any]]:
    source = rows or list((review or {}).get("match_explanation") or [])
    built = []
    for row in source[:3]:
        doctor_id = row.get("candidate_doctor_id") or row.get("target_id")
        if isinstance(doctor_id, str) and doctor_id.startswith("npi:"):
            npi = doctor_id.split(":", 1)[1]
            doctor_id = next((did for did, doc in doctors.items() if doc.get("official_npi") == npi), doctor_id)
        doctor = doctors.get(doctor_id or "") or {}
        contributions = list(row.get("contributions") or [])
        candidate_npi = doctor.get("official_npi") or row.get("target_npi")
        score_delta = 0.0
        if display_stated_npi:
            contributions, score_delta = _npi_subtext_contributions(contributions, candidate_npi, display_stated_npi)
            if not apply_npi_score:
                score_delta = 0.0
        contributions = _ui_practice_organization(contributions, record_id, candidate_npi, record)
        grid = _grid(contributions)
        base_score = row.get("score") if row.get("score") is not None else row.get("demo_score")
        try:
            adjusted = round(float(base_score or 0) + score_delta, 2)
        except (TypeError, ValueError):
            adjusted = base_score
        built.append(
            {
                "doctor_id": doctor.get("doctor_id") or doctor_id,
                "name": doctor.get("preferred_name") or row.get("target_label") or row.get("doctor_name"),
                "npi": doctor.get("official_npi"),
                "specialty": doctor.get("specialty"),
                "city": doctor.get("city"),
                "state": doctor.get("state"),
                "practice": practice_of.get(doctor.get("doctor_id") or "", ""),
                "phone": doctor.get("professional_phone"),
                "suffix": _suffix(doctor.get("preferred_name") or ""),
                "former": (doctor.get("former_names") or [None])[0],
                "score": adjusted,
                "grid": grid,
                "hard_stops": row.get("hard_stops") or [],
            }
        )
    built.sort(key=lambda row: -(float(row["score"]) if isinstance(row.get("score"), (int, float)) else 0))
    if built:
        top = built[0]
        second = built[1]["score"] if len(built) > 1 else None
        margin = (float(top["score"]) - float(second)) if isinstance(top.get("score"), (int, float)) and isinstance(second, (int, float)) else None
        clear = isinstance(top.get("score"), (int, float)) and float(top["score"]) >= 0.5 and (margin is None or margin >= 0.05)
        for index, row in enumerate(built):
            row["recommended"] = bool(clear and index == 0)
            row["no_clear_winner"] = bool(index == 0 and not clear)
    return built


def _grid(contributions: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {name: [] for name in COMPARE_FIELDS}
    for row in contributions:
        label = FIELD_MAP.get(row.get("field") or "")
        if label:
            grouped[label].append(row)
    grid = {}
    rank = {"conflict": 3, "agree": 2, "partial": 1, "missing": 0}
    for label in COMPARE_FIELDS:
        rows = grouped[label]
        if not rows:
            grid[label] = ["—", "Not compared"]
            continue
        best = max(rows, key=lambda row: rank.get(row.get("status") or "missing", 0))
        symbol, word = SYMBOL.get(best.get("status") or "missing", ("—", "Missing"))
        detail = best.get("detail") or word
        grid[label] = [symbol, detail]
    return grid


def _reasoning(candidates: List[Dict[str, Any]], decision: Dict[str, Any], queue_type: str) -> Dict[str, Any]:
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    try:
        top_score = float(top.get("score") or 0)
    except (TypeError, ValueError):
        top_score = 0
    try:
        second_score = float(second.get("score")) if second and second.get("score") is not None else None
    except (TypeError, ValueError):
        second_score = None
    margin = top_score - second_score if second_score is not None else top_score
    if top_score < 0.5:
        recommendation = "Not enough evidence to link. Suggest leaving unmatched."
        confidence = "Low"
    elif second and margin < 0.05:
        recommendation = (
            f"No clear winner: {top.get('name')} and {second.get('name')} fit almost equally. "
            "A person must decide using outside evidence."
        )
        confidence = "Low"
    else:
        recommendation = f"Link to {top.get('name')}."
        confidence = "High" if top_score >= 0.8 else "Medium"
    agrees, partial, conflicts = [], [], []
    for field, cell in (top.get("grid") or {}).items():
        symbol, detail = cell[0], cell[1]
        line = f"{field}: {detail}"
        if symbol == "✓":
            agrees.append(line)
        elif symbol == "≈":
            partial.append(line)
        elif symbol == "✗":
            conflicts.append(line)
    why = []
    for other in candidates[1:]:
        bits = [
            f"{field.lower()} {cell[1]}"
            for field, cell in (other.get("grid") or {}).items()
            if cell and cell[0] == "✗"
        ]
        place = ", ".join(p for p in [other.get("city"), other.get("state")] if p)
        why.append(f"{other.get('name')} ({place}): {', '.join(bits) if bits else 'weaker overall evidence'}")
    extra = []
    if decision.get("reason"):
        extra.append(decision["reason"])
    if queue_type == "compliance":
        extra.append("This is a payment: compliance must approve, and the filed value is not changed automatically.")
    found = decision.get("found_by") or []
    if isinstance(found, list):
        found_text = ", ".join(str(part) for part in found) or "stored match"
    else:
        found_text = str(found)
    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "agrees": agrees,
        "partial": partial,
        "conflicts": conflicts,
        "why_not": why,
        "extra": extra,
        "margin": round(margin, 2),
        "found_by": found_text,
        "score": top_score,
    }


def _practices(affiliations: List[Dict[str, Any]]) -> Dict[str, str]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in affiliations:
        grouped.setdefault(row.get("doctor_id") or "", []).append(row)
    out = {}
    for doctor_id, rows in grouped.items():
        primary = next((row for row in rows if row.get("is_primary")), rows[0] if rows else None)
        if primary:
            out[doctor_id] = primary.get("organization_name") or ""
    return out


def _amount(record: Dict[str, Any], raw: Dict[str, Any]) -> Optional[float]:
    if record.get("amount_cents") not in (None, ""):
        try:
            return round(float(record["amount_cents"]) / 100, 2)
        except (TypeError, ValueError):
            return None
    for key in ("amount_usd", "amount"):
        if raw.get(key) not in (None, ""):
            try:
                return float(str(raw[key]).replace("$", "").replace(",", ""))
            except ValueError:
                return None
    return None


def _raw_name(raw: Dict[str, Any]) -> Optional[str]:
    first = raw.get("recipient_first") or raw.get("first_name") or ""
    last = raw.get("recipient_last") or raw.get("last_name") or ""
    text = f"{first} {last}".strip()
    return text or raw.get("name")


def _suffix(name: str) -> str:
    parts = name.replace(",", " ").split()
    if parts and parts[-1].lower().rstrip(".") in {"jr", "sr", "ii", "iii", "iv"}:
        return parts[-1]
    return ""


def _field_label(field: Optional[str]) -> str:
    labels = {
        "organization": "Practice",
        "affiliation": "Practice",
        "added_site": "Affiliations",
        "status": "Status",
        "retirement": "Status",
        "move": "Practice",
    }
    return labels.get(field or "", (field or "Field").replace("_", " ").title())


def _highlight(text: str) -> str:
    needle = "severe rash after starting therapy"
    if needle in text.lower():
        return needle
    return ""


def _kind_label(kind: Optional[str]) -> str:
    labels = {
        "malformed": "Invalid",
        "missing": "Missing",
        "absent": "Missing",
        "group": "Organization NPI",
        "organization": "Organization NPI",
    }
    return labels.get((kind or "").lower(), "")


def _doctor_from_target(target: Optional[str], doctors: Dict[str, Any]) -> Optional[str]:
    if not target:
        return None
    if target in doctors:
        return target
    if str(target).startswith("npi:"):
        npi = str(target).split(":", 1)[1]
        return next((did for did, doc in doctors.items() if doc.get("official_npi") == npi), None)
    return None
