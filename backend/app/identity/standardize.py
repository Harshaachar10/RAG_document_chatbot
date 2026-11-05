from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.identity.config import NON_PERSON_NAME_TOKENS, TAXONOMY_FAMILY_HINTS

CREDENTIAL_RE = re.compile(
    r"\b(MD|DO|NP|PA|PhD|MBBS|RN|DPM|DDS|DMD|FACS|FACP)\b\.?",
    re.I,
)
SUFFIX_RE = re.compile(r"\b(JR|SR|II|III|IV|2ND|3RD)\b\.?", re.I)
# Groups are compared at score time. First names are not rewritten, so "Sara Li"
# stays distinct from "Sarah Lee" until a last name also agrees.
NICKNAME_GROUPS = (
    frozenset({"william", "bill", "will", "liam"}),
    frozenset({"robert", "bob", "rob", "bobby"}),
    frozenset({"michael", "mike"}),
    frozenset({"miguel", "mike"}),
    frozenset({"kathryn", "katherine", "kate", "katie", "kathy", "kat"}),
    frozenset({"sarah", "sara"}),
    frozenset({"elizabeth", "beth", "liz", "betty"}),
    frozenset({"james", "jim", "jimmy"}),
    frozenset({"jennifer", "jenny", "jen"}),
    frozenset({"thomas", "tom"}),
    frozenset({"jose", "joe"}),
    frozenset({"anthon", "anthony", "tony"}),
)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _repair_mojibake(text: str) -> str:
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def normalize_text(value: Any) -> str:
    text = str(value or "")
    text = _repair_mojibake(text)
    text = text.replace("â€™", "'").replace("â€œ", '"').replace("â€", '"')
    text = _strip_accents(text)
    text = text.replace("'", "'").replace("'", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else digits


def normalize_email(value: Any) -> str:
    return normalize_text(value).lower()


def normalize_zip(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 4:
        digits = digits.zfill(5)
    return digits[:5] if digits else ""


def nickname_equivalent(left: str, right: str) -> bool:
    a = (left or "").lower()
    b = (right or "").lower()
    if not a or not b:
        return False
    if a == b:
        return True
    return any(a in group and b in group for group in NICKNAME_GROUPS)


def specialty_label(value: Any) -> str:
    """Keep specific specialties. Do not collapse Dermatology or Hematology."""
    from app.identity.config import TAXONOMY_LABELS

    text = normalize_text(value)
    if not text:
        return ""
    upper = text.upper()
    if upper in TAXONOMY_LABELS:
        return TAXONOMY_LABELS[upper]
    low = text.lower()
    if "breast" in low:
        return "Breast Oncology"
    if "thoracic" in low:
        return "Thoracic Oncology"
    if "nurse" in low or low.strip() in {"np"}:
        return "Nurse Practitioner"
    if "dermat" in low:
        return "Dermatology"
    if "hematol" in low and "onc" not in low and "hem/" not in low and "hem " not in low:
        return "Hematology"
    if "heme" == low or low.startswith("heme"):
        return "Hematology" if "onc" not in low else "Hematology & Oncology"
    if any(tok in low for tok in ("hem/onc", "hem onc", "hematology oncology", "hematology & oncology", "hematology-oncology")):
        return "Hematology & Oncology"
    if "pedia" in low:
        return "Pediatrics"
    if "card" in low:
        return "Cardiology"
    if "endo" in low:
        return "Endocrinology"
    if any(tok in low for tok in ("onc", "cancer", "med onc")):
        return "Medical Oncology"
    return text


def specialty_family(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if text.upper() in TAXONOMY_FAMILY_HINTS:
        return TAXONOMY_FAMILY_HINTS[text.upper()]
    low = text.lower()
    if "derm" in low:
        return "dermatology"
    if "card" in low:
        return "cardiology"
    if "pedia" in low:
        return "pediatrics"
    if "endo" in low:
        return "endocrinology"
    if "nurse" in low or low.strip() == "np":
        return "nursing"
    if low.strip() in {"heme", "hematology"} or ("hematol" in low and "onc" not in low):
        return "hematology"
    if any(tok in low for tok in ("onc", "cancer", "hem/onc", "hem onc", "med onc")):
        return "oncology"
    return low


def parse_date(value: Any) -> Tuple[Optional[str], List[str]]:
    raw = normalize_text(value)
    flags: List[str] = []
    if not raw:
        return None, flags
    # compact YYYYMMDD
    if re.fullmatch(r"\d{8}", raw):
        try:
            dt = datetime.strptime(raw, "%Y%m%d").date()
            if dt > date.today():
                flags.append("future_date")
                return None, flags
            return dt.isoformat(), flags
        except ValueError:
            flags.append("invalid_date")
            return None, flags
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y"):
        try:
            dt = datetime.strptime(raw, fmt).date()
            if dt > date.today():
                flags.append("future_date")
                return None, flags
            return dt.isoformat(), flags
        except ValueError:
            continue
    flags.append("invalid_date")
    return None, flags


def parse_person_name(raw: Any) -> Dict[str, Any]:
    original = normalize_text(raw)
    text = original
    text = re.sub(r"(?i)(?<![A-Za-z])M\.\s*D\.?(?![A-Za-z])", "MD", text)
    text = re.sub(r"(?i)(?<![A-Za-z])Ph\.\s*D\.?(?![A-Za-z])", "PhD", text)
    text = re.sub(r"(?i)(?<![A-Za-z])N\.\s*P\.?(?![A-Za-z])", "NP", text)
    credentials = [m.group(1).upper() for m in CREDENTIAL_RE.finditer(text)]
    suffixes = [
        m.group(1).upper().replace("2ND", "II").replace("3RD", "III") for m in SUFFIX_RE.finditer(text)
    ]

    # Strip titles/credentials/suffixes before deciding name order so
    # "Dr. Sarah Lee, MD" is not treated as LAST, FIRST.
    working = CREDENTIAL_RE.sub(" ", text)
    working = SUFFIX_RE.sub(" ", working)
    working = re.sub(r"\b(DR|DOCTOR|PROF|PROFESSOR)\b\.?", " ", working, flags=re.I)
    working = re.sub(r"\s+", " ", working).strip(" ,")

    first = middle = last = ""
    # LAST, FIRST [MIDDLE] — only when both sides still have name tokens
    if "," in working:
        left, right = [p.strip() for p in working.split(",", 1)]
        left = re.sub(r"[.]", " ", left).strip()
        right = re.sub(r"[.]", " ", right).strip()
        if left and right:
            last = left
            tokens = right.split()
            first = tokens[0] if tokens else ""
            middle = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        else:
            working = f"{left} {right}".strip()
            # fall through to western order below
            working = re.sub(r"[,.]", " ", working)
            working = re.sub(r"\s+", " ", working).strip()
            tokens = working.split()
            if len(tokens) == 1:
                if len(tokens[0]) <= 2:
                    first = tokens[0]
                else:
                    last = tokens[0]
            elif len(tokens) >= 2:
                first = tokens[0].rstrip(".")
                last = tokens[-1]
                middle = " ".join(tokens[1:-1])
    else:
        cleaned = re.sub(r"[,.]", " ", working)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        tokens = cleaned.split()
        if len(tokens) == 1:
            if len(tokens[0]) <= 2:
                first = tokens[0]
            else:
                last = tokens[0]
        elif len(tokens) >= 2:
            first = tokens[0].rstrip(".")
            last = tokens[-1]
            middle = " ".join(tokens[1:-1])

    if middle.upper() == "O" and last and not last.lower().startswith("o"):
        last = "O'" + last
        middle = ""
    first_n = first.lower()
    last_n = re.sub(r"[^a-z]", "", last.lower())
    # hyphenated surnames: also keep hyphen-stripped for matching
    last_hyphen_parts = [p for p in last.lower().split("-") if p]
    display = " ".join(x for x in [first, middle, last] if x).strip()
    low_raw = original.lower()
    is_non_person = low_raw in NON_PERSON_NAME_TOKENS or any(
        tok in low_raw for tok in NON_PERSON_NAME_TOKENS if len(tok) > 2
    )
    return {
        "raw": str(raw or ""),
        "first": first,
        "middle": middle,
        "last": last,
        "first_norm": first_n,
        "last_norm": last_n,
        "last_parts": last_hyphen_parts,
        "display": display or original,
        "credentials": credentials,
        "suffixes": suffixes,
        "is_non_person": is_non_person,
    }


def soundex(word: str) -> str:
    text = re.sub(r"[^A-Za-z]", "", (word or "").upper())
    if not text:
        return ""
    mappings = {
        **dict.fromkeys(list("BFPV"), "1"),
        **dict.fromkeys(list("CGJKQSXZ"), "2"),
        **dict.fromkeys(list("DT"), "3"),
        **dict.fromkeys(list("L"), "4"),
        **dict.fromkeys(list("MN"), "5"),
        **dict.fromkeys(list("R"), "6"),
    }
    first = text[0]
    digits = [mappings.get(ch, "0") for ch in text[1:]]
    coded = first
    prev = mappings.get(first, "0")
    for d in digits:
        if d != "0" and d != prev:
            coded += d
        prev = d if d != "0" else prev
    return (coded + "000")[:4]


def _first_present(raw: Dict[str, str], keys: List[str]) -> str:
    for k in keys:
        if raw.get(k):
            return raw[k]
    return ""


def standardize_record(raw: Dict[str, str], *, source_key: str, profile_flags: Dict[str, Any]) -> Dict[str, Any]:
    name_fields = list(profile_flags.get("name_fields") or [])
    name_bits = [raw.get(f, "") for f in name_fields if raw.get(f)]
    if source_key == "payments":
        name_bits = [f"{raw.get('recipient_first', '')} {raw.get('recipient_last', '')}".strip()]
    elif source_key == "nppes":
        name_bits = [
            f"{raw.get('Provider_First_Name', '')} {raw.get('Provider_Middle_Name', '')} {raw.get('Provider_Last_Name', '')}".strip()
        ]
        if not any(name_bits) and raw.get("Provider_Organization_Name"):
            name_bits = [raw["Provider_Organization_Name"]]
    name_raw = " ".join(b for b in name_bits if b).strip()
    parsed = parse_person_name(name_raw)

    city = normalize_text(
        _first_present(
            raw,
            ["City", "city", "Practice_City", "venue_city", "Provider_Business_Practice_Location_Address_City_Name"],
        )
    )
    state = normalize_text(
        _first_present(
            raw,
            [
                "St",
                "st",
                "state",
                "Practice_State",
                "venue_state",
                "Provider_Business_Practice_Location_Address_State_Name",
            ],
        )
    ).upper()
    postal = normalize_zip(
        _first_present(
            raw,
            [
                "Zip",
                "zip",
                "Practice_Postal_Code",
                "Provider_Business_Practice_Location_Address_Postal_Code",
            ],
        )
    )
    phone = normalize_phone(
        _first_present(
            raw,
            [
                "Phone",
                "phone",
                "Practice_Phone",
                "prescriber_phone",
                "Provider_Business_Practice_Location_Address_Telephone_Number",
            ],
        )
    )
    email = normalize_email(_first_present(raw, ["Email", "email"]))
    org = normalize_text(
        _first_present(
            raw,
            [
                "Primary_Parent",
                "primary_org",
                "practice",
                "org_as_written",
                "Provider_Organization_Name",
            ],
        )
    )
    specialty_raw = _first_present(
        raw,
        ["Specialty", "specialty_desc", "recipient_specialty", "Taxonomy_Code_1", "Healthcare_Provider_Taxonomy_Code_1"],
    )
    specialty = specialty_family(specialty_raw)
    specific = specialty_label(specialty_raw)
    address = normalize_text(
        _first_present(
            raw,
            [
                "Address",
                "address",
                "Practice_Address",
                "Provider_First_Line_Business_Practice_Location_Address",
            ],
        )
    )

    if profile_flags.get("venue_is_not_practice"):
        practice_city, practice_state = "", ""
        venue_city, venue_state = city, state
    else:
        practice_city, practice_state = city, state
        venue_city, venue_state = "", ""

    date_raw = _first_present(
        raw,
        [
            "Last_Modified",
            "last_updated",
            "service_date",
            "event_date",
            "payment_date",
            "enroll_date",
            "note_date",
            "created_date",
            "Enumeration_Date",
            "Provider_Enumeration_Date",
        ],
    )
    iso_date, date_flags = parse_date(date_raw)
    license_no = normalize_text(_first_present(raw, ["State_License", "license_no", "License_Number_1"]))
    license_state = normalize_text(_first_present(raw, ["License_State_1"]) or practice_state).upper()

    # former / other last name from NPPES
    other_last = normalize_text(raw.get("Provider_Other_Last_Name") or "")
    suffix_from_nppes = normalize_text(raw.get("Provider_Name_Suffix") or "").upper()
    if suffix_from_nppes and suffix_from_nppes not in parsed["suffixes"]:
        parsed["suffixes"] = [*parsed["suffixes"], suffix_from_nppes]

    return {
        "source_key": source_key,
        "name": parsed,
        "other_last": other_last.lower().replace("-", "") if other_last else "",
        "organization": org,
        "address": address,
        "city": practice_city,
        "state": practice_state,
        "postal": postal,
        "zip3": postal[:3] if postal else "",
        "phone": phone,
        "email": email,
        "specialty": specialty,
        "specialty_raw": normalize_text(specialty_raw),
        "specialty_label": specific,
        "license_no": license_no,
        "license_state": license_state,
        "record_date": iso_date,
        "date_flags": date_flags,
        "venue_city": venue_city,
        "venue_state": venue_state,
        "soundex_last": soundex(parsed["last_norm"]),
        "is_non_person": parsed["is_non_person"],
        "note_text": normalize_text(raw.get("note_text") or "") if source_key == "notes" else "",
    }
