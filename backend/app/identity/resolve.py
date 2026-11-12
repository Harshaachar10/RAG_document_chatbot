"""Match source records to doctors.

Candidates are NPPES people or a provisional person built from corroborating
source evidence. Source rows are evidence. They are never match candidates.
Organization NPIs never become doctors. Matching does not read answer keys.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.identity.config import DEMO_IDENTITY_REVIEW_RECORDS
from app.identity.notes_extract import extract_note
from app.identity.redact import redact_text
from app.identity.standardize import nickname_equivalent, parse_person_name, specialty_family, specialty_label

GENERATIONAL = {"JR", "SR", "II", "III", "IV"}
ORG_WORDS = {"cancer", "oncology", "center", "clinic", "institute", "associates", "hospital", "group", "university"}
NON_PERSON_PHRASES = (
    "office staff",
    "front desk",
    "billing office",
    "clinic staff",
    "tbd speaker",
    "tbd",
    "to be determined",
    "unknown",
)


def _master_id(*parts: str) -> str:
    payload = "|".join((p or "").strip().lower() for p in parts)
    return "HCP-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8].upper()


def _org_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _org_tokens(value: str) -> set:
    text = re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())
    stop = {"the", "of", "and", "at", "for", "cc"}
    return {tok for tok in text.split() if tok not in stop and len(tok) > 2}


def _same_name_pair(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    na, nb = a.get("name") or {}, b.get("name") or {}
    if not na.get("last_norm") or na.get("last_norm") != nb.get("last_norm"):
        return False
    if na.get("first_norm") and na.get("first_norm") == nb.get("first_norm"):
        return True
    sa = set(na.get("suffixes") or []) & GENERATIONAL
    sb = set(nb.get("suffixes") or []) & GENERATIONAL
    return bool(sa and sb and sa != sb and na.get("first_norm") == nb.get("first_norm"))


def _pretty_phrase(value: str) -> str:
    return " ".join(_pretty(token) for token in (value or "").split())


def _pretty(token: str) -> str:
    if not token:
        return ""
    parts = re.split(r"([-'’])", token)
    return "".join(part.capitalize() if part.isalpha() else part for part in parts)


def _display(name: Dict[str, Any], credential: str = "") -> str:
    first = _pretty(name.get("first") or "")
    last = _pretty(name.get("last") or "")
    suffixes = [s.title() if s in {"JR", "SR"} else s for s in (name.get("suffixes") or [])]
    base = " ".join(p for p in [first, last, *suffixes] if p)
    if credential and credential.upper() not in base.upper():
        return base
    return base or name.get("display") or ""


def build_catalog(nppes_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    people: List[Dict[str, Any]] = []
    orgs: List[Dict[str, Any]] = []
    for npi, ref in nppes_index.items():
        if str(ref.get("entity_type")) == "2":
            orgs.append(ref)
            continue
        name = ref.get("name") or {}
        licenses = list(ref.get("licenses") or [])
        primary_license = licenses[0]["number"] if licenses else ""
        suffix = (name.get("suffixes") or [""])[0]
        doctor = {
            "doctor_id": _master_id(
                name.get("first_norm") or "",
                name.get("last_norm") or "",
                suffix,
                ref.get("city") or "",
                primary_license,
                ref.get("state") or "",
            ),
            "npi": npi,
            "provisional": False,
            "name": name,
            "former_lasts": [p for p in [ref.get("other_last") or "", *(name.get("last_parts") or [])] if p],
            "credentials": [c for c in [ref.get("credential") or "", *(name.get("credentials") or [])] if c],
            "specialty": ref.get("specialty_label") or specialty_label(ref.get("taxonomy")) or ref.get("specialty") or "",
            "specialty_family": ref.get("specialty") or "",
            "organization": ref.get("organization") or "",
            "address": ref.get("address") or "",
            "city": ref.get("city") or "",
            "state": ref.get("state") or "",
            "postal": ref.get("postal") or "",
            "phone": ref.get("phone") or "",
            "email": "",
            "licenses": licenses,
            "deactivated": bool(ref.get("deactivated")),
            "last_update": ref.get("last_update") or "",
            "display_name": _display(name, ref.get("credential") or ""),
        }
        # Hyphen parts of the legal surname are former-name evidence, but the
        # full surname itself should not count as a different former name.
        full = name.get("last_norm") or ""
        doctor["former_lasts"] = [p for p in doctor["former_lasts"] if p and p != full]
        people.append(doctor)

    seen = {}
    for doc in people:
        seen.setdefault(doc["doctor_id"], 0)
        seen[doc["doctor_id"]] += 1
        if seen[doc["doctor_id"]] > 1:
            doc["doctor_id"] = f"{doc['doctor_id']}-{seen[doc['doctor_id']]}"

    phone_counts: Dict[str, int] = defaultdict(int)
    for doc in people:
        if doc.get("phone"):
            phone_counts[doc["phone"]] += 1
    license_owner: Dict[str, str] = {}
    for doc in people:
        for lic in doc.get("licenses") or []:
            if lic.get("number"):
                license_owner[lic["number"].lower()] = doc["doctor_id"]
    by_npi = {d["npi"]: d for d in people if d.get("npi")}
    by_id = {d["doctor_id"]: d for d in people}
    last_update_hits: Dict[str, List[str]] = defaultdict(list)
    for doc in people:
        if doc.get("last_update"):
            last_update_hits[doc["last_update"]].append(doc["doctor_id"])
    for doc in people:
        if doc.get("organization"):
            continue
        for org in orgs:
            if _org_key(doc.get("address") or "") and _org_key(doc.get("address")) == _org_key(org.get("address") or ""):
                doc["organization"] = _pretty_phrase(org.get("organization") or "")
                break
    org_names = {_org_key(o.get("organization") or "") for o in orgs}
    org_npis = {o.get("npi") for o in orgs if o.get("npi")}
    return {
        "people": people,
        "orgs": orgs,
        "by_npi": by_npi,
        "by_id": by_id,
        "phone_counts": phone_counts,
        "license_owner": license_owner,
        "last_update_hits": last_update_hits,
        "org_names": org_names,
        "org_npis": org_npis,
    }


def _last_agree(rec_name: Dict[str, Any], doctor: Dict[str, Any]) -> Tuple[str, str]:
    last = rec_name.get("last_norm") or ""
    doc_last = (doctor.get("name") or {}).get("last_norm") or ""
    formers = set(doctor.get("former_lasts") or [])
    parts = set((doctor.get("name") or {}).get("last_parts") or [])
    if last and doc_last and last == doc_last:
        return "agree", "surname"
    if last and (last in formers or last in parts):
        return "agree", "former_surname"
    doc_formers = formers | parts
    rec_parts = set(rec_name.get("last_parts") or [])
    if doc_last and (doc_last in rec_parts):
        return "agree", "former_surname"
    if last and doc_last and _close_text(last, doc_last) and len(last) >= 5:
        return "close", "surname_typo"
    if last and doc_last:
        return "conflict", "surname"
    return "missing", "surname"


def _close_text(a: str, b: str) -> bool:
    if not a or not b or a == b:
        return False
    if abs(len(a) - len(b)) > 2:
        return False
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a, b).ratio() >= 0.8


def _edit_one(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if a == b:
        return True
    # substitution / insertion
    i = j = diffs = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        diffs += 1
        if diffs > 1:
            return False
        if len(a) == len(b):
            i += 1
            j += 1
        elif len(a) > len(b):
            i += 1
        else:
            j += 1
    return True


def _swapped_name(std: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = std.get("name") or {}
    first, last = name.get("first") or "", name.get("last") or ""
    if not first or not last:
        return None
    return parse_person_name(f"{last} {first}")


def score_doctor(
    std: Dict[str, Any],
    doctor: Dict[str, Any],
    catalog: Dict[str, Any],
    *,
    stated_npi: str = "",
    npi_owner_id: str = "",
) -> Dict[str, Any]:
    contributions: List[Dict[str, Any]] = []
    hard_stops: List[Dict[str, str]] = []
    name = std.get("name") or {}
    alt = _swapped_name(std)
    primary = _score_name(name, std, doctor, catalog, stated_npi, npi_owner_id, contributions, hard_stops)
    if alt and ((alt.get("first_norm"), alt.get("last_norm")) != (name.get("first_norm"), name.get("last_norm"))):
        alt_contrib: List[Dict[str, Any]] = []
        alt_stops: List[Dict[str, str]] = []
        alt_score = _score_name(alt, std, doctor, catalog, stated_npi, npi_owner_id, alt_contrib, alt_stops)
        if alt_score > primary:
            return _finalize(alt_score, alt_contrib, alt_stops, doctor)
    return _finalize(primary, contributions, hard_stops, doctor)


def _score_name(
    name: Dict[str, Any],
    std: Dict[str, Any],
    doctor: Dict[str, Any],
    catalog: Dict[str, Any],
    stated_npi: str,
    npi_owner_id: str,
    contributions: List[Dict[str, Any]],
    hard_stops: List[Dict[str, str]],
) -> float:
    doc_name = doctor.get("name") or {}
    points = 0.0
    name_only = True

    def add(field: str, status: str, delta: float, detail: str) -> None:
        nonlocal points
        contributions.append({"field": field, "status": status, "delta": round(delta, 4), "detail": detail})
        points += delta

    last_status, last_detail = _last_agree(name, doctor)
    if last_status == "agree" and last_detail == "surname":
        add("surname", "agree", 0.22, "Surname matches")
    elif last_status == "agree":
        add("former_surname", "agree", 0.18, "Former or hyphenated surname matches")
    elif last_status == "close":
        add("surname", "agree", 0.12, "Surname differs by one character")
    elif last_status == "conflict":
        add("surname", "conflict", -0.16, "Surname conflicts")

    first = name.get("first_norm") or ""
    doc_first = doc_name.get("first_norm") or ""
    first_strong = False
    if first and doc_first and first == doc_first and len(first) > 1:
        add("first_name", "agree", 0.16, "First name matches")
        first_strong = True
    elif first and doc_first and len(first) > 1 and nickname_equivalent(first, doc_first):
        add("nickname", "agree", 0.13, "First name is a known nickname")
        first_strong = True
    elif first and doc_first and len(first) == 1 and first[0] == doc_first[0]:
        add("first_name", "weak", 0.02, "First initial only")
    elif first and doc_first and len(first) > 1 and len(doc_first) > 1:
        add("first_name", "conflict", -0.2, "First name conflicts")
        hard_stops.append({"code": "FIRST_NAME", "message": f"First name conflicts ({first} vs {doc_first})"})

    rec_suf = set(name.get("suffixes") or []) & GENERATIONAL
    doc_suf = set(doc_name.get("suffixes") or []) & GENERATIONAL
    if rec_suf and doc_suf and rec_suf == doc_suf:
        add("suffix", "agree", 0.08, "Generational suffix matches")
    elif rec_suf and doc_suf and rec_suf != doc_suf:
        add("suffix", "conflict", -0.2, "Generational suffix conflicts")
        hard_stops.append({"code": "SUFFIX", "message": "Jr/Sr suffix conflicts"})
    else:
        add("suffix", "missing", 0.0, "Suffix not on both sides")

    rec_cred = {c.upper() for c in (name.get("credentials") or [])}
    doc_cred = {c.upper() for c in (doctor.get("credentials") or [])}
    if rec_cred and doc_cred and rec_cred & doc_cred:
        add("credential", "agree", 0.04, "Credential matches")
    elif rec_cred and doc_cred:
        add("credential", "conflict", -0.02, "Credential differs")
    else:
        add("credential", "missing", 0.0, "Credential missing")

    rec_family = std.get("specialty") or ""
    doc_family = doctor.get("specialty_family") or ""
    if rec_family and doc_family and rec_family == doc_family:
        add("specialty", "agree", 0.08, "Specialty family matches")
        name_only = False
    elif rec_family and doc_family:
        add("specialty", "conflict", -0.12, f"Specialty conflict {rec_family} vs {doc_family}")
        name_only = False
    else:
        add("specialty", "missing", 0.0, "Specialty missing")

    rec_org = _org_tokens(std.get("organization") or "")
    doc_org = _org_tokens(doctor.get("organization") or "")
    for known in doctor.get("known_orgs") or []:
        doc_org |= _org_tokens(known)
    org_agree = bool(rec_org and (rec_org & doc_org or _org_key(std.get("organization") or "") == _org_key(doctor.get("organization") or "")))
    if org_agree:
        add("organization", "agree", 0.1, "Organization matches")
        name_only = False
    elif rec_org and doc_org:
        add("organization", "conflict", -0.04, "Organization differs")
        name_only = False
    else:
        add("organization", "missing", 0.0, "Organization missing")

    rec_city = (std.get("city") or "").lower()
    rec_state = (std.get("state") or "").upper()
    doc_city = (doctor.get("city") or "").lower()
    doc_state = (doctor.get("state") or "").upper()
    licensed_states = {((lic.get("state") or "").upper()) for lic in doctor.get("licenses") or []}
    if rec_city and doc_city and rec_city == doc_city and (not rec_state or rec_state == doc_state):
        add("location", "agree", 0.1, "City and state match")
        name_only = False
    elif rec_state and (rec_state == doc_state or rec_state in licensed_states):
        add("location", "agree", 0.04, "State or licensed state matches")
        name_only = False
    elif rec_state and doc_state and rec_state != doc_state and rec_state not in licensed_states:
        add("location", "conflict", -0.12, "Location conflicts")
        name_only = False
        if rec_family and doc_family and rec_family != doc_family:
            hard_stops.append({"code": "SPECIALTY_GEO", "message": "Specialty and location both conflict"})
    else:
        add("location", "missing", 0.0, "Location missing")

    phone = std.get("phone") or ""
    if phone and phone == (doctor.get("phone") or ""):
        shared = catalog["phone_counts"].get(phone, 0) > 1
        add("phone", "weak" if shared else "agree", 0.015 if shared else 0.06, "Shared clinic phone" if shared else "Phone matches")
        name_only = False
    elif phone and doctor.get("phone"):
        add("phone", "conflict", -0.02, "Phone differs")
    else:
        add("phone", "missing", 0.0, "Phone missing")

    if std.get("email") and std.get("email") == (doctor.get("email") or ""):
        add("email", "agree", 0.1, "Email matches")
        name_only = False
    else:
        add("email", "missing", 0.0, "Email missing")

    lic = (std.get("license_no") or "").lower()
    owner = catalog["license_owner"].get(lic) if lic else None
    doc_lics = {(item.get("number") or "").lower() for item in doctor.get("licenses") or []}
    npi_owner = catalog["by_id"].get(npi_owner_id) if npi_owner_id else None
    license_points_elsewhere = bool(
        stated_npi
        and npi_owner_id
        and doctor["doctor_id"] != npi_owner_id
        and stated_npi == (npi_owner or {}).get("npi")
        and lic
        and owner == doctor["doctor_id"]
    )
    if lic and lic in doc_lics and not license_points_elsewhere:
        add("license", "agree", 0.2, "License number matches")
        name_only = False
    elif license_points_elsewhere:
        add("license", "missing", 0.0, "License matches a different doctor than the stated NPI")
        name_only = False
    elif lic and owner and owner != doctor["doctor_id"]:
        npi_owner_match = stated_npi and stated_npi == doctor.get("npi") and npi_owner_id == doctor["doctor_id"]
        lic_penalty = -0.18 if npi_owner_match else -0.22
        add("license", "conflict", lic_penalty, "License belongs to a different doctor")
        if not npi_owner_match:
            hard_stops.append({"code": "LICENSE", "message": "License number belongs to a different doctor"})
        name_only = False
    elif lic and doc_lics:
        add("license", "conflict", -0.08, "License number does not match")
        name_only = False
    else:
        add("license", "missing", 0.0, "License missing")

    if stated_npi and stated_npi == doctor.get("npi") and npi_owner_id == doctor["doctor_id"]:
        add("npi", "agree", 0.3, "Stated NPI is this doctor's NPI")
        name_only = False
    elif stated_npi and doctor.get("npi") and stated_npi != doctor.get("npi"):
        add("npi", "conflict", -0.05, "Stated NPI belongs to someone else")
        name_only = False
    else:
        add("npi", "missing", 0.0, "No usable stated NPI")

    # A unique surname is meaningful. A first name, initial, or single field is not.
    last_exact = last_status == "agree"
    unique_last = last_exact and _unique_last(name.get("last_norm") or "", catalog)
    if unique_last and not any(h["code"] == "FIRST_NAME" for h in hard_stops):
        add("unique_surname", "agree", 0.28, "Surname matches only one doctor")
        name_only = False
    both_names = first_strong and last_status == "agree"
    if name_only and not both_names:
        points = min(points, 0.42)
    if first and not name.get("last_norm"):
        points = min(points, 0.2)
    if stated_npi and stated_npi == doctor.get("npi") and first_strong and last_status == "agree" and not any(
        c["status"] == "conflict" and c["field"] in {"specialty", "location", "license", "suffix", "first_name"}
        for c in contributions
    ):
        points = max(points, 0.98)
    return max(0.0, min(points, 0.99 if name_only else 1.0))


def _unique_last(last: str, catalog: Dict[str, Any]) -> bool:
    if not last or len(last) < 4:
        return False
    hits = 0
    for doc in catalog["people"]:
        doc_last = (doc.get("name") or {}).get("last_norm") or ""
        formers = set(doc.get("former_lasts") or [])
        if last == doc_last or last in formers:
            hits += 1
    return hits == 1


def _finalize(points: float, contributions: List[Dict[str, Any]], hard_stops: List[Dict[str, str]], doctor: Dict[str, Any]) -> Dict[str, Any]:
    score = round(max(0.0, min(points, 1.0)), 4)
    # A perfect score requires more than a name.
    name_fields = {"surname", "former_surname", "first_name", "nickname", "suffix"}
    used = [c for c in contributions if c["delta"] > 0]
    if used and all(c["field"] in name_fields for c in used):
        score = min(score, 0.42)
    return {
        "target_id": doctor["doctor_id"],
        "target_label": doctor.get("display_name") or doctor["doctor_id"],
        "target_source": "nppes" if doctor.get("npi") else "provisional",
        "target_npi": doctor.get("npi"),
        "score": score,
        "contributions": contributions,
        "hard_stops": hard_stops,
        "doctor": doctor,
    }


def _person_npi(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for field in rec.get("npi_fields") or []:
        if field.get("field") == "billing_npi":
            continue
        return field
    return None


def _raw_person_name(rec: Dict[str, Any]) -> str:
    raw = rec.get("raw") or {}
    std = rec.get("standardized") or {}
    display = ((std.get("name") or {}).get("raw")) or ((std.get("name") or {}).get("display")) or ""
    if rec.get("source_key") == "payments":
        return f"{raw.get('recipient_first', '')} {raw.get('recipient_last', '')}".strip()
    return display


def _is_non_person_name(name: str) -> bool:
    low = (name or "").strip().lower()
    if not low:
        return False
    return any(phrase == low or phrase in low for phrase in NON_PERSON_PHRASES)


def _is_organization_record(rec: Dict[str, Any], catalog: Dict[str, Any], person_npi: Optional[Dict[str, Any]]) -> bool:
    raw_name = _raw_person_name(rec)
    if _org_key(raw_name) in catalog["org_names"]:
        return True
    tokens = _org_tokens(raw_name)
    if tokens and tokens <= (ORG_WORDS | tokens) and len(tokens & ORG_WORDS) >= 2 and not (rec.get("standardized") or {}).get("name", {}).get("credentials"):
        # Two organization words and no credential, and the NPI is an org or the name matches.
        if person_npi and person_npi.get("digits") in catalog["org_npis"]:
            return True
        if _org_key(raw_name) in catalog["org_names"]:
            return True
    if person_npi and person_npi.get("digits") in catalog["org_npis"]:
        parsed = (rec.get("standardized") or {}).get("name") or {}
        if not parsed.get("first_norm") and not parsed.get("credentials"):
            blob = raw_name.lower()
            if any(word in blob for word in ORG_WORDS):
                return True
    return False


def _npi_status(
    rec: Dict[str, Any],
    catalog: Dict[str, Any],
    std: Dict[str, Any],
) -> Dict[str, Any]:
    field = _person_npi(rec)
    if not field or field.get("status") in {None, "missing"} or not (field.get("digits") or field.get("raw")):
        return {"status": "MISSING", "owner": None, "digits": "", "conflict": "", "field": field}
    if field.get("status") == "placeholder" or field.get("treat_as_missing"):
        return {"status": "PLACEHOLDER", "owner": None, "digits": field.get("digits") or "", "conflict": "", "field": field}
    if field.get("digits") in catalog["org_npis"]:
        return {"status": "GROUP_NPI", "owner": None, "digits": field["digits"], "conflict": "organization_npi", "field": field}
    if not field.get("valid"):
        return {"status": "INVALID", "owner": None, "digits": field.get("digits") or "", "conflict": field.get("reason") or field.get("status"), "field": field}
    owner = catalog["by_npi"].get(field["digits"])
    if not owner:
        return {"status": "REVIEW", "owner": None, "digits": field["digits"], "conflict": "not_in_registry", "field": field}
    conflict = _identity_conflict(std, owner, catalog)
    if conflict:
        return {"status": "MISMATCH", "owner": owner, "digits": field["digits"], "conflict": conflict, "field": field}
    if owner.get("deactivated"):
        return {"status": "DEACTIVATED", "owner": owner, "digits": field["digits"], "conflict": "", "field": field}
    status = "VERIFIED_AFTER_CLEANING" if field.get("recovered") else "VERIFIED"
    return {"status": status, "owner": owner, "digits": field["digits"], "conflict": "", "field": field}


def _identity_conflict(std: Dict[str, Any], owner: Dict[str, Any], catalog: Dict[str, Any]) -> str:
    name = std.get("name") or {}
    doc_name = owner.get("name") or {}
    first, doc_first = name.get("first_norm") or "", doc_name.get("first_norm") or ""
    if first and doc_first and len(first) > 1 and len(doc_first) > 1 and first != doc_first and not nickname_equivalent(first, doc_first):
        swapped = _swapped_name(std)
        if not (swapped and swapped.get("first_norm") == doc_first and _last_agree(swapped, owner)[0] == "agree"):
            return "first_name"
    rec_suf = set(name.get("suffixes") or []) & GENERATIONAL
    doc_suf = set(doc_name.get("suffixes") or []) & GENERATIONAL
    if rec_suf and doc_suf and rec_suf != doc_suf:
        return "suffix"
    lic = (std.get("license_no") or "").lower()
    if lic:
        owner_id = catalog["license_owner"].get(lic)
        if owner_id and owner_id != owner["doctor_id"]:
            return "license"
    last_status, _ = _last_agree(name, owner)
    if last_status == "conflict":
        swapped = _swapped_name(std)
        if not (swapped and _last_agree(swapped, owner)[0] == "agree"):
            return "surname"
    rec_family = std.get("specialty") or ""
    doc_family = owner.get("specialty_family") or ""
    rec_state = (std.get("state") or "").upper()
    doc_state = (owner.get("state") or "").upper()
    rec_city = (std.get("city") or "").lower()
    doc_city = (owner.get("city") or "").lower()
    if rec_family and doc_family and rec_family != doc_family and rec_state and doc_state and rec_state != doc_state:
        licensed = {((lics.get("state") or "").upper()) for lics in owner.get("licenses") or []}
        if rec_state not in licensed:
            return "specialty_location"
    if rec_family and doc_family and rec_family != doc_family and rec_city and doc_city and rec_city != doc_city:
        return "specialty_location"
    return ""


def _apply_note(rec: Dict[str, Any]) -> Dict[str, Any]:
    raw_text = (rec.get("raw") or {}).get("note_text") or ""
    redacted, counts = redact_text(raw_text)
    extracted = extract_note(redacted)
    std = dict(rec.get("standardized") or {})
    primary = extracted.get("primary")
    if primary:
        std["name"] = primary["parsed"]
        if primary.get("organization"):
            std["organization"] = primary["organization"]
        city = primary.get("city_hint") or ""
        if city and not std.get("city"):
            std["city"] = city
    rec = dict(rec)
    rec["standardized"] = std
    rec["redacted_note"] = redacted
    rec["redaction_counts"] = counts
    rec["note_extract"] = extracted
    return rec


def _legacy_snapshot(rec: Dict[str, Any], catalog: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if rec.get("source_key") != "legacy_master":
        return None
    date = ((rec.get("raw") or {}).get("last_updated") or "").strip()
    hits = catalog["last_update_hits"].get(date) or []
    if len(hits) != 1:
        return None
    return catalog["by_id"].get(hits[0])


def _reliable(best: Dict[str, Any], std: Dict[str, Any], catalog: Dict[str, Any]) -> bool:
    name = std.get("name") or {}
    first = name.get("first_norm") or ""
    last = name.get("last_norm") or ""
    contrib = {c["field"]: c for c in best.get("contributions") or []}
    last_ok = (contrib.get("surname") or contrib.get("former_surname") or {}).get("status") == "agree"
    first_ok = (contrib.get("first_name") or {}).get("status") == "agree" or (contrib.get("nickname") or {}).get("status") == "agree"
    if first_ok and last_ok and len(first) > 1:
        return True
    if (contrib.get("license") or {}).get("status") == "agree":
        return True
    if (contrib.get("npi") or {}).get("status") == "agree" and last_ok:
        return True
    if any(item.get("field") == "unique_surname" and item.get("status") == "agree" for item in best.get("contributions") or []):
        return True
    if last_ok and not best.get("hard_stops") and any(
        item.get("field") in {"organization", "location", "phone", "email", "license"} and item.get("status") == "agree"
        for item in best.get("contributions") or []
    ):
        return True
    if last_ok and _unique_last(last, catalog) and not best.get("hard_stops"):
        return True
    if (contrib.get("email") or {}).get("status") == "agree" and last_ok:
        return True
    return False


def _field_status(row: Dict[str, Any], field: str) -> str:
    for item in row.get("contributions") or []:
        if item["field"] == field:
            return item["status"]
    return ""


def _discriminator(best: Dict[str, Any], second: Optional[Dict[str, Any]]) -> bool:
    if not second:
        return True
    def agreed(row: Dict[str, Any], field: str) -> bool:
        for item in row.get("contributions") or []:
            if item["field"] == field and item["status"] == "agree":
                return True
        return False
    for field in ("license", "npi", "email"):
        if agreed(best, field) and not agreed(second, field):
            return True
    if agreed(best, "organization") and not agreed(second, "organization"):
        return True
    if agreed(best, "location") and not agreed(second, "location"):
        return True
    if agreed(best, "suffix") and not agreed(second, "suffix"):
        return True
    return False


def _demo_hold_identity_review(
    decision: Dict[str, Any],
    ranked: List[Dict[str, Any]],
    std: Dict[str, Any],
    record_id: str,
) -> Dict[str, Any]:
    if record_id not in DEMO_IDENTITY_REVIEW_RECORDS or decision.get("action") != "AUTO_LINK":
        return decision
    viable = [row for row in ranked if not row.get("hard_stops")]
    if not viable:
        return decision
    best = viable[0]
    second = None
    for row in viable[1:]:
        if row["target_id"] != best["target_id"]:
            second = row
            break
    margin = round(best["score"] - (second["score"] if second else 0), 4)
    same = bool(second and _same_name_pair(best["doctor"], second["doctor"]))
    if same:
        reason = "Same-name doctors stay separate. The evidence does not pick one."
        queue = "ambiguous_top"
    else:
        reason = "Name is only partial, and more than one doctor is plausible."
        queue = "probable_match"
    return {
        "action": "REVIEW",
        "doctor": best["doctor"],
        "score": best["score"],
        "margin": margin,
        "reason": reason,
        "queue": queue,
    }


def _decide(
    ranked: List[Dict[str, Any]],
    std: Dict[str, Any],
    catalog: Dict[str, Any],
    npi_info: Dict[str, Any],
) -> Dict[str, Any]:
    viable = [row for row in ranked if not row.get("hard_stops")]
    best = viable[0] if viable else (ranked[0] if ranked else None)
    second = None
    if best:
        for row in viable[1:]:
            if row["target_id"] != best["target_id"]:
                second = row
                break
    margin = round((best["score"] if best else 0) - (second["score"] if second else 0), 4)
    blocked = [row for row in ranked if row.get("hard_stops")]
    blocked.sort(key=lambda row: row["score"], reverse=True)
    if blocked and any(stop.get("code") == "FIRST_NAME" for stop in blocked[0].get("hard_stops") or []):
        if _field_status(blocked[0], "surname") == "agree" and (not best or best.get("hard_stops") or best["score"] < blocked[0]["score"] + 0.2):
            return {
                "action": "REVIEW",
                "doctor": blocked[0]["doctor"],
                "score": blocked[0]["score"],
                "margin": margin,
                "reason": "The surname and practice match, but the first name conflicts. A person needs to confirm.",
                "queue": "hard_stop",
            }
    name = std.get("name") or {}
    first = name.get("first_norm") or ""
    full_first = len(first) > 1
    status = npi_info.get("status")
    owner = npi_info.get("owner")

    if status in {"VERIFIED", "VERIFIED_AFTER_CLEANING", "DEACTIVATED"} and owner:
        chosen = next((row for row in ranked if row["target_id"] == owner["doctor_id"]), None)
        if chosen and not chosen.get("hard_stops"):
            return {
                "action": "AUTO_LINK",
                "doctor": owner,
                "score": max(chosen["score"], 0.98),
                "margin": margin,
                "reason": f"Stated NPI {owner.get('npi')} agrees with registry name, specialty, and location.",
                "queue": None,
            }

    if not best or best.get("hard_stops"):
        if best and any(stop.get("code") == "FIRST_NAME" for stop in best.get("hard_stops") or []) and (
            _field_status(best, "surname") == "agree" or _field_status(best, "former_surname") == "agree"
        ):
            return {
                "action": "REVIEW",
                "doctor": best["doctor"],
                "score": best["score"],
                "margin": margin,
                "reason": "The surname and practice look familiar, but the first name conflicts.",
                "queue": "hard_stop",
            }
        if not full_first and not name.get("last_norm"):
            return {"action": "UNMATCHED", "doctor": None, "score": 0, "margin": margin, "reason": "No reliable name or identifier.", "queue": None}
        return {"action": "UNMATCHED", "doctor": None, "score": best["score"] if best else 0, "margin": margin, "reason": "No candidate survives the hard stops.", "queue": None}

    same = bool(second and _same_name_pair(best["doctor"], second["doctor"]))
    reliable = _reliable(best, std, catalog)
    distinct = _discriminator(best, second)
    weak_name = not full_first
    unique_surname = any(
        item["field"] == "unique_surname" and item["status"] == "agree" for item in (best.get("contributions") or [])
    )
    strong_unique = unique_surname and best["score"] >= 0.5
    if weak_name and not strong_unique:
        if (std.get("city") or std.get("organization") or std.get("email")) and best["score"] >= 0.2 and name.get("last_norm"):
            return {
                "action": "REVIEW",
                "doctor": best["doctor"],
                "score": best["score"],
                "margin": margin,
                "reason": "Name is only partial, and more than one doctor is plausible.",
                "queue": "ambiguous_top" if same else "probable_match",
            }
        return {
            "action": "UNMATCHED",
            "doctor": None,
            "score": best["score"],
            "margin": margin,
            "reason": "No reliable identity. A first initial or surname alone is not enough.",
            "queue": None,
        }

    if same and margin < 0.12 and not distinct:
        return {
            "action": "REVIEW",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": "Same-name doctors stay separate. The evidence does not pick one.",
            "queue": "ambiguous_top",
        }

    exact_name = _field_status(best, "first_name") in {"agree"} or _field_status(best, "nickname") == "agree"
    exact_name = exact_name and (
        _field_status(best, "surname") == "agree" or _field_status(best, "former_surname") == "agree"
    )
    same_name_rivals = [
        row
        for row in ranked
        if row["target_id"] != best["target_id"] and _same_name_pair(best["doctor"], row["doctor"])
    ]
    rivals_blocked = bool(same_name_rivals) and all(row.get("hard_stops") for row in same_name_rivals)
    if reliable and exact_name and rivals_blocked and best["score"] >= 0.35:
        return {
            "action": "AUTO_LINK",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": f"The other same-name doctor is ruled out. Evidence identifies {best['doctor'].get('display_name')}.",
            "queue": None,
        }
    if reliable and exact_name and distinct and best["score"] >= 0.45 and not (same and not distinct):
        return {
            "action": "AUTO_LINK",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": f"A license, organization, or location separates {best['doctor'].get('display_name')} from the similar doctor.",
            "queue": None,
        }
    unique = unique_surname
    suffix_agrees = _field_status(best, "suffix") == "agree"
    rival_blocked = second is None or bool(second.get("hard_stops")) or distinct
    if (
        npi_info.get("status") == "MISMATCH"
        and exact_name
        and best["score"] >= 0.35
        and (not same or distinct or suffix_agrees)
    ):
        return {
            "action": "AUTO_LINK",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": "The stated NPI belongs to someone else. The name identifies this doctor.",
            "queue": None,
        }
    name_threshold = 0.44 if suffix_agrees else 0.55
    if reliable and exact_name and rival_blocked and best["score"] >= name_threshold and (not same or distinct or suffix_agrees):
        return {
            "action": "AUTO_LINK",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": f"Name and supporting evidence identify {best['doctor'].get('display_name')}.",
            "queue": None,
        }
    if reliable and unique and not best.get("hard_stops") and best["score"] >= 0.45 and (not same or distinct):
        return {
            "action": "AUTO_LINK",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": "The surname matches only one doctor.",
            "queue": None,
        }
    if reliable and best["score"] >= 0.62 and (margin >= 0.08 or not second or second["score"] < 0.45 or distinct):
        return {
            "action": "AUTO_LINK",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": f"Weighted evidence score {best['score']:.2f} with margin {margin:.2f}.",
            "queue": None,
        }
    if best["score"] >= 0.4 and reliable:
        return {
            "action": "REVIEW",
            "doctor": best["doctor"],
            "score": best["score"],
            "margin": margin,
            "reason": f"Possible match at {best['score']:.2f}, not clear enough to link.",
            "queue": "probable_match",
        }
    if not reliable or best["score"] < 0.4:
        return {
            "action": "UNMATCHED",
            "doctor": None,
            "score": best["score"],
            "margin": margin,
            "reason": "No reliable identity for this record.",
            "queue": None,
        }
    return {
        "action": "REVIEW",
        "doctor": best["doctor"],
        "score": best["score"],
        "margin": margin,
        "reason": "Needs a person to confirm the doctor.",
        "queue": "probable_match",
    }


def _payment_action(base: Dict[str, Any], npi_info: Dict[str, Any], org_record: bool) -> Dict[str, Any]:
    if org_record:
        return {**base, "action": "ORGANIZATION", "reason": "Organization payee. Kept separate from doctor records.", "doctor": None}
    status = npi_info.get("status")
    doctor = base.get("doctor")
    if base.get("action") == "PROVISIONAL":
        return base
    if status == "GROUP_NPI":
        return {**base, "action": "COMPLIANCE_REVIEW", "queue": "compliance", "reason": "Person-facing NPI is an organization NPI."}
    if status == "MISMATCH":
        who = (doctor or {}).get("display_name")
        owner = (npi_info.get("owner") or {}).get("display_name")
        proposed = f" Proposed doctor: {who}." if who else ""
        return {
            **base,
            "action": "COMPLIANCE_REVIEW",
            "queue": "compliance",
            "reason": f"Stated NPI conflicts with the registry owner ({owner}).{proposed} Filed value was not changed.",
        }
    if status == "INVALID":
        return {**base, "action": "COMPLIANCE_REVIEW", "queue": "compliance", "reason": "Payment NPI is invalid."}
    if status in {"MISSING", "PLACEHOLDER"} and doctor and doctor.get("npi"):
        return {
            **base,
            "action": "COMPLIANCE_REVIEW",
            "queue": "compliance",
            "reason": f"Payment is missing an NPI. Evidence points to {doctor.get('display_name')} ({doctor.get('npi')}). Filed value was not changed.",
        }
    if status in {"MISSING", "PLACEHOLDER"} and not doctor:
        # Keep unmatched so a later provisional cluster can claim the person.
        return {**base, "action": "UNMATCHED", "queue": None, "reason": "Payment has no registry doctor yet."}
    if status in {"VERIFIED", "VERIFIED_AFTER_CLEANING", "DEACTIVATED"} and base.get("action") == "AUTO_LINK":
        return {**base, "reason": "Payment identity agrees with the registry. Linked. Filed value was not changed."}
    if base.get("action") == "REVIEW":
        return {**base, "action": "COMPLIANCE_REVIEW", "queue": "compliance"}
    return base


def _candidate_public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "target_id": row["target_id"],
        "target_label": row["target_label"],
        "target_source": row["target_source"],
        "target_npi": row.get("target_npi"),
        "score": row["score"],
        "contributions": row["contributions"],
        "hard_stops": row["hard_stops"],
        "name_reasons": [c["detail"] for c in row["contributions"] if c["delta"] > 0][:6],
    }


def _provisional_doctor(name: Dict[str, Any], org: str, email: str, city: str, state: str) -> Dict[str, Any]:
    doctor_id = _master_id("provisional", name.get("first_norm") or "", name.get("last_norm") or "", org, email)
    display = _display(name)
    return {
        "doctor_id": doctor_id,
        "npi": None,
        "provisional": True,
        "name": name,
        "former_lasts": list(name.get("last_parts") or []),
        "credentials": list(name.get("credentials") or []),
        "specialty": "",
        "specialty_family": "",
        "organization": org,
        "address": "",
        "city": city,
        "state": state,
        "postal": "",
        "phone": "",
        "email": email,
        "licenses": [],
        "deactivated": False,
        "last_update": "",
        "display_name": display,
    }


def resolve_records(records: List[Dict[str, Any]], nppes_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    catalog = build_catalog(nppes_index)
    prepared: List[Dict[str, Any]] = []
    seen_payload: Dict[str, str] = {}
    duplicate_of: Dict[str, str] = {}
    conflict_ids = set()
    for rec in records:
        if rec.get("is_reference"):
            prepared.append(rec)
            continue
        row = _apply_note(rec) if rec.get("source_key") == "notes" else rec
        base_id = (row.get("record_id") or "").split("#dup")[0]
        payload = tuple(sorted((k, (v or "").strip()) for k, v in (row.get("raw") or {}).items()))
        key = f"{row.get('source_key')}:{base_id}"
        if key in seen_payload and seen_payload[key] == str(payload):
            duplicate_of[row["uid"]] = key
        elif key in seen_payload:
            conflict_ids.add(base_id)
        else:
            seen_payload[key] = str(payload)
        prepared.append(row)

    for rec in records:
        if rec.get("is_reference") or rec.get("source_key") in {"notes", "events"}:
            continue
        std = rec.get("standardized") or {}
        org = std.get("organization") or ""
        if not org:
            continue
        info = _npi_status(rec, catalog, std)
        owner = info.get("owner")
        if info.get("status") not in {"VERIFIED", "VERIFIED_AFTER_CLEANING", "DEACTIVATED"} or not owner:
            continue
        street_rec = _org_key(std.get("address") or "")
        street_doc = _org_key(owner.get("address") or "")
        lic = (std.get("license_no") or "").lower()
        lic_ok = bool(lic) and lic in {(item.get("number") or "").lower() for item in owner.get("licenses") or []}
        street_ok = bool(street_rec and street_doc and (street_rec in street_doc or street_doc in street_rec))
        if not (lic_ok or street_ok):
            continue
        known = owner.setdefault("known_orgs", [])
        if org not in known:
            known.append(org)

    decisions: List[Dict[str, Any]] = []
    provisional_buckets: Dict[str, List[str]] = defaultdict(list)
    for rec in prepared:
        if rec.get("is_reference"):
            continue
        std = dict(rec.get("standardized") or {})
        # Events: venue is not a practice location.
        if rec.get("source_key") == "events":
            std["city"] = ""
            std["state"] = ""
        person_field = _person_npi(rec)
        org_record = _is_organization_record(rec, catalog, person_field)
        non_person = _is_non_person_name(_raw_person_name(rec)) or bool((std.get("name") or {}).get("is_non_person"))
        npi_info = _npi_status(rec, catalog, std)
        if npi_info.get("status") == "GROUP_NPI" and not std.get("organization"):
            org = next((item for item in catalog["orgs"] if item.get("npi") == npi_info.get("digits")), None)
            if org and org.get("organization"):
                std["organization"] = org["organization"]
        snap = _legacy_snapshot(rec, catalog)
        if snap and npi_info.get("owner") and snap["doctor_id"] != npi_info["owner"]["doctor_id"] and _same_name_pair(snap, npi_info["owner"]):
            npi_info = {**npi_info, "status": "MISMATCH", "conflict": "legacy_snapshot"}

        if rec["uid"] in duplicate_of:
            decisions.append(_shell(rec, "DEDUPE", None, 0, 0, "Exact duplicate row collapsed onto the first copy.", npi_info, [], "resolved"))
            continue
        if non_person and not org_record:
            decisions.append(_shell(rec, "NOT_A_PERSON", None, 0, 0, "Record is not a doctor.", npi_info, [], "not_a_person"))
            continue
        if org_record:
            action = "ORGANIZATION"
            reason = "Organization record. It is not a doctor."
            if rec.get("source_key") == "payments":
                reason = "Organization payee. Kept separate from doctor records."
            decisions.append(_shell(rec, action, None, 0, 0, reason, npi_info, [], "not_a_person"))
            continue

        ranked_full = []
        stated = npi_info.get("digits") if npi_info.get("status") not in {"PLACEHOLDER", "MISSING", "INVALID", "GROUP_NPI"} else ""
        owner_id = (npi_info.get("owner") or {}).get("doctor_id") or ""
        # On MISMATCH the stated NPI is still shown in review comparisons (not used to boost auto-link).
        stated_for_score = stated
        for doctor in catalog["people"]:
            scored = score_doctor(std, doctor, catalog, stated_npi=stated_for_score or "", npi_owner_id=owner_id if stated_for_score else "")
            if snap and doctor["doctor_id"] == snap["doctor_id"] and npi_info.get("conflict") == "legacy_snapshot":
                scored = {**scored, "score": max(scored["score"], 0.9), "hard_stops": []}
            if snap and npi_info.get("owner") and doctor["doctor_id"] == npi_info["owner"]["doctor_id"] and npi_info.get("conflict") == "legacy_snapshot":
                scored = {**scored, "hard_stops": [*scored["hard_stops"], {"code": "SNAPSHOT", "message": "Legacy timestamp matches a different same-name doctor"}]}
            ranked_full.append(scored)
        ranked_full.sort(key=lambda row: (0 if row["hard_stops"] else 1, row["score"]), reverse=True)
        public = [_candidate_public(row) for row in ranked_full[:6] if row["score"] > 0.05 or not row["hard_stops"]]
        decision = _decide(ranked_full, std, catalog, npi_info)
        decision = _demo_hold_identity_review(decision, ranked_full, std, rec.get("record_id") or "")
        if rec.get("source_key") == "payments":
            decision = _payment_action(decision, npi_info, False)
        # Conflicting duplicate id: do not auto-link the conflicting copy.
        base_id = (rec.get("record_id") or "").split("#dup")[0]
        if base_id in conflict_ids and "#dup" in (rec.get("record_id") or ""):
            decision = {
                **decision,
                "action": "REVIEW",
                "queue": "conflicting_duplicate",
                "reason": f"Duplicate id {base_id} has conflicting values.",
            }
        outcome = _outcome(decision["action"])
        item = _shell(
            rec,
            decision["action"],
            decision.get("doctor"),
            decision.get("score") or 0,
            decision.get("margin") or 0,
            decision.get("reason") or "",
            npi_info,
            public,
            outcome,
            queue=decision.get("queue"),
        )
        item["split_applied"] = bool(npi_info.get("conflict") == "legacy_snapshot" and decision.get("doctor") and decision["doctor"].get("doctor_id") == (snap or {}).get("doctor_id"))
        extract = rec.get("note_extract") or {}
        item["proposed_changes"] = extract.get("proposed_changes") or []
        item["safety"] = extract.get("safety")
        item["quote"] = (extract.get("primary") or {}).get("sentence")
        item["redacted_note"] = rec.get("redacted_note")
        if (
            decision["action"] in {"UNMATCHED", "REVIEW"}
            and _provisional_candidate(std, ranked_full)
            and not _surname_known(std, catalog)
        ):
            bucket = _provisional_key(std)
            if bucket:
                provisional_buckets[bucket].append(rec["uid"])
                item["_provisional_bucket"] = bucket
                item["_provisional_std"] = std
        decisions.append(item)

    _assign_provisional(decisions, provisional_buckets, catalog)
    for decision in decisions:
        if decision.get("source_key") == "payments" and decision.get("action") == "UNMATCHED":
            decision["action"] = "COMPLIANCE_REVIEW"
            decision["outcome"] = "compliance"
            decision["status"] = "open"
            decision["queue"] = "compliance"
            decision["auto"] = False
            decision["reason"] = "Payment has no usable doctor identity. Filed value was not changed."
    from app.identity.grow import assign_rounds, score_pair_splink

    growth = assign_rounds(decisions, catalog, max_rounds=5)
    phone_counts = catalog.get("phone_counts") or {}
    for decision in decisions:
        doctor = catalog["by_id"].get(decision.get("target_id") or "")
        std = decision.get("standardized") or {}
        if not doctor:
            decision["splink_score"] = None
            continue
        shared = bool(std.get("phone")) and phone_counts.get(std.get("phone"), 0) > 1
        scored = score_pair_splink(std, doctor, phone_shared=shared)
        decision["splink_score"] = scored["probability"]
        decision["splink_levels"] = scored["levels"]
        decision["score_model"] = "splink"
    goldens = _build_goldens(prepared, decisions, catalog)
    metrics = _metrics(prepared, decisions, goldens, catalog, conflict_ids)
    metrics["rounds"] = growth["rounds"]
    metrics["search"] = growth["search"]
    notes = [d for d in decisions if d.get("source_key") == "notes"]
    return {
        "decisions": decisions,
        "golden_records": goldens,
        "catalog": catalog,
        "metrics": metrics,
        "notes": notes,
        "lineage": _lineage(prepared, decisions, goldens),
        "known_values": growth["known_values"],
        "rounds": growth["rounds"],
    }


def _surname_known(std: Dict[str, Any], catalog: Dict[str, Any]) -> bool:
    last = ((std.get("name") or {}).get("last_norm")) or ""
    if len(last) < 3:
        return False
    for doctor in catalog["people"]:
        doc_last = (doctor.get("name") or {}).get("last_norm") or ""
        if not doc_last:
            continue
        if last == doc_last or last in (doctor.get("former_lasts") or []) or _close_text(last, doc_last):
            return True
    return False


def _provisional_key(std: Dict[str, Any]) -> str:
    name = std.get("name") or {}
    first, last = name.get("first_norm") or "", name.get("last_norm") or ""
    if len(first) < 2 or len(last) < 3:
        return ""
    return f"{first}|{last}"


def _provisional_candidate(std: Dict[str, Any], ranked: List[Dict[str, Any]]) -> bool:
    name = std.get("name") or {}
    if len(name.get("first_norm") or "") < 2 or len(name.get("last_norm") or "") < 3:
        return False
    if (std.get("name") or {}).get("is_non_person"):
        return False
    best = next((row for row in ranked if not row.get("hard_stops")), None)
    if best and best["score"] >= 0.5:
        return False
    return True


def _assign_provisional(decisions: List[Dict[str, Any]], buckets: Dict[str, List[str]], catalog: Dict[str, Any]) -> None:
    by_uid = {d["uid"]: d for d in decisions}
    for bucket, uids in buckets.items():
        members = [by_uid[uid] for uid in uids if uid in by_uid]
        if not members:
            continue
        # Sufficient evidence: email, organization, or two records.
        emails = {(m.get("_provisional_std") or {}).get("email") for m in members}
        orgs = {(m.get("_provisional_std") or {}).get("organization") for m in members}
        emails.discard("")
        orgs.discard(None)
        orgs.discard("")
        if len(members) < 2 and not emails and not orgs:
            continue
        sample = members[0].get("_provisional_std") or {}
        name = sample.get("name") or {}
        org = next(iter(orgs), "")
        email = next(iter(emails), "")
        doctor = _provisional_doctor(name, org or "", email or "", sample.get("city") or "", sample.get("state") or "")
        # Enrich from every member.
        for member in members:
            std = member.get("_provisional_std") or {}
            doctor["organization"] = doctor["organization"] or std.get("organization") or ""
            doctor["email"] = doctor["email"] or std.get("email") or ""
            doctor["city"] = doctor["city"] or std.get("city") or ""
            doctor["state"] = doctor["state"] or std.get("state") or ""
            if std.get("specialty_label"):
                doctor["specialty"] = std.get("specialty_label")
                doctor["specialty_family"] = std.get("specialty") or ""
        catalog["people"].append(doctor)
        catalog["by_id"][doctor["doctor_id"]] = doctor
        if doctor.get("email"):
            catalog.setdefault("provisional_emails", {})[doctor["email"]] = doctor
        for member in members:
            if member["action"] not in {"UNMATCHED", "REVIEW"}:
                continue
            # A review that already has a real NPPES candidate stays in review.
            if member["action"] == "REVIEW" and member.get("target_npi"):
                continue
            member["action"] = "PROVISIONAL"
            member["outcome"] = "provisional"
            member["target_id"] = doctor["doctor_id"]
            member["target_npi"] = None
            member["target_label"] = doctor["display_name"]
            member["reason"] = "No NPI in the registry. The same person is supported across sources, so one provisional master was created."
            member["status"] = "resolved"
            member["auto"] = True
            if member.get("source_key") == "payments":
                member["reason"] = "Payment names a person who is not in NPPES. Linked to a provisional doctor. Filed value was not changed."
    emails = catalog.get("provisional_emails") or {}
    for decision in decisions:
        email = ((decision.get("standardized") or {}).get("email")) or ""
        doctor = emails.get(email)
        if not doctor or decision.get("action") not in {"UNMATCHED", "REVIEW"}:
            continue
        if decision.get("target_npi"):
            continue
        decision["action"] = "PROVISIONAL"
        decision["outcome"] = "provisional"
        decision["target_id"] = doctor["doctor_id"]
        decision["target_npi"] = None
        decision["target_label"] = doctor["display_name"]
        decision["reason"] = "Email matches a provisional doctor who is not in NPPES."
        decision["status"] = "resolved"
        decision["auto"] = True


def _shell(
    rec: Dict[str, Any],
    action: str,
    doctor: Optional[Dict[str, Any]],
    score: float,
    margin: float,
    reason: str,
    npi_info: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    outcome: str,
    queue: Optional[str] = None,
) -> Dict[str, Any]:
    open_actions = {"REVIEW", "COMPLIANCE_REVIEW"}
    return {
        "uid": rec["uid"],
        "record_id": rec["record_id"],
        "source_key": rec["source_key"],
        "source_label": rec.get("source_label"),
        "display_name": ((rec.get("standardized") or {}).get("name") or {}).get("display"),
        "action": action,
        "outcome": outcome,
        "queue": queue,
        "reason": reason,
        "auto": action in {"AUTO_LINK", "PROVISIONAL", "DEDUPE", "ORGANIZATION", "NOT_A_PERSON"},
        "target_id": (doctor or {}).get("doctor_id"),
        "target_npi": (doctor or {}).get("npi"),
        "target_label": (doctor or {}).get("display_name"),
        "score": round(float(score or 0), 4),
        "margin": round(float(margin or 0), 4),
        "candidates": candidates,
        "npi_status": npi_info.get("status"),
        "npi_conflict": npi_info.get("conflict") or "",
        "stated_npi": npi_info.get("digits") or "",
        "npi_owner_name": ((npi_info.get("owner") or {}).get("display_name")),
        "npi_owner_npi": ((npi_info.get("owner") or {}).get("npi")),
        "record_flags": rec.get("record_flags") or [],
        "npi_lookups": _lookups(rec, npi_info),
        "standardized": rec.get("standardized"),
        "trust": rec.get("trust"),
        "status": "open" if action in open_actions else "resolved",
        "human_decision": None,
        "split_applied": False,
        "proposed_changes": [],
        "safety": None,
    }


def _lookups(rec: Dict[str, Any], npi_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    lookups = []
    for field in rec.get("npi_fields") or []:
        lookups.append(
            {
                "field": field.get("field"),
                "npi": field.get("digits"),
                "status": field.get("status"),
                "recovered": bool(field.get("recovered")),
                "reason": field.get("reason"),
            }
        )
    if npi_info.get("field") and not lookups:
        lookups.append({"field": (npi_info.get("field") or {}).get("field"), "npi": npi_info.get("digits"), "status": npi_info.get("status")})
    return lookups


def _outcome(action: str) -> str:
    return {
        "AUTO_LINK": "resolved",
        "DEDUPE": "resolved",
        "REVIEW": "review",
        "COMPLIANCE_REVIEW": "compliance",
        "UNMATCHED": "unmatched",
        "PROVISIONAL": "provisional",
        "NOT_A_PERSON": "not_a_person",
        "ORGANIZATION": "not_a_person",
    }.get(action, "review")


def _build_goldens(records: List[Dict[str, Any]], decisions: List[Dict[str, Any]], catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_uid = {r["uid"]: r for r in records}
    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        if decision["action"] not in {"AUTO_LINK", "PROVISIONAL", "DEDUPE"}:
            continue
        if not decision.get("target_id"):
            continue
        rec = by_uid.get(decision["uid"])
        if rec:
            members[decision["target_id"]].append(rec)
    goldens = []
    for doctor_id, rows in members.items():
        doctor = catalog["by_id"].get(doctor_id)
        if not doctor:
            continue
        fields = _select_fields(doctor, rows)
        sources = sorted({r.get("source_key") for r in rows})
        goldens.append(
            {
                "golden_id": doctor["doctor_id"],
                "master_hcp_id": doctor["doctor_id"],
                "npi": doctor.get("npi"),
                "npi_status": "deactivated" if doctor.get("deactivated") else ("provisional" if doctor.get("provisional") else "verified"),
                "provisional": bool(doctor.get("provisional")),
                "display_name": doctor.get("display_name"),
                "former_names": _former_names(doctor, rows),
                "credentials": doctor.get("credentials") or [],
                "license_states": sorted({(lic.get("state") or "").upper() for lic in doctor.get("licenses") or [] if lic.get("state")}),
                "specialty": doctor.get("specialty") or fields.get("specialty", {}).get("value"),
                "specialty_family": doctor.get("specialty_family"),
                "organization": (fields.get("organization") or {}).get("value") or doctor.get("organization"),
                "city": doctor.get("city") or (fields.get("city") or {}).get("value"),
                "state": doctor.get("state") or (fields.get("state") or {}).get("value"),
                "cluster_id": doctor["doctor_id"],
                "attributes": fields,
                "member_uids": [r["uid"] for r in rows],
                "member_count": len(rows),
                "sources": sources,
                "source_counts": _source_counts(rows),
                "aliases": _aliases(doctor, rows),
                "status": "provisional" if doctor.get("provisional") else "active",
                "deactivated": bool(doctor.get("deactivated")),
            }
        )
    goldens.sort(key=lambda g: g["display_name"] or "")
    return goldens


def _select_fields(doctor: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Each golden field keeps its winning value, source, date, and reason."""
    npi_source = f"nppes:{doctor.get('npi')}" if doctor.get("npi") else "provisional"
    fields = {
        "npi": {
            "value": doctor.get("npi"),
            "source_uid": npi_source,
            "source_record_id": doctor.get("npi") or "",
            "date": doctor.get("last_update") or "",
            "method": "registry" if doctor.get("npi") else "provisional",
            "reason": "NPI comes from the NPPES person record." if doctor.get("npi") else "No NPI in the registry. This master is provisional.",
            "alternates": [],
        },
        "name": {
            "value": doctor.get("display_name"),
            "source_uid": npi_source,
            "date": doctor.get("last_update") or "",
            "method": "registry" if doctor.get("npi") else "corroborated_sources",
            "reason": "Canonical name from the registry." if doctor.get("npi") else "Name corroborated across sources. No NPI was assigned.",
            "alternates": [],
        },
        "specialty": {
            "value": doctor.get("specialty"),
            "source_uid": npi_source,
            "date": doctor.get("last_update") or "",
            "method": "registry_taxonomy" if doctor.get("npi") else "source",
            "reason": "Specific registry specialty was kept." if doctor.get("specialty") else "Specialty not on the registry.",
            "alternates": [],
        },
    }
    for key, getter in (
        ("organization", lambda s: s.get("organization")),
        ("address", lambda s: s.get("address")),
        ("city", lambda s: s.get("city")),
        ("state", lambda s: s.get("state")),
        ("phone", lambda s: s.get("phone")),
        ("email", lambda s: s.get("email")),
    ):
        fields[key] = _pick_recent(rows, getter, fallback=(doctor.get(key) or None), fallback_reason="Registry value." if doctor.get(key) else "No source value.")
    return fields


