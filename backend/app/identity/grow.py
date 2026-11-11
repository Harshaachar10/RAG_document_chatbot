"""Round assignment for seed-and-grow.

Round 0 links records whose person NPI is VERIFIED or VERIFIED_AFTER_CLEANING
(and deactivated registry NPIs that still name the same person). Those links
add known values. Later rounds search with filter routes. A route that needs
a value learned from an earlier auto-link is marked as learned. Semantic
neighbors are recorded and never override a hard stop or the scorer.

Unconfirmed matches do not add known values.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from app.identity.search_plan import template_plan
from app.identity.splink_model import match_probability
from app.identity.standardize import nickname_equivalent, soundex

VERIFIED_STATUSES = {"VERIFIED", "VERIFIED_AFTER_CLEANING"}
SEED_STATUSES = VERIFIED_STATUSES | {"DEACTIVATED"}
LINK_ACTIONS = {"AUTO_LINK", "PROVISIONAL"}


def _tokens(value: str) -> Set[str]:
    stop = {"the", "of", "and", "at", "for", "cc", "md", "group"}
    return {tok for tok in re.sub(r"[^a-z0-9\s]", " ", (value or "").lower()).split() if len(tok) > 2 and tok not in stop}


def _org_overlap(left: str, right: str) -> bool:
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return False
    return bool(a & b)


class KnownValue:
    def __init__(self, value: str, round_added: int, source: str) -> None:
        self.value = value
        self.round_added = round_added
        self.source = source


class Known:
    def __init__(self) -> None:
        self.surnames: List[KnownValue] = []
        self.firsts: List[KnownValue] = []
        self.states: List[KnownValue] = []
        self.cities: List[KnownValue] = []
        self.orgs: List[KnownValue] = []
        self.phones: List[KnownValue] = []
        self.emails: List[KnownValue] = []
        self.licenses: List[KnownValue] = []
        self.zip3: List[KnownValue] = []
        self.specialties: List[KnownValue] = []

    def add(self, bucket: str, value: str, round_added: int, source: str) -> None:
        text = (value or "").strip()
        if not text:
            return
        key = text.lower()
        current: List[KnownValue] = getattr(self, bucket)
        if any(item.value.lower() == key for item in current):
            return
        current.append(KnownValue(text, round_added, source))

    def has(self, bucket: str, value: str) -> Optional[KnownValue]:
        key = (value or "").strip().lower()
        if not key:
            return None
        for item in getattr(self, bucket):
            if item.value.lower() == key:
                return item
        return None


def _seed_known(doctor: Dict[str, Any]) -> Known:
    known = Known()
    name = doctor.get("name") or {}
    known.add("surnames", name.get("last_norm") or "", 0, "nppes")
    for former in doctor.get("former_lasts") or []:
        known.add("surnames", former, 0, "nppes")
    for part in name.get("last_parts") or []:
        known.add("surnames", part, 0, "nppes")
    known.add("firsts", name.get("first_norm") or "", 0, "nppes")
    known.add("states", doctor.get("state") or "", 0, "nppes")
    known.add("cities", doctor.get("city") or "", 0, "nppes")
    known.add("orgs", doctor.get("organization") or "", 0, "nppes")
    known.add("phones", doctor.get("phone") or "", 0, "nppes")
    known.add("emails", doctor.get("email") or "", 0, "nppes")
    known.add("zip3", (doctor.get("postal") or "")[:3], 0, "nppes")
    known.add("specialties", doctor.get("specialty_family") or doctor.get("specialty") or "", 0, "nppes")
    for lic in doctor.get("licenses") or []:
        if lic.get("number"):
            known.add("licenses", f"{lic.get('number')}|{lic.get('state') or ''}".lower(), 0, "nppes")
            known.add("states", lic.get("state") or "", 0, "nppes")
    return known


def _absorb(known: Known, std: Dict[str, Any], round_added: int, source: str) -> bool:
    before = sum(len(getattr(known, name)) for name in ("surnames", "firsts", "states", "cities", "orgs", "phones", "emails", "licenses"))
    name = std.get("name") or {}
    known.add("surnames", name.get("last_norm") or "", round_added, source)
    for part in name.get("last_parts") or []:
        known.add("surnames", part, round_added, source)
    known.add("firsts", name.get("first_norm") or "", round_added, source)
    known.add("states", std.get("state") or "", round_added, source)
    known.add("cities", std.get("city") or "", round_added, source)
    known.add("orgs", std.get("organization") or "", round_added, source)
    known.add("phones", std.get("phone") or "", round_added, source)
    known.add("emails", std.get("email") or "", round_added, source)
    known.add("zip3", std.get("zip3") or "", round_added, source)
    known.add("specialties", std.get("specialty") or "", round_added, source)
    if std.get("license_no"):
        known.add("licenses", f"{std.get('license_no')}|{std.get('license_state') or ''}".lower(), round_added, source)
    after = sum(len(getattr(known, name)) for name in ("surnames", "firsts", "states", "cities", "orgs", "phones", "emails", "licenses"))
    return after > before


def _state_ok(std: Dict[str, Any], known: Known) -> Optional[KnownValue]:
    state = (std.get("state") or "").upper()
    if not state:
        return KnownValue("", 0, "missing")
    for item in known.states:
        if item.value.upper() == state:
            return item
    return None


def explain_routes(std: Dict[str, Any], doctor: Dict[str, Any], known: Known) -> List[Dict[str, Any]]:
    """Filter routes from the source profile. Each hit records whether it used a learned value."""
    hits: List[Dict[str, Any]] = []
    name = std.get("name") or {}
    last = name.get("last_norm") or ""
    first = name.get("first_norm") or ""
    state_hit = _state_ok(std, known)
    doc_last = ((doctor.get("name") or {}).get("last_norm")) or ""
    surname_known = None
    if last:
        surname_known = known.has("surnames", last)
        if not surname_known and soundex(last) and soundex(last) == soundex(doc_last):
            surname_known = known.has("surnames", doc_last)

    def add(route: str, learned_from: Optional[KnownValue], detail: str) -> None:
        # A value counts as learned when it was not on the NPPES seed.
        learned = bool(learned_from and learned_from.source not in {"nppes", "missing", ""})
        hits.append(
            {
                "route": route,
                "learned": learned,
                "learned_round": (learned_from.round_added if learned_from else 0),
                "detail": detail,
            }
        )

    if surname_known and state_hit and (std.get("state") or "") and state_hit.source != "missing":
        learned_from = surname_known if surname_known.round_added > state_hit.round_added else state_hit
        if last and doc_last and last != doc_last and last not in (doctor.get("former_lasts") or []):
            add("phonetic_surname_state", learned_from, "Phonetic surname and state.")
        else:
            add("phonetic_surname_state", learned_from, "Surname and state.")
    if surname_known and surname_known.value.lower() != doc_last and state_hit:
        add("former_surname_state", surname_known if surname_known.round_added else state_hit, "Former surname and state.")

    first_known = None
    if first:
        first_known = known.has("firsts", first)
        if not first_known:
            for item in known.firsts:
                if nickname_equivalent(first, item.value):
                    first_known = item
                    break
    zip_known = known.has("zip3", std.get("zip3") or "")
    spec_known = known.has("specialties", std.get("specialty") or "")
    if first_known and zip_known and spec_known:
        learned_from = max([first_known, zip_known, spec_known], key=lambda item: item.round_added)
        add("first_zip3_specialty", learned_from, "First name, ZIP3, and specialty.")

    swapped_last = first
    swapped_first = last
    if swapped_last and known.has("surnames", swapped_last) and swapped_first and (
        known.has("firsts", swapped_first) or any(nickname_equivalent(swapped_first, item.value) for item in known.firsts)
    ):
        add("nickname_and_swapped", known.has("surnames", swapped_last), "Swapped name order.")
    elif first_known and surname_known and (nickname_equivalent(first, ((doctor.get("name") or {}).get("first_norm") or "")) or first == ((doctor.get("name") or {}).get("first_norm"))):
        learned_from = first_known if first_known.round_added >= (surname_known.round_added if surname_known else 0) else surname_known
        if state_hit is not None:
            add("nickname_and_swapped", learned_from, "Nickname or exact given name with surname.")

    phone = std.get("phone") or ""
    phone_known = known.has("phones", phone) if phone else None
    if phone_known:
        add("phone", phone_known, "Phone number.")
    email = std.get("email") or ""
    email_known = known.has("emails", email) if email else None
    if email_known:
        add("email", email_known, "Email.")
    if std.get("license_no"):
        lic_key = f"{std.get('license_no')}|{std.get('license_state') or ''}".lower()
        lic_known = known.has("licenses", lic_key)
        if lic_known:
            add("license_state", lic_known, "License and state.")
    org = std.get("organization") or ""
    if org and surname_known:
        org_hit = None
        for item in known.orgs:
            if _org_overlap(org, item.value):
                org_hit = item
                break
        if org_hit:
            learned_from = org_hit if org_hit.round_added >= surname_known.round_added else surname_known
            add("organization_surname", learned_from, "Organization and surname.")
    return hits


def score_pair_splink(std: Dict[str, Any], doctor: Dict[str, Any], *, embedding_band: Optional[str] = None, phone_shared: bool = False) -> Dict[str, Any]:
    name = std.get("name") or {}
    doc_name = doctor.get("name") or {}
    last = name.get("last_norm") or ""
    doc_last = doc_name.get("last_norm") or ""
    first = name.get("first_norm") or ""
    doc_first = doc_name.get("first_norm") or ""
    levels: List[Dict[str, Any]] = []
    if last and doc_last:
        if last == doc_last:
            levels.append({"name": "surname_exact", "agree": True, "u_override": 0.004 if _rare(doc_last) else None})
        elif last in (doctor.get("former_lasts") or []) or doc_last in (name.get("last_parts") or []):
            levels.append({"name": "surname_former", "agree": True})
        else:
            levels.append({"name": "surname_exact", "agree": False})
    if first and doc_first:
        if first == doc_first:
            levels.append({"name": "first_exact", "agree": True})
        elif nickname_equivalent(first, doc_first):
            levels.append({"name": "first_nickname", "agree": True})
        elif len(first) == 1 and doc_first.startswith(first):
            levels.append({"name": "first_initial", "agree": True})
        else:
            levels.append({"name": "first_exact", "agree": False})
    rec_state = (std.get("state") or "").upper()
    doc_state = (doctor.get("state") or "").upper()
    if rec_state and doc_state:
        levels.append({"name": "state_agree", "agree": rec_state == doc_state})
    rec_city = (std.get("city") or "").lower()
    doc_city = (doctor.get("city") or "").lower()
    if rec_city and doc_city:
        levels.append({"name": "city_agree", "agree": rec_city == doc_city})
    rec_spec = std.get("specialty") or ""
    doc_spec = doctor.get("specialty_family") or ""
    if rec_spec and doc_spec:
        if rec_spec == doc_spec:
            levels.append({"name": "specialty_agree", "agree": True})
        else:
            levels.append({"name": "specialty_conflict", "agree": True})
    phone = std.get("phone") or ""
    if phone and doctor.get("phone"):
        if phone == doctor.get("phone"):
            levels.append({"name": "phone_shared" if phone_shared else "phone_unique", "agree": True})
        else:
            levels.append({"name": "phone_unique", "agree": False})
    if (std.get("email") or "") and doctor.get("email"):
        levels.append({"name": "email_exact", "agree": std.get("email") == doctor.get("email")})
    if std.get("organization") and doctor.get("organization"):
        levels.append({"name": "org_agree", "agree": _org_overlap(std.get("organization") or "", doctor.get("organization") or "")})
    if embedding_band == "high":
        levels.append({"name": "embedding_high", "agree": True})
    elif embedding_band == "mid":
        levels.append({"name": "embedding_mid", "agree": True})
    return match_probability(levels)


def _rare(last: str) -> bool:
    return last not in {"smith", "lee", "park", "sharma", "harris", "nowak"}


def assign_rounds(
    decisions: List[Dict[str, Any]],
    catalog: Dict[str, Any],
    *,
    semantic_hits: Optional[Dict[str, List[str]]] = None,
    max_rounds: int = 5,
) -> Dict[str, Any]:
    semantic_hits = semantic_hits or {}
    by_id = catalog.get("by_id") or {}
    for decision in decisions:
        decision["round"] = None
        decision["found_by"] = []
        decision["route"] = ""
        decision["learned_value"] = False
        decision["routes"] = []
    known: Dict[str, Known] = {}
    for doctor in catalog.get("people") or []:
        known[doctor["doctor_id"]] = _seed_known(doctor)

    records_by_uid = {}
    for decision in decisions:
        std = decision.get("standardized") or {}
        records_by_uid[decision["uid"]] = std
        decision.setdefault("round", None)
        decision.setdefault("found_by", [])
        decision.setdefault("route", "")
        decision.setdefault("learned_value", False)

    def stamp(decision: Dict[str, Any], round_no: int, routes: List[Dict[str, Any]], semantic: bool) -> None:
        found = []
        if routes:
            found.append("filter")
        if semantic:
            found.append("semantic")
        if not found:
            found.append("filter")
        decision["round"] = round_no
        decision["found_by"] = found
        decision["route"] = routes[0]["route"] if routes else ("semantic" if semantic else "")
        decision["routes"] = routes
        decision["learned_value"] = bool(routes) and all(item.get("learned") for item in routes)
        if semantic and not routes:
            decision["found_by"] = ["semantic"]
            decision["route"] = "semantic"
        elif semantic and routes:
            decision["found_by"] = ["filter", "semantic"]
        plan = template_plan(
            decision.get("standardized"),
            reason="Template plan from fields on the row. Repeated plans skip a model call.",
        )
        if plan.get("valid"):
            decision["search_plan"] = plan
        else:
            decision["search_plan"] = None
            decision["search_plan_errors"] = plan.get("errors") or []

    # Round 0 — verified NPI seeds. Wrong, group, placeholder, and invalid NPIs do not seed.
    for decision in decisions:
        if decision.get("action") not in LINK_ACTIONS:
            continue
        if decision.get("npi_status") not in SEED_STATUSES:
            continue
        doctor = by_id.get(decision.get("target_id") or "")
        if not doctor:
            continue
        if decision.get("target_npi") and decision.get("stated_npi") and decision["target_npi"] != decision["stated_npi"]:
            continue
        stamp(decision, 0, [{"route": "verified_npi", "learned": False, "learned_round": 0, "detail": "Verified NPI seed."}], False)
        _absorb(known[doctor["doctor_id"]], decision.get("standardized") or {}, 0, decision.get("record_id") or "")

    round_rows = [{"round": 0, "linked": sum(1 for d in decisions if d.get("round") == 0), "new_values": 0, "stop_reason": ""}]
    for round_no in range(1, max_rounds + 1):
        linked = 0
        new_values = 0
        pending = [
            d
            for d in decisions
            if d.get("round") is None and d.get("target_id") and d.get("action") in LINK_ACTIONS | {"REVIEW", "COMPLIANCE_REVIEW"}
        ]
        # Stable order so the same input always walks records the same way.
        pending.sort(key=lambda d: (d.get("source_key") or "", d.get("record_id") or ""))
        stamped: List[Dict[str, Any]] = []
        for decision in pending:
            doctor = by_id.get(decision.get("target_id") or "")
            if not doctor:
                continue
            routes = explain_routes(decision.get("standardized") or {}, doctor, known[doctor["doctor_id"]])
            semantic = decision.get("target_id") in (semantic_hits.get(decision["uid"]) or [])
            if not routes and not semantic:
                continue
            # Reviews are visible once found, but they do not teach new values.
            stamp(decision, round_no, routes, semantic)
            stamped.append(decision)
        for decision in stamped:
            if decision.get("action") in LINK_ACTIONS:
                doctor = by_id.get(decision.get("target_id") or "")
                if doctor and _absorb(known[doctor["doctor_id"]], decision.get("standardized") or {}, round_no, decision.get("record_id") or ""):
                    new_values += 1
                linked += 1
        round_rows.append({"round": round_no, "linked": linked, "new_values": new_values, "reviews": sum(1 for d in stamped if d.get("action") not in LINK_ACTIONS)})
        if linked == 0 and new_values == 0:
            round_rows[-1]["stop_reason"] = "No new links or values."
            break
    else:
        round_rows.append({"round": max_rounds, "linked": 0, "new_values": 0, "stop_reason": "Reached the configured maximum rounds."})

    for decision in decisions:
        if decision.get("round") is not None:
            continue
        semantic = decision.get("target_id") in (semantic_hits.get(decision["uid"]) or [])
        decision["round"] = None
        decision["found_by"] = ["semantic"] if semantic else []
        decision["route"] = "semantic" if semantic else ""
        decision["learned_value"] = False

    known_export: Dict[str, List[Dict[str, Any]]] = {}
    for doctor_id, bucket in known.items():
        rows = []
        for name, label in (
            ("surnames", "name"),
            ("firsts", "name"),
            ("orgs", "practice"),
            ("cities", "address"),
            ("states", "address"),
            ("phones", "phone"),
            ("emails", "email"),
            ("licenses", "license"),
        ):
            for item in getattr(bucket, name):
                if item.source == "nppes" and not item.value:
                    continue
                rows.append(
                    {
                        "kind": label,
                        "field": name,
                        "value": item.value,
                        "round": item.round_added,
                        "source": item.source,
                        "status": "current" if item.round_added == 0 else "learned",
                    }
                )
        known_export[doctor_id] = rows

    filter_only = 0
    semantic_only = 0
    both = 0
    learned = 0
    for decision in decisions:
        if decision.get("action") not in LINK_ACTIONS:
            continue
        found = set(decision.get("found_by") or [])
        if found == {"filter"}:
            filter_only += 1
        elif found == {"semantic"}:
            semantic_only += 1
        elif "filter" in found and "semantic" in found:
            both += 1
        if decision.get("learned_value"):
            learned += 1

    return {
        "rounds": round_rows,
        "known_values": known_export,
        "search": {
            "filter_only": filter_only,
            "semantic_only": semantic_only,
            "both": both,
            "learned_value_links": learned,
            "semantic_status": "skipped" if not semantic_hits else "used",
        },
    }
