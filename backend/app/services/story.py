"""Dashboard figures taken only from persisted pipeline decisions."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from app.identity.completeness import completeness

LINKED = {"AUTO_LINK", "PROVISIONAL"}
REVIEW = {"REVIEW"}
COMPLIANCE = {"COMPLIANCE_REVIEW"}
NOT_PERSON = {"NOT_A_PERSON", "ORGANIZATION", "DEDUPE"}
WRONG_NPI = {"GROUP_NPI", "INVALID", "PLACEHOLDER", "MISMATCH", "DEACTIVATED"}
CREDENTIALS = {"md", "do", "np", "pa", "phd", "jr", "sr", "dr"}


def _money(cents: Optional[int]) -> float:
    if not cents:
        return 0.0
    return round(cents / 100.0, 2)


def _name_key(value: str) -> str:
    tokens = [tok for tok in re.sub(r"[^a-z\s]", " ", (value or "").lower()).split() if tok not in CREDENTIALS]
    return " ".join(tokens[:3])


def _naive_name_pairs(people: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pairs a naive exact-name match would merge. Suffixes and credentials are ignored."""
    groups: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def add(key: str, doctor: Dict[str, Any]) -> None:
        if not key or not doctor.get("doctor_id"):
            return
        groups.setdefault(key, {})[doctor["doctor_id"]] = doctor

    for doctor in people:
        add(_name_key(doctor.get("preferred_name") or ""), doctor)
        for former in doctor.get("former_names") or []:
            if isinstance(former, str):
                add(_name_key(former), doctor)
    seen = set()
    pairs = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        frozen = frozenset(group)
        if frozen in seen:
            continue
        seen.add(frozen)
        pairs.append(
            {
                "name": key,
                "doctors": [
                    {
                        "doctor_id": doctor.get("doctor_id"),
                        "name": doctor.get("preferred_name"),
                        "npi": doctor.get("official_npi"),
                        "href": f"/doctors/{doctor.get('doctor_id')}",
                    }
                    for doctor in group.values()
                ],
            }
        )
    return pairs


_OUTCOME_META = [
    ("legacy", "Legacy master rows", "#8a9bb0", "gold"),
    ("verified_npi", "Linked by verified NPI", "#0d8065", "gold"),
    ("layer2", "Linked without a usable NPI", "#35a98c", "gold"),
    ("approved", "Approved by people", "#5b45c2", "gold"),
    ("waiting", "Waiting for people", "#c27a00", "queue"),
    ("unmatched", "Unmatched", "#94a3b8", "aside"),
    ("not_a_person", "Not a person", "#b8c3d1", "aside"),
]
_RESULT_META = [
    ("gold", "Golden doctors", "#1e5aa8"),
    ("queue", "Review queue", "#c27a00"),
    ("aside", "Set aside", "#94a3b8"),
]
_SOURCE_LABELS = {
    "legacy_master": "Legacy master",
    "crm": "CRM",
    "claims": "Claims",
    "events": "Events",
    "payments": "Payments",
    "hub": "Hub",
    "notes": "Notes",
    "nppes": "NPPES",
    "upload": "Upload",
}


def _outcome_key(decision: Dict[str, Any], source: str = "") -> str:
    action = decision.get("action")
    if action in NOT_PERSON:
        return "not_a_person"
    if action == "UNMATCHED":
        return "unmatched"
    if action in REVIEW or action in COMPLIANCE:
        return "waiting"
    if decision.get("decision_method") == "reviewer" or decision.get("reviewer"):
        return "approved"
    round_no = decision.get("round")
    if action == "PROVISIONAL" or (isinstance(round_no, int) and round_no >= 1):
        return "layer2"
    if source == "legacy_master" or decision.get("source_key") == "legacy_master":
        return "legacy"
    return "verified_npi"