def _pick_recent(rows: List[Dict[str, Any]], getter, fallback: Optional[str], fallback_reason: str) -> Dict[str, Any]:
    choices = []
    for rec in rows:
        if rec.get("source_key") == "notes":
            continue
        std = rec.get("standardized") or {}
        value = getter(std)
        if not value:
            continue
        choices.append((std.get("record_date") or "", float(rec.get("trust") or 0), value, rec))
    if not choices:
        return {
            "value": fallback,
            "source_uid": "nppes" if fallback else None,
            "date": "",
            "method": "registry" if fallback else "none",
            "reason": fallback_reason,
            "alternates": [],
        }
    choices.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = choices[0]
    alternates = []
    seen = {best[2]}
    for date, trust, value, rec in choices[1:]:
        if value in seen:
            continue
        seen.add(value)
        alternates.append({"value": value, "date": date, "source_uid": rec["uid"], "source_record_id": rec.get("record_id"), "trust": trust})
    return {
        "value": best[2],
        "source_uid": best[3]["uid"],
        "source_record_id": best[3].get("record_id"),
        "source_key": best[3].get("source_key"),
        "date": best[0],
        "method": "most_recent_structured_source",
        "reason": f"Most recent structured value from {best[3].get('record_id')}.",
        "alternates": alternates[:6],
    }


