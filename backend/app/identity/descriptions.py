"""Fixed-template doctor and record descriptions. No model writes this text."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

_SECRET_RE = re.compile(
    r"\b\d{10}\b|\b[A-Z]{2}-\d{4,}\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|@",
    re.I,
)


def _pretty(token: str) -> str:
    if not token:
        return ""
    parts = re.split(r"([-'’])", token)
    return "".join(part.capitalize() if part.isalpha() else part for part in parts)


def _join_name(name: Dict[str, Any], credential: str = "") -> str:
    first = _pretty(name.get("first") or "")
    middle = _pretty(name.get("middle") or "")
    last = _pretty(name.get("last") or "")
    suffixes = []
    for suffix in name.get("suffixes") or []:
        suffixes.append(suffix.title() if suffix.upper() in {"JR", "SR"} else suffix)
    base = " ".join(part for part in [first, middle, last, *suffixes] if part)
    cred = (credential or "").strip()
    if cred and cred.upper() not in base.upper():
        return f"{base}, {cred}" if base else cred
    return base


def _sentence_list(label: str, values: List[str]) -> str:
    clean = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text and text not in clean:
            clean.append(text)
    if not clean:
        return ""
    return f"{label} {', '.join(clean)}."


def description_text(
    *,
    name: str,
    also_known: List[str],
    credential: str,
    specialty: str,
    practices: List[str],
    previous_practices: List[str],
    city: str,
    state: str,
    license_states: List[str],
) -> str:
    """Golden and incoming records share this template.

    NPI, license numbers, DEA, phone, email, and patient data are not included.
    """
    parts: List[str] = []
    who = name.strip()
    if credential and credential.upper() not in who.upper():
        who = f"{who}, {credential}" if who else credential
    if who:
        parts.append(who if who.endswith(".") else f"{who}.")
    aliases = [a for a in also_known if a and a.lower() != name.lower()]
    if aliases:
        parts.append(f"Also known as {', '.join(aliases)}.")
    if specialty:
        parts.append(f"{specialty}.")
    current = [p for p in practices if p]
    if current:
        place = current[0]
        where = ", ".join(bit for bit in [city, state] if bit)
        if where and where.lower() not in place.lower():
            parts.append(f"Practices at {place}, {where}.")
        else:
            parts.append(f"Practices at {place}.")
    elif city or state:
        where = ", ".join(bit for bit in [city, state] if bit)
        parts.append(f"Located in {where}.")
    previous = [p for p in previous_practices if p and p not in current]
    if previous:
        parts.append(f"Previously at {', '.join(previous)}.")
    states = [s for s in license_states if s]
    if states:
        parts.append(f"Licensed in {', '.join(states)}.")
    text = " ".join(parts)
    text = _SECRET_RE.sub("", text)
    return " ".join(text.split())


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def describe_doctor(doctor: Dict[str, Any], known: Dict[str, Any] | None = None) -> str:
    known = known or {}
    name = doctor.get("display_name") or ""
    creds = doctor.get("credentials") or []
    credential = creds[0] if creds else ""
    also = list(doctor.get("former_names") or [])
    for alias in known.get("aliases") or []:
        if alias not in also:
            also.append(alias)
    practices = []
    org = doctor.get("organization") or ""
    if org:
        practices.append(org)
    for extra in known.get("organizations") or []:
        if extra and extra not in practices:
            practices.append(extra)
    current = practices[:1]
    previous = practices[1:]
    license_states = list(doctor.get("license_states") or [])
    if not license_states:
        license_states = [lic.get("state") for lic in doctor.get("licenses") or [] if lic.get("state")]
    return description_text(
        name=name,
        also_known=also,
        credential=credential,
        specialty=doctor.get("specialty") or "",
        practices=current,
        previous_practices=previous,
        city=doctor.get("city") or "",
        state=doctor.get("state") or "",
        license_states=[str(s) for s in license_states if s],
    )


def describe_record(record: Dict[str, Any]) -> str:
    std = record.get("standardized") or {}
    name = std.get("name") or {}
    creds = name.get("credentials") or []
    credential = creds[0] if creds else ""
    display = name.get("display") or _join_name(name, credential)
    org = std.get("organization") or ""
    if record.get("source_key") == "events":
        # Venue is not a practice address.
        city, state = "", ""
        org = org
    else:
        city, state = std.get("city") or "", std.get("state") or ""
    license_states = []
    if std.get("license_state") and record.get("source_key") != "events":
        license_states.append(std["license_state"])
    return description_text(
        name=display,
        also_known=[],
        credential=credential,
        specialty=std.get("specialty_label") or std.get("specialty") or "",
        practices=[org] if org else [],
        previous_practices=[],
        city=city,
        state=state,
        license_states=license_states,
    )


def assert_description_safe(text: str) -> None:
    """Used by tests. Product matching does not depend on this."""
    lowered = text.lower()
    for banned in ("npi", "patient", "dob", "@", "phone"):
        if banned in lowered:
            raise AssertionError(banned)
