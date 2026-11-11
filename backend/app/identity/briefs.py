"""Stored doctor summaries and safety alarms built from pipeline output."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from app.utils.dates import utc_now_iso


def alarms_from_decisions(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alarms: List[Dict[str, Any]] = []
    for decision in decisions:
        safety = decision.get("safety") or {}
        if not safety.get("flagged"):
            continue
        alarms.append(
            {
                "record_id": decision.get("record_id"),
                "doctor_id": decision.get("target_id"),
                "doctor_name": decision.get("target_label"),
                "quote": safety.get("quote") or "",
                "reason": safety.get("reason") or "Possible adverse event",
                "route": "pharmacovigilance",
            }
        )
    return alarms


def compose_brief(doctor: Dict[str, Any], alarms: List[Dict[str, Any]]) -> Dict[str, Any]:
    name = doctor.get("preferred_name") or "This doctor"
    npi = doctor.get("official_npi") or "no NPI on file"
    status = doctor.get("npi_status") or "not recorded"
    specialty = doctor.get("specialty") or "specialty not recorded"
    place = ", ".join(part for part in [doctor.get("city"), doctor.get("state")] if part) or "location not recorded"
    former = [name for name in (doctor.get("former_names") or []) if name and name != doctor.get("preferred_name")]
    org = ""
    attributes = doctor.get("attributes") or {}
    if isinstance(attributes, dict):
        org = str(attributes.get("organization") or "")
    sentences = [
        f"{name} ({npi}, {status}) is recorded in {specialty} at {place}."
    ]
    if org:
        sentences.append(f"Current organization: {org}.")
    if former:
        sentences.append("Also recorded as " + ", ".join(former) + ".")
    if alarms:
        quotes = [alarm.get("quote") for alarm in alarms if alarm.get("quote")]
        sentences.append(
            "Safety alarm: a linked note mentions a possible adverse event"
            + (f" — {quotes[0]}" if quotes else ".")
        )
    text = " ".join(sentences)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return {
        "text": text,
        "input_hash": digest,
        "updated_at": utc_now_iso(),
        "source": "stored profile",
    }


def attach_briefs(doctors: Dict[str, Dict[str, Any]], decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alarms = alarms_from_decisions(decisions)
    by_doctor: Dict[str, List[Dict[str, Any]]] = {}
    for alarm in alarms:
        did = alarm.get("doctor_id") or ""
        if did:
            by_doctor.setdefault(did, []).append(alarm)
    for doctor_id, doctor in doctors.items():
        doctor_alarms = by_doctor.get(doctor_id) or []
        doctor["alarms"] = doctor_alarms
        doctor["profile_brief"] = compose_brief(doctor, doctor_alarms)
    return alarms