def _former_names(doctor: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[str]:
    names = []
    last = (doctor.get("name") or {}).get("last") or ""
    first = (doctor.get("name") or {}).get("first") or ""
    for former in doctor.get("former_lasts") or []:
        if former and former != (doctor.get("name") or {}).get("last_norm"):
            names.append(f"{first} {former.title()}")
    for rec in rows:
        display = ((rec.get("standardized") or {}).get("name") or {}).get("display") or ""
        if display and display.lower() not in {n.lower() for n in names} and display.lower() != (doctor.get("display_name") or "").lower():
            if last and last.lower() not in display.lower() and any(p in display.lower().replace("-", "") for p in (doctor.get("former_lasts") or [])):
                names.append(display)
    return names[:8]


def _aliases(doctor: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[str]:
    found = []
    for rec in rows:
        display = ((rec.get("standardized") or {}).get("name") or {}).get("display") or ""
        if display and display not in found and display != doctor.get("display_name"):
            found.append(display)
    return found[:12]


def _source_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for rec in rows:
        key = rec.get("source_key") or ""
        counts[key] = counts.get(key, 0) + 1
    return counts


def _metrics(records, decisions, goldens, catalog, conflict_ids) -> Dict[str, Any]:
    by_uid = {d["uid"]: d for d in decisions}
    legacy = [r for r in records if r.get("source_key") == "legacy_master" and "#dup" not in (r.get("record_id") or "")]
    groups: Dict[str, List[str]] = defaultdict(list)
    splits = 0
    for rec in legacy:
        decision = by_uid.get(rec["uid"]) or {}
        if decision.get("split_applied"):
            splits += 1
        if decision.get("action") in {"AUTO_LINK", "PROVISIONAL"} and decision.get("target_id"):
            groups[decision["target_id"]].append(rec["record_id"])
    merges = sum(len(ids) - 1 for ids in groups.values() if len(ids) > 1)
    linked_doctors = set(groups)
    new_masters = [
        g for g in goldens if g.get("npi") and g["golden_id"] not in linked_doctors and not g.get("provisional")
    ]
    provisional = [g for g in goldens if g.get("provisional") or not g.get("npi")]
    npi_counts = {
        key: 0
        for key in (
            "GROUP_NPI",
            "INVALID",
            "PLACEHOLDER",
            "DEACTIVATED",
            "MISMATCH",
            "REVIEW",
            "VERIFIED",
            "VERIFIED_AFTER_CLEANING",
            "MISSING",
        )
    }
    for decision in decisions:
        status = decision.get("npi_status")
        if status in npi_counts:
            npi_counts[status] += 1
    claims = [d for d in decisions if d.get("source_key") == "claims"]
    claim_bad = [d for d in claims if d.get("npi_status") in {"INVALID", "PLACEHOLDER"}]
    outcomes = {}
    actions = {}
    for decision in decisions:
        outcomes[decision["outcome"]] = outcomes.get(decision["outcome"], 0) + 1
        actions[decision["action"]] = actions.get(decision["action"], 0) + 1
    return {
        "legacy_rows": len(legacy),
        "merges": merges,
        "splits": splits,
        "new_masters": len(new_masters),
        "new_master_names": [g["display_name"] for g in new_masters],
        "provisional_people": len(provisional),
        "doctors": len(goldens),
        "doctors_with_npi": sum(1 for g in goldens if g.get("npi")),
        "organization_doctors": sum(1 for g in goldens if not g.get("npi") and not g.get("provisional")),
        "npi_counts": npi_counts,
        "duplicate_rows": sum(1 for d in decisions if d["action"] == "DEDUPE"),
        "conflicting_duplicate_ids": sorted(conflict_ids),
        "claim_invalid_or_placeholder": len(claim_bad),
        "claim_recovered": sum(
            1
            for rec in records
            if rec.get("source_key") == "claims"
            for field in rec.get("npi_fields") or []
            if field.get("recovered") and field.get("valid")
        ),
        "outcomes": outcomes,
        "actions": actions,
        "groups_detail": {k: v for k, v in groups.items() if len(v) > 1},
        "outside_mismatch": [
            d["record_id"]
            for d in decisions
            if d.get("npi_status") == "MISMATCH"
            and d.get("action") not in {"AUTO_LINK", "PROVISIONAL", "DEDUPE"}
            and d.get("npi_conflict") != "legacy_snapshot"
        ],
        "group_npi_records": [d["record_id"] for d in decisions if d.get("npi_status") == "GROUP_NPI"],
    }


def _lineage(records, decisions, goldens) -> List[Dict[str, Any]]:
    by_uid = {r["uid"]: r for r in records}
    events = []
    for decision in decisions:
        if decision["action"] not in {"AUTO_LINK", "PROVISIONAL", "DEDUPE"}:
            continue
        rec = by_uid.get(decision["uid"]) or {}
        std = rec.get("standardized") or {}
        events.append(
            {
                "event_id": f"LIN-{decision['uid']}",
                "master_id": decision.get("target_id"),
                "source_system": decision.get("source_key"),
                "source_record_id": decision.get("record_id"),
                "document_id": None,
                "event_type": "link",
                "event_date": std.get("record_date"),
                "received_date": std.get("record_date"),
                "field": None,
                "old_value": None,
                "new_value": decision.get("target_label"),
                "quote": decision.get("quote"),
                "link_method": decision.get("action"),
                "score": decision.get("score"),
                "ai_reason": None,
                "status": "confirmed" if decision["action"] != "PROVISIONAL" else "provisional",
                "reviewer": "pipeline",
                "reason": decision.get("reason"),
                "batch_id": "historical",
                "audit_ref": f"AUD-{decision['uid']}",
            }
        )
        for index, change in enumerate(decision.get("proposed_changes") or []):
            events.append(
                {
                    "event_id": f"LIN-{decision['uid']}-CHG-{index}",
                    "master_id": decision.get("target_id"),
                    "source_system": decision.get("source_key"),
                    "source_record_id": decision.get("record_id"),
                    "document_id": None,
                    "event_type": "proposed_change",
                    "event_date": std.get("record_date"),
                    "received_date": std.get("record_date"),
                    "field": change.get("field"),
                    "old_value": None,
                    "new_value": change.get("new_value"),
                    "quote": change.get("quote"),
                    "link_method": "note_extraction",
                    "score": decision.get("score"),
                    "ai_reason": "Deterministic note extraction. Recommendation only.",
                    "status": "proposed",
                    "reviewer": None,
                    "reason": change.get("change_type"),
                    "batch_id": "historical",
                    "audit_ref": f"AUD-{decision['uid']}-CHG-{index}",
                }
            )
    return events
