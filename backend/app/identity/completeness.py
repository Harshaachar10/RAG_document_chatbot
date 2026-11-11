"""Share of required golden-record fields that are filled. The field list is the configuration."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

COMPLETENESS_FIELDS: Sequence[str] = (
    "NPI",
    "specialty",
    "practice",
    "location",
    "phone",
    "license",
    "email",
)


def completeness(doctor: Dict[str, Any], *, has_practice: bool) -> Tuple[int, List[str]]:
    checks = {
        "NPI": bool(doctor.get("official_npi")),
        "specialty": bool(doctor.get("specialty")),
        "practice": has_practice,
        "location": bool(doctor.get("city") or doctor.get("state")),
        "phone": bool(doctor.get("professional_phone")),
        "license": bool(doctor.get("license_states")),
        "email": bool(doctor.get("professional_email")),
    }
    missing = [name for name in COMPLETENESS_FIELDS if not checks[name]]
    filled = len(COMPLETENESS_FIELDS) - len(missing)
    pct = round(100 * filled / len(COMPLETENESS_FIELDS)) if COMPLETENESS_FIELDS else 0
    return pct, missing
