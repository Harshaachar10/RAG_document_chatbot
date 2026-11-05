from __future__ import annotations

from typing import Any, Dict, List, Optional


def evaluate_hard_stops(
    left: Dict[str, Any],
    right: Dict[str, Any],
    *,
    right_is_nppes: bool = False,
) -> List[Dict[str, str]]:
    """
    Return list of hard-stop violations. Any violation blocks AUTO_LINK.
    """
    stops: List[Dict[str, str]] = []
    a = left.get("standardized") or left
    if right_is_nppes:
        b = {
            "name": right.get("name") or {},
            "specialty": right.get("specialty") or "",
            "state": right.get("state") or "",
            "city": right.get("city") or "",
            "zip3": (right.get("postal") or "")[:3],
        }
        right_npis = {right.get("npi")} if right.get("npi") else set()
        entity = right.get("entity_type") or ""
        if entity == "2":
            stops.append({"code": "ORG_ENTITY", "message": "NPPES entity is organization, not individual"})
    else:
        b = right.get("standardized") or right
        right_npis = {nf["digits"] for nf in (right.get("npi_fields") or []) if nf.get("valid")}

    left_npis = {nf["digits"] for nf in (left.get("npi_fields") or []) if nf.get("valid")}

    # conflicting valid NPIs
    if left_npis and right_npis and not (left_npis & right_npis):
        stops.append(
            {
                "code": "NPI_CONFLICT",
                "message": f"Conflicting valid NPIs: {sorted(left_npis)} vs {sorted(right_npis)}",
            }
        )

    # Jr/Sr conflict with same first+last
    sa = set((a.get("name") or {}).get("suffixes") or [])
    sb = set((b.get("name") or {}).get("suffixes") or [])
    generational = {"JR", "SR", "II", "III", "IV"}
    if (sa & generational) and (sb & generational) and not (sa & sb):
        na, nb = a.get("name") or {}, b.get("name") or {}
        if na.get("first_norm") == nb.get("first_norm") and na.get("last_norm") == nb.get("last_norm"):
            stops.append(
                {
                    "code": "GENERATIONAL_SUFFIX",
                    "message": f"Generational suffix conflict: {sorted(sa)} vs {sorted(sb)}",
                }
            )

    # specialty family hard conflict when both present and unrelated + different geo
    sa_spec = a.get("specialty") or ""
    sb_spec = b.get("specialty") or ""
    if sa_spec and sb_spec and sa_spec != sb_spec:
        same_state = (a.get("state") or "") and a.get("state") == b.get("state")
        same_zip = (a.get("zip3") or "") and a.get("zip3") == b.get("zip3")
        if not same_state and not same_zip:
            stops.append(
                {
                    "code": "SPECIALTY_GEO_CONFLICT",
                    "message": f"Specialty families differ ({sa_spec} vs {sb_spec}) with different geography",
                }
            )

    # non-person names
    if (a.get("name") or {}).get("is_non_person") or a.get("is_non_person"):
        stops.append({"code": "NOT_A_PERSON", "message": "Left record appears non-person / office staff"})
    if (b.get("name") or {}).get("is_non_person") or b.get("is_non_person"):
        stops.append({"code": "NOT_A_PERSON", "message": "Right record appears non-person / office staff"})

    # placeholder / invalid NPIs already classified — treat placeholder-only as soft, not hard

    return stops


def record_level_flags(record: Dict[str, Any]) -> List[Dict[str, str]]:
    flags: List[Dict[str, str]] = []
    std = record.get("standardized") or {}
    if std.get("is_non_person") or (std.get("name") or {}).get("is_non_person"):
        flags.append({"code": "NOT_A_PERSON", "message": "Name looks like office/staff/non-person"})
    for nf in record.get("npi_fields") or []:
        if nf.get("status") in {"placeholder", "luhn_fail", "invalid_format"}:
            flags.append({"code": f"NPI_{nf['status'].upper()}", "message": f"NPI field {nf.get('field')}: {nf.get('status')}"})
    for df in std.get("date_flags") or []:
        flags.append({"code": df.upper(), "message": f"Date flag: {df}"})
    if record.get("requires_compliance_review") or record.get("payment_source"):
        flags.append({"code": "COMPLIANCE_REVIEW", "message": "Payment/transparency source requires compliance review"})
    return flags