def _resolution_flow(
    decisions: List[Dict[str, Any]],
    people: List[Dict[str, Any]],
    reviews_by_uid: Dict[str, str],
    record_for: Callable[[Dict[str, Any]], Dict[str, Any]],
    source_of: Callable[[Dict[str, Any]], str],
) -> Dict[str, Any]:
    source_order = ["legacy_master", "crm", "claims", "events", "payments", "hub", "notes"]

    def key_of(decision: Dict[str, Any]) -> str:
        return source_of(decision) or decision.get("source_key") or "unknown"

    present = []
    for key in source_order:
        rows = [d for d in decisions if key_of(d) == key]
        if rows:
            present.append((key, rows))
    extra_keys = sorted({key_of(d) for d in decisions if key_of(d) not in source_order and key_of(d) != "nppes"})
    for key in extra_keys:
        present.append((key, [d for d in decisions if key_of(d) == key]))

    by_outcome: Dict[str, List[Dict[str, Any]]] = {key: [] for key, *_rest in _OUTCOME_META}
    bands: Dict[str, int] = {}
    for _key, rows in present:
        for decision in rows:
            outcome = _outcome_key(decision, key_of(decision))
            by_outcome.setdefault(outcome, []).append(decision)
            bands[f"{key_of(decision)}|{outcome}"] = bands.get(f"{key_of(decision)}|{outcome}", 0) + 1

    def node_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [_item(row, record_for(row), reviews_by_uid) for row in rows]

    sources = [
        {
            "key": key,
            "label": _SOURCE_LABELS.get(key, key.replace("_", " ").title()),
            "count": len(rows),
            "items": node_items(rows),
        }
        for key, rows in present
    ]
    outcomes = []
    for key, label, color, result in _OUTCOME_META:
        rows = by_outcome.get(key) or []
        if not rows:
            continue
        outcomes.append({"key": key, "label": label, "color": color, "result": result, "count": len(rows), "items": node_items(rows)})
    results = []
    for key, label, color in _RESULT_META:
        rows = [row for outcome in outcomes if outcome["result"] == key for row in by_outcome.get(outcome["key"]) or []]
        if not rows and key == "gold":
            continue
        if not rows:
            continue
        results.append(
            {
                "key": key,
                "label": "golden doctors" if key == "gold" else label,
                "color": color,
                "count": len(rows),
                "doctors": len(people) if key == "gold" else None,
                "items": node_items(rows),
            }
        )
    return {
        "sources": sources,
        "outcomes": outcomes,
        "results": results,
        "bands": [{"from": pair.split("|", 1)[0], "to": pair.split("|", 1)[1], "count": count} for pair, count in bands.items()],
        "doctor_count": len(people),
        "row_count": len(decisions),
    }


def _item(decision: Dict[str, Any], record: Dict[str, Any], reviews_by_uid: Dict[str, str]) -> Dict[str, Any]:
    uid = decision.get("uid") or ""
    review_id = reviews_by_uid.get(uid)
    target = decision.get("target_id") or ""
    if review_id:
        href = f"/review/{review_id}"
    elif target:
        href = f"/doctors/{target}"
    else:
        href = "/review"
    amount = _money((record or {}).get("amount_cents"))
    return {
        "record_id": decision.get("record_id") or (record or {}).get("original_transaction_id") or uid,
        "uid": uid,
        "label": decision.get("target_label") or decision.get("display_name") or decision.get("record_id"),
        "action": decision.get("action"),
        "npi_status": decision.get("npi_status"),
        "amount": amount,
        "href": href,
        "source": decision.get("source_key") or (record or {}).get("source_id") or "",
    }


