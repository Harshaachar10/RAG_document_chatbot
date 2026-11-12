from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.identity.config import PLACEHOLDER_NPIS, REFERENCE_NPI_LUHN_EXEMPT, TAXONOMY_LABELS
from app.identity.standardize import (
    normalize_phone,
    normalize_text,
    normalize_zip,
    parse_person_name,
    specialty_family,
    specialty_label,
)


def digits_only(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def luhn_valid_npi(npi: str) -> bool:
    """CMS NPI Luhn check: prefix 80840 + 10-digit NPI."""
    if len(npi) != 10 or not npi.isdigit():
        return False
    payload = "80840" + npi
    total = 0
    reverse = payload[::-1]
    for idx, ch in enumerate(reverse):
        d = int(ch)
        if idx % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


_SCIENCE_RE = re.compile(r"^\d+(?:\.\d+)?[eE][+\-]?\d+$")
_EXCEL_FLOAT_RE = re.compile(r"^(\d+)\.0+$")
_NPI_PREFIX_RE = re.compile(r"^NPI\s*[:#]\s*", re.I)


def _base(raw: str, **extra: Any) -> Dict[str, Any]:
    info = {
        "raw": raw,
        "digits": "",
        "status": "missing",
        "valid": False,
        "treat_as_missing": True,
        "recovered": False,
        "reason": "",
    }
    info.update(extra)
    return info


def classify_npi(raw_value: Any) -> Dict[str, Any]:
    """Clean spaces, dashes, an NPI: prefix, and a trailing Excel .0 before validation.

    Scientific notation such as 1.06087E+09 has already lost digits, so it stays invalid.
    Placeholders are not invalid numbers; matching treats them as missing.
    """
    raw = normalize_text(raw_value)
    if not raw:
        return _base("")
    upper = raw.upper()
    if upper in {"UNKNOWN", "N/A", "NA", "NONE", "NULL", "0", "-", "--"}:
        return _base(raw, status="placeholder", treat_as_missing=True, reason="placeholder_token")

    compact = re.sub(r"\s+", "", raw)
    if _SCIENCE_RE.fullmatch(compact):
        return _base(
            raw,
            digits=digits_only(compact),
            status="invalid_format",
            treat_as_missing=False,
            reason="excel_scientific_notation",
        )

    text = _NPI_PREFIX_RE.sub("", raw).strip()
    recovered = text != raw
    float_match = _EXCEL_FLOAT_RE.fullmatch(text.replace(" ", ""))
    if float_match:
        text = float_match.group(1)
        recovered = True
    stripped = re.sub(r"[\s\-]", "", text)
    recovered = recovered or stripped != text
    text = stripped
    digits = digits_only(text)
    recovered = recovered or (bool(digits) and digits != text)
    if digits in PLACEHOLDER_NPIS:
        return _base(raw, digits=digits, status="placeholder", treat_as_missing=True, reason="placeholder_npi")
    if len(digits) != 10:
        return _base(
            raw,
            digits=digits,
            status="invalid_format",
            treat_as_missing=False,
            recovered=recovered,
            reason="length",
        )
    if not luhn_valid_npi(digits):
        if digits in REFERENCE_NPI_LUHN_EXEMPT:
            return _base(
                raw,
                digits=digits,
                status="valid",
                valid=True,
                treat_as_missing=False,
                recovered=recovered,
                reason="demo_reference_npi",
            )
        return _base(
            raw,
            digits=digits,
            status="luhn_fail",
            treat_as_missing=False,
            recovered=recovered,
            reason="luhn",
        )
    return _base(
        raw,
        digits=digits,
        status="valid",
        valid=True,
        treat_as_missing=False,
        recovered=recovered,
        reason="recovered_excel_decimal" if recovered else "valid",
    )


def build_nppes_index(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        npi_info = classify_npi(row.get("NPI"))
        if not npi_info["valid"]:
            digits = npi_info.get("digits") or ""
            if digits not in REFERENCE_NPI_LUHN_EXEMPT:
                continue
            npi_info = {**npi_info, "valid": True, "status": "valid", "treat_as_missing": False}
        name = parse_person_name(
            f"{row.get('Provider_First_Name', '')} {row.get('Provider_Middle_Name', '')} {row.get('Provider_Last_Name', '')}".strip()
        )
        if row.get("Provider_Name_Suffix"):
            suf = normalize_text(row["Provider_Name_Suffix"]).upper()
            if suf and suf not in name["suffixes"]:
                name["suffixes"] = [*name["suffixes"], suf]
        taxonomy = row.get("Taxonomy_Code_1") or row.get("Healthcare_Provider_Taxonomy_Code_1") or ""
        licenses = []
        for num_key, state_key in (("License_Number_1", "License_State_1"), ("License_Number_2", "License_State_2")):
            num = normalize_text(row.get(num_key) or "")
            lic_state = normalize_text(row.get(state_key) or "").upper()
            if num:
                licenses.append({"number": num, "state": lic_state})
        index[npi_info["digits"]] = {
            "npi": npi_info["digits"],
            "entity_type": row.get("Entity_Type_Code") or "",
            "name": name,
            "other_last": normalize_text(row.get("Provider_Other_Last_Name") or "").lower().replace("-", ""),
            "organization": normalize_text(row.get("Provider_Organization_Name")),
            "address": normalize_text(row.get("Practice_Address") or row.get("Provider_First_Line_Business_Practice_Location_Address")),
            "city": normalize_text(row.get("Practice_City") or row.get("Provider_Business_Practice_Location_Address_City_Name")),
            "state": normalize_text(
                row.get("Practice_State") or row.get("Provider_Business_Practice_Location_Address_State_Name")
            ).upper(),
            "postal": normalize_zip(
                row.get("Practice_Postal_Code") or row.get("Provider_Business_Practice_Location_Address_Postal_Code")
            ),
            "phone": normalize_phone(
                row.get("Practice_Phone") or row.get("Provider_Business_Practice_Location_Address_Telephone_Number")
            ),
            "specialty": specialty_family(taxonomy),
            "specialty_label": specialty_label(taxonomy) or TAXONOMY_LABELS.get(taxonomy.upper(), ""),
            "taxonomy": taxonomy,
            "license_no": licenses[0]["number"] if licenses else "",
            "license_state": licenses[0]["state"] if licenses else "",
            "licenses": licenses,
            "credential": normalize_text(row.get("Provider_Credential") or ""),
            "enumeration_date": row.get("Enumeration_Date") or row.get("Provider_Enumeration_Date") or "",
            "last_update": row.get("Last_Update_Date") or row.get("Provider_Last_Update_Date") or "",
            "deactivated": bool(normalize_text(row.get("NPI_Deactivation_Date"))),
            "raw": row,
        }
    return index


def lookup_npi(npi_digits: str, index: Dict[str, Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
    if not npi_digits:
        return None, "missing"
    hit = index.get(npi_digits)
    if hit:
        if hit.get("deactivated"):
            return hit, "deactivated"
        return hit, "found"
    return None, "not_in_reference"
