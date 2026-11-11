from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class SourceProfile:
    key: str
    label: str
    filename: str
    id_fields: Tuple[str, ...]
    npi_fields: Tuple[str, ...] = ()
    name_fields: Tuple[str, ...] = ()
    trust: float = 0.5
    is_reference: bool = False
    exclude_from_matching: bool = False
    answer_key: bool = False
    payment_source: bool = False
    is_notes: bool = False
    venue_is_not_practice: bool = False
    requires_compliance_review: bool = False


DEFAULT_SOURCE_PROFILES: Dict[str, SourceProfile] = {
    "nppes": SourceProfile(
        key="nppes",
        label="NPPES Reference",
        filename="01_nppes_reference.csv",
        id_fields=("NPI",),
        npi_fields=("NPI",),
        name_fields=("Provider_First_Name", "Provider_Middle_Name", "Provider_Last_Name", "Provider_Organization_Name"),
        trust=1.0,
        is_reference=True,
        exclude_from_matching=True,
    ),
    "legacy_master": SourceProfile(
        key="legacy_master",
        label="Legacy Customer Master",
        filename="02_legacy_customer_master.csv",
        id_fields=("master_id",),
        npi_fields=("npi",),
        name_fields=("full_name",),
        trust=0.55,
    ),
    "crm": SourceProfile(
        key="crm",
        label="CRM Accounts",
        filename="03_crm_accounts.csv",
        id_fields=("Account_ID",),
        npi_fields=("NPI_vod",),
        name_fields=("Account_Name",),
        trust=0.6,
    ),
    "claims": SourceProfile(
        key="claims",
        label="Claims",
        filename="04_claims.csv",
        id_fields=("claim_id",),
        npi_fields=("prescriber_npi", "billing_npi"),
        name_fields=("prescriber_name",),
        trust=0.7,
    ),
    "events": SourceProfile(
        key="events",
        label="Events",
        filename="05_events.csv",
        id_fields=("event_id",),
        npi_fields=(),
        name_fields=("attendee",),
        trust=0.45,
        venue_is_not_practice=True,
    ),
    "payments": SourceProfile(
        key="payments",
        label="Payments / Transparency",
        filename="06_payments.csv",
        id_fields=("payment_id",),
        npi_fields=("recipient_npi",),
        name_fields=("recipient_first", "recipient_last"),
        trust=0.75,
        payment_source=True,
        requires_compliance_review=False,
    ),
    "hub": SourceProfile(
        key="hub",
        label="Hub Enrollments",
        filename="07_hub_enrollments.csv",
        id_fields=("enrollment_id",),
        npi_fields=("prescriber_npi",),
        name_fields=("prescriber_name",),
        trust=0.65,
    ),
    "notes": SourceProfile(
        key="notes",
        label="Call Notes & Inquiries",
        filename="08_call_notes_and_inquiries.csv",
        id_fields=("note_id",),
        npi_fields=(),
        name_fields=(),
        trust=0.35,
        is_notes=True,
        exclude_from_matching=True,  # free-text; linked via extraction/review, not pairwise match
    ),
}


@dataclass
class MatchThresholds:
    auto_link: float = 0.95
    review_low: float = 0.70
    clear_winner_margin: float = 0.08
    max_rounds: int = 5


FIELD_WEIGHTS: Dict[str, float] = {
    "npi": 0.45,
    "license": 0.28,
    "name": 0.22,
    "former_name": 0.18,
    "suffix": 0.16,
    "specialty": 0.12,
    "phone": 0.08,
    "email": 0.10,
    "zip3": 0.09,
    "city_state": 0.10,
    "organization": 0.07,
    "credential": 0.05,
}

PLACEHOLDER_NPIS = {"0000000000", "1111111111", "1234567890", "9999999999", "0000000001"}

NON_PERSON_NAME_TOKENS = {
    "office staff",
    "front desk",
    "billing office",
    "infusion suite",
    "pharmacy",
    "clinic staff",
    "unknown",
    "n/a",
    "na",
}

# Taxonomy family hints used when NPPES only has taxonomy codes
TAXONOMY_FAMILY_HINTS: Dict[str, str] = {
    "207RX0202X": "oncology",
    "207RH0003X": "oncology",
    "207N00000X": "dermatology",
    "207RC0000X": "cardiology",
    "208000000X": "pediatrics",
    "207RE0101X": "endocrinology",
    "207RH0000X": "hematology",
    "363L00000X": "nursing",
}

# Specific labels. Hematology and dermatology must not collapse into oncology.
TAXONOMY_LABELS: Dict[str, str] = {
    "207RX0202X": "Medical Oncology",
    "207RH0003X": "Hematology & Oncology",
    "207N00000X": "Dermatology",
    "207RC0000X": "Cardiovascular Disease",
    "208000000X": "Pediatrics",
    "207RE0101X": "Endocrinology",
    "207RH0000X": "Hematology",
    "363L00000X": "Nurse Practitioner",
    "193200000X": "Multi-Specialty Group",
    "282N00000X": "General Acute Care Hospital",
}

# Payments are not all compliance cases. The resolver sends only suspected identity problems.
# Keep the profile flag false so a valid NPI is not forced into review.
