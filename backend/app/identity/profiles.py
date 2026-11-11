"""Source profiles: an agent proposes column roles; a person approves a version.

The agent sees headers and masked samples only. It does not match records.
Later files of the same source type reuse the approved version.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.identity.config import DEFAULT_SOURCE_PROFILES

ROLES = {
    "person_npi",
    "organization_npi",
    "first_name",
    "last_name",
    "full_name",
    "credential",
    "specialty",
    "organization",
    "address",
    "city",
    "state",
    "zip",
    "phone",
    "email",
    "license",
    "license_state",
    "date",
    "amount",
    "free_text",
    "patient_field",
    "ignore",
}

_HEADER_ROLES = [
    (re.compile(r"patient|member_id|mrn|dob|date_of_birth", re.I), "patient_field"),
    (re.compile(r"billing_npi|organization_npi|org_npi|group_npi", re.I), "organization_npi"),
    (re.compile(r"(^|_)npi($|_)|prescriber_npi|recipient_npi|npi_vod", re.I), "person_npi"),
    (re.compile(r"first_name|recipient_first|provider_first", re.I), "first_name"),
    (re.compile(r"last_name|recipient_last|provider_last|other_last", re.I), "last_name"),
    (re.compile(r"full_name|account_name|prescriber_name|attendee|recipient_name", re.I), "full_name"),
    (re.compile(r"credential", re.I), "credential"),
    (re.compile(r"specialty|taxonomy", re.I), "specialty"),
    (re.compile(r"org|parent|practice|venue", re.I), "organization"),
    (re.compile(r"address", re.I), "address"),
    (re.compile(r"city", re.I), "city"),
    (re.compile(r"(^|_)st$|state", re.I), "state"),
    (re.compile(r"zip|postal", re.I), "zip"),
    (re.compile(r"phone|telephone", re.I), "phone"),
    (re.compile(r"email", re.I), "email"),
    (re.compile(r"license_state", re.I), "license_state"),
    (re.compile(r"license", re.I), "license"),
    (re.compile(r"date|enumeration|last_update|last_modified", re.I), "date"),
    (re.compile(r"amount|quantity|days_supply", re.I), "amount"),
    (re.compile(r"note_text|comment|free", re.I), "free_text"),
]

_TYPE_BY_FILENAME = {
    "01_nppes_reference.csv": "nppes",
    "02_legacy_customer_master.csv": "master",
    "03_crm_accounts.csv": "crm",
    "04_claims.csv": "claims",
    "05_events.csv": "events",
    "06_payments.csv": "payments",
    "07_hub_enrollments.csv": "hub",
    "08_call_notes_and_inquiries.csv": "notes",
}

_ROUTES = [
    "phonetic_surname_state",
    "first_zip3_specialty",
    "former_surname_state",
    "nickname_and_swapped",
    "phone",
    "email",
    "license_state",
    "organization_surname",
]


def _mask(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= 2:
        return "*" * len(text)
    return text[0] + ("*" * (len(text) - 2)) + text[-1]


def _role_for(header: str) -> tuple[str, float, str]:
    for pattern, role in _HEADER_ROLES:
        if pattern.search(header or ""):
            return role, 0.9, f"Header '{header}' matches the {role.replace('_', ' ')} pattern."
    return "ignore", 0.55, f"Header '{header}' has no identity role."


def _source_type(filename: str, headers: List[str]) -> tuple[str, float, str]:
    if filename in _TYPE_BY_FILENAME:
        kind = _TYPE_BY_FILENAME[filename]
        return kind, 0.95, f"Filename {filename} is the historical {kind} extract."
    blob = " ".join(headers).lower()
    if "taxonomy" in blob or "entity_type" in blob:
        return "nppes", 0.7, "Headers look like an NPPES registry extract."
    if "payment" in blob or "amount" in blob and "recipient" in blob:
        return "payments", 0.7, "Headers include a payment recipient and an amount."
    if "note_text" in blob:
        return "notes", 0.8, "A free-text note column is present."
    if "claim" in blob or "prescriber" in blob:
        return "claims", 0.66, "Headers look like a claim or prescription feed."
    if "attendee" in blob or "venue" in blob:
        return "events", 0.66, "Headers look like an event roster."
    if "account" in blob:
        return "crm", 0.6, "Headers look like a CRM account extract."
    return "unknown", 0.4, "The file type is not recognized from the headers."


def propose_profile(filename: str, headers: List[str], sample_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Deterministic proposer. An LLM may replace the reason text; validation still applies."""
    source_type, type_confidence, type_reason = _source_type(filename, headers)
    columns = []
    excluded = []
    for header in headers:
        role, confidence, reason = _role_for(header)
        samples = [_mask(row.get(header) or "") for row in sample_rows[:3]]
        samples = [s for s in samples if s]
        if role == "patient_field":
            excluded.append(header)
            reason = f"{reason} Patient fields are excluded from matching and from model calls."
        if role == "organization_npi" or header.lower() in {"billing_npi"}:
            if header not in excluded:
                excluded.append(header)
            reason = f"{reason} This is not used as a doctor NPI."
        columns.append(
            {
                "column": header,
                "role": role,
                "confidence": confidence,
                "reason": reason,
                "masked_samples": samples,
            }
        )
    rules = []
    if source_type == "events":
        rules.append("Venue city is not a practice address.")
    if source_type == "payments":
        rules.append("Any doubtful identity goes to compliance. Filed values are not changed.")
    if source_type == "claims":
        rules.append("billing_npi is an organization NPI and is not a doctor identifier.")
    if source_type == "notes":
        rules.append("Free text is redacted before any model call. Quotes must appear in the redacted text.")
    if source_type == "nppes":
        rules.append("Use Last_Update_Date. Do not count these rows as missing NPIs.")
    return {
        "filename": filename,
        "source_type": source_type,
        "type_confidence": type_confidence,
        "type_reason": type_reason,
        "columns": columns,
        "excluded_fields": excluded,
        "search_routes": list(_ROUTES),
        "rules": rules,
        "status": "proposed",
        "version": 1,
        "proposed_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_profile(profile: Dict[str, Any], headers: List[str], sample_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Columns must exist. Sample values must fit the claimed role. Required fields must be present."""
    errors: List[str] = []
    known = set(headers)
    roles_present = set()
    for column in profile.get("columns") or []:
        name = column.get("column")
        role = column.get("role")
        if name not in known:
            errors.append(f"Column {name} is not in the file.")
            continue
        if role not in ROLES:
            errors.append(f"Column {name} has an unknown role {role}.")
            continue
        roles_present.add(role)
        if role in {"person_npi", "organization_npi"}:
            for row in sample_rows[:8]:
                raw = (row.get(name) or "").strip()
                if not raw:
                    continue
                digits = re.sub(r"\D", "", raw.split("e")[0] if re.search(r"[eE]", raw) else raw)
                if raw and not digits and raw.upper() not in {"N/A", "NA", "NONE", "NULL", "UNKNOWN"}:
                    errors.append(f"Column {name} claimed as {role} but a sample is not an identifier.")
                    break
    if profile.get("source_type") not in {"notes", "unknown"} and "person_npi" not in roles_present and profile.get("source_type") not in {"events"}:
        if profile.get("source_type") in {"nppes", "master", "crm", "claims", "payments", "hub"}:
            errors.append("A person NPI column is required for this source type.")
    if profile.get("source_type") == "notes" and "free_text" not in roles_present:
        errors.append("Notes need a free-text column.")
    return {"ok": not errors, "errors": errors}


class ProfileStore:
    """Versioned approvals. Matching reads only approved versions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"profiles": []})

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def all(self) -> List[Dict[str, Any]]:
        return list(self._read().get("profiles") or [])

    def for_type(self, source_type: str) -> List[Dict[str, Any]]:
        return [p for p in self.all() if p.get("source_type") == source_type]

    def approved(self, source_type: str) -> Optional[Dict[str, Any]]:
        versions = [p for p in self.for_type(source_type) if p.get("status") == "approved"]
        if not versions:
            return None
        return sorted(versions, key=lambda p: int(p.get("version") or 0))[-1]

    def profile_for_run(self, source_type: str) -> Dict[str, Any]:
        chosen = self.approved(source_type)
        if not chosen:
            raise PermissionError(f"No approved profile for {source_type}.")
        return chosen

    def add_proposal(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        existing = [p for p in data["profiles"] if p.get("source_type") == profile.get("source_type")]
        version = 1 + max((int(p.get("version") or 0) for p in existing), default=0)
        stored = dict(profile)
        stored["version"] = version
        stored["status"] = "proposed"
        stored["id"] = hashlib.sha1(f"{stored.get('source_type')}|{version}".encode("utf-8")).hexdigest()[:12]
        data["profiles"].append(stored)
        self._write(data)
        return stored

    def decide(self, source_type: str, version: int, status: str, reviewer: str, reason: str = "") -> Dict[str, Any]:
        if status not in {"approved", "rejected"}:
            raise ValueError("status must be approved or rejected")
        data = self._read()
        found = None
        for profile in data["profiles"]:
            if profile.get("source_type") == source_type and int(profile.get("version") or 0) == int(version):
                profile["status"] = status
                profile["reviewer"] = reviewer or "Unassigned"
                profile["decision_reason"] = reason
                profile["decided_at"] = datetime.now(timezone.utc).isoformat()
                found = profile
        if not found:
            raise KeyError(f"Profile {source_type} version {version} was not found.")
        self._write(data)
        return found


def load_sample_profiles(data_dir: Path, limit: int = 3) -> List[Dict[str, Any]]:
    """Propose a profile for each historical file. Samples are masked."""
    import csv

    proposals = []
    for profile in DEFAULT_SOURCE_PROFILES.values():
        path = data_dir / profile.filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = list(reader.fieldnames or [])
            rows = []
            for index, row in enumerate(reader):
                if index >= limit:
                    break
                rows.append({k: ("" if v is None else str(v)) for k, v in row.items()})
        proposal = propose_profile(profile.filename, headers, rows)
        proposal["source_key"] = profile.key
        proposal["label"] = profile.label
        checked = validate_profile(proposal, headers, rows)
        proposal["validation"] = checked
        proposal["status"] = "Seeded — review before demo."
        proposals.append(proposal)
    return proposals