def _loaded_sources(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for source in state.get("sources_meta") or []:
        rows.append(
            {
                "source": source.get("source_id") or source.get("key"),
                "label": source.get("source_name") or source.get("label") or source.get("source_id"),
                "rows": source.get("row_count") or 0,
            }
        )
    return rows


def build_story(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("pipeline_cleared"):
        return {
            "needs_run": True,
            "headlines": [],
            "would_have_gone_wrong": [],
            "by_source": [],
            "conflicts": {},
            "alerts": [],
            "source_quality": [],
            "search": {},
            "loaded_sources": _loaded_sources(state),
            "resolution": None,
        }

    decisions: List[Dict[str, Any]] = list(state.get("match_decisions") or [])
    records = state.get("source_records") or {}
    doctors = list((state.get("doctors") or {}).values())
    reviews = list((state.get("reviews") or {}).values()) if isinstance(state.get("reviews"), dict) else list(state.get("reviews") or [])
    reviews_by_uid = {r.get("source_record_id"): r.get("review_id") for r in reviews if r.get("review_id")}
    metrics = state.get("pipeline_metrics") or {}
    search = state.get("search_quality") or {}

    def record_for(decision: Dict[str, Any]) -> Dict[str, Any]:
        return records.get(decision.get("uid") or "") or {}

    def source_of(decision: Dict[str, Any]) -> str:
        return decision.get("source_key") or record_for(decision).get("source_id") or ""

    people = [d for d in doctors if d.get("identity_status") != "reference" and d.get("npi_status") != "reference"]
    verified = [d for d in people if d.get("official_npi")]
    provisional = [d for d in people if not d.get("official_npi")]
    linked = [d for d in decisions if d.get("action") in LINKED]
    layer2 = [d for d in linked if isinstance(d.get("round"), int) and d.get("round") >= 1]
    wrong = [d for d in decisions if d.get("npi_status") in WRONG_NPI]
    payments = [d for d in decisions if source_of(d) == "payments"]
    payment_issues = [d for d in payments if d.get("action") in COMPLIANCE or d.get("npi_status") in WRONG_NPI]
    unresolved = [d for d in decisions if d.get("action") in REVIEW | COMPLIANCE | {"UNMATCHED"}]

    def pack(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        items = [_item(d, record_for(d), reviews_by_uid) for d in rows]
        return {
            "count": len(items),
            "amount": round(sum(item["amount"] for item in items), 2),
            "items": items[:80],
        }

    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for decision in wrong:
        by_type.setdefault(decision.get("npi_status") or "OTHER", []).append(decision)

    headlines = [
        {
            "key": "records_to_doctors",
            "label": "Records processed",
            "value": len(decisions),
            "secondary": int(metrics.get("doctors") or len(people)),
            "detail": f"{int(metrics.get('doctors') or len(people))} unique doctors identified",
            "items": pack(decisions)["items"],
        },
        {
            "key": "verified_vs_provisional",
            "label": "Doctors with verified NPI vs provisional",
            "value": len(verified),
            "secondary": len(provisional),
            "detail": f"{len(verified)} verified · {len(provisional)} provisional",
            "href": "/doctors",
        },
        {
            "key": "layer2",
            "label": "Records linked without a usable NPI",
            "value": len(layer2),
            "detail": "Linked in a later round, after a verified NPI was not available on the row",
            "items": pack(layer2)["items"],
        },
        {
            "key": "wrong_npis",
            "label": "Wrong NPIs caught",
            "value": len(wrong),
            "detail": " · ".join(f"{len(rows)} {label.replace('_', ' ').lower()}" for label, rows in sorted(by_type.items())) or "None in this run",
            "parts": [{"label": label.replace("_", " ").title(), "value": len(rows), "items": pack(rows)["items"]} for label, rows in sorted(by_type.items())],
            "items": pack(wrong)["items"],
        },
        {
            "key": "payment_issues",
            "label": "Payments with identity issues",
            "value": len(payment_issues),
            "amount": pack(payment_issues)["amount"],
            "detail": f"${pack(payment_issues)['amount']:,.2f} total",
            "items": pack(payment_issues)["items"],
        },
        {
            "key": "unresolved",
            "label": "Unresolved records",
            "value": len(unresolved),
            "detail": "Open identity, compliance, and unmatched rows",
            "items": pack(unresolved)["items"],
        },
    ]

    wrong_payments = [d for d in payments if d.get("npi_status") in {"MISMATCH", "GROUP_NPI", "INVALID", "PLACEHOLDER"}]
    claim_rows = [d for d in decisions if source_of(d) == "claims"]
    claim_fixed = [d for d in claim_rows if d.get("npi_status") in {"GROUP_NPI", "INVALID", "PLACEHOLDER", "MISMATCH"} and d.get("action") in LINKED]
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for doctor in people:
        key = _name_key(doctor.get("preferred_name") or "")
        if key:
            by_name.setdefault(key, []).append(doctor)
    same_name_pairs = []
    for key, group in by_name.items():
        distinct = {d.get("doctor_id") for d in group}
        if len(distinct) >= 2:
            same_name_pairs.append({"name": key, "doctors": [{"doctor_id": d.get("doctor_id"), "name": d.get("preferred_name"), "npi": d.get("official_npi"), "href": f"/doctors/{d.get('doctor_id')}"} for d in group]})

    would = [
        {
            "key": "payments",
            "label": "Payments whose stated NPI is wrong, a group NPI, invalid, or belongs to another doctor",
            "count": len(wrong_payments),
            "amount": pack(wrong_payments)["amount"],
            "items": pack(wrong_payments)["items"],
        },
        {
            "key": "claims",
            "label": "Claims credited to a group or invalid NPI, or otherwise not usable, that are now attributed to a doctor",
            "count": len(claim_fixed),
            "amount": 0,
            "items": pack(claim_fixed)["items"],
        },
        {
            "key": "same_name",
            "label": "Same-name doctor pairs that an exact-name match would have merged",
            "count": len(same_name_pairs),
            "amount": 0,
            "pairs": same_name_pairs,
        },
    ]

    sources: Dict[str, List[Dict[str, Any]]] = {}
    for decision in decisions:
        sources.setdefault(source_of(decision) or "unknown", []).append(decision)
    by_source = []
    for source, rows in sorted(sources.items()):
        def bucket(actions: set) -> Dict[str, Any]:
            chosen = [d for d in rows if d.get("action") in actions]
            return {"count": len(chosen), "items": pack(chosen)["items"]}

        by_source.append(
            {
                "source": source,
                "total": len(rows),
                "items": pack(rows)["items"],
                "linked": bucket(LINKED),
                "review": bucket(REVIEW),
                "compliance": bucket(COMPLIANCE),
                "unmatched": bucket({"UNMATCHED"}),
                "not_a_person": bucket(NOT_PERSON),
            }
        )

    suspicious = metrics.get("suspicious") or []
    conflicts = {
        "same_name_pairs": same_name_pairs,
        "npi_conflicts": pack([d for d in decisions if d.get("npi_status") == "MISMATCH"])["items"],
        "suspicious": suspicious,
    }

    alerts = []
    for decision in decisions:
        for change in decision.get("proposed_changes") or []:
            kind = change.get("change_type") or "change"
            action = "Update territory" if kind in {"move", "affiliation", "added_site"} else "Check payment before filing" if kind == "retirement" else "Review the proposed change"
            alerts.append(
                {
                    "record_id": decision.get("record_id"),
                    "kind": kind,
                    "quote": change.get("quote") or "",
                    "suggested_action": action,
                    "href": _item(decision, record_for(decision), reviews_by_uid)["href"],
                }
            )
        if decision.get("npi_status") == "DEACTIVATED":
            alerts.append(
                {
                    "record_id": decision.get("record_id"),
                    "kind": "deactivated_npi",
                    "quote": decision.get("reason") or "",
                    "suggested_action": "Check payment before filing",
                    "href": _item(decision, record_for(decision), reviews_by_uid)["href"],
                }
            )

    quality = []
    for source, rows in sorted(sources.items()):
        with_npi = sum(1 for d in rows if d.get("npi_status") in {"VERIFIED", "VERIFIED_AFTER_CLEANING"})
        quality.append(
            {
                "source": source,
                "total": len(rows),
                "verified_npi": with_npi,
                "wrong_npi": sum(1 for d in rows if d.get("npi_status") in WRONG_NPI),
                "duplicates": sum(1 for d in rows if d.get("action") == "DEDUPE"),
            }
        )

    practice_doctors = set()
    affiliations = state.get("affiliations") or {}
    if isinstance(affiliations, dict):
        for aff in affiliations.values():
            if aff.get("organization_name") and aff.get("doctor_id"):
                practice_doctors.add(aff["doctor_id"])
    gap_counts: Dict[str, int] = {}
    pcts: List[int] = []
    for doctor in people:
        pct, missing = completeness(doctor, has_practice=doctor.get("doctor_id") in practice_doctors)
        pcts.append(pct)
        for field in missing:
            gap_counts[field] = gap_counts.get(field, 0) + 1
    top_gap = max(gap_counts.items(), key=lambda item: item[1]) if gap_counts else ("none", 0)
    average_completeness = round(sum(pcts) / len(pcts)) if pcts else 0

    npi_breakdown = {
        "invalid": sum(1 for d in decisions if d.get("npi_status") == "INVALID"),
        "placeholder": sum(1 for d in decisions if d.get("npi_status") == "PLACEHOLDER"),
        "group": sum(1 for d in decisions if d.get("npi_status") == "GROUP_NPI"),
        "deactivated": sum(1 for d in decisions if d.get("npi_status") == "DEACTIVATED"),
        "mismatch": sum(1 for d in decisions if d.get("npi_status") in {"MISMATCH", "REVIEW"}),
    }
    metrics_block = metrics if isinstance(metrics, dict) else {}
    masters = {
        "merges": int(metrics_block.get("merges") or 0),
        "splits": int(metrics_block.get("splits") or 0),
        "new": int(metrics_block.get("new_masters") or 0),
    }
    masters["total"] = masters["merges"] + masters["splits"] + masters["new"]
    compliance_payments = [d for d in payments if d.get("action") in COMPLIANCE]
    payment_pack = pack(compliance_payments)
    claim_problem = [
        d
        for d in decisions
        if source_of(d) == "claims" and d.get("npi_status") in {"GROUP_NPI", "INVALID", "PLACEHOLDER", "MISMATCH", "REVIEW"}
    ]
    claim_problem_fixed = [d for d in claim_problem if d.get("action") in LINKED]
    naive_pairs = _naive_name_pairs(people)

    for alert in alerts:
        if not alert.get("title"):
            alert["title"] = f"{alert.get('record_id')}: {(alert.get('kind') or 'change').replace('_', ' ')}"

    present_quality = []
    for source, rows in sorted(sources.items()):
        total = len(rows) or 1
        present = sum(1 for d in rows if d.get("npi_status") not in {None, "", "MISSING"})
        valid = sum(1 for d in rows if d.get("npi_status") in {"VERIFIED", "VERIFIED_AFTER_CLEANING"})
        present_quality.append(
            {
                "source": source,
                "total": len(rows),
                "verified_npi": valid,
                "wrong_npi": sum(1 for d in rows if d.get("npi_status") in WRONG_NPI),
                "duplicates": sum(1 for d in rows if d.get("action") == "DEDUPE"),
                "present_pct": round(100 * present / total),
                "valid_pct": round(100 * valid / total),
            }
        )

    return {
        "needs_run": False,
        "headlines": headlines,
        "would_have_gone_wrong": would,
        "by_source": by_source,
        "conflicts": conflicts,
        "alerts": alerts[:40],
        "source_quality": present_quality or quality,
        "loaded_sources": _loaded_sources(state),
        "cards": {
            "doctors": len(people),
            "rows": len(decisions),
            "verified": len(verified),
            "provisional": len(provisional),
            "npi_issues": npi_breakdown,
            "npi_issue_total": sum(npi_breakdown.values()),
            "payments_at_risk": {"count": payment_pack["count"], "amount": payment_pack["amount"], "items": payment_pack["items"]},
            "masters_fixed": masters,
            "completeness": {
                "average": average_completeness,
                "top_gap": top_gap[0],
                "top_gap_count": top_gap[1],
            },
        },
        "impact": {
            "payment_amount": payment_pack["amount"],
            "payment_count": payment_pack["count"],
            "payment_items": payment_pack["items"],
            "claims_problem": len(claim_problem),
            "claims_fixed": len(claim_problem_fixed),
            "claims_review": len(claim_problem) - len(claim_problem_fixed),
            "claims_items": pack(claim_problem)["items"],
            "false_merge_pairs": len(naive_pairs),
            "pairs": naive_pairs,
        },
        "resolution": _resolution_flow(decisions, people, reviews_by_uid, record_for, source_of),
        "search": {
            "filter_only": search.get("filter_only") or 0,
            "semantic_only": search.get("semantic_only") or 0,
            "both": search.get("both") or 0,
            "learned_value_links": search.get("learned_value_links") or 0,
            "semantic_status": search.get("semantic_status") or "skipped",
            "vector_store": search.get("vector_store") or "",
        },
        "rounds": state.get("cleanup_rounds") or [],
    }
