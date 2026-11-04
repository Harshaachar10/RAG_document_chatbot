#!/usr/bin/env python3
"""Generate coherent fixed-seed CSV and document fixtures for Doctor Intelligence."""
from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.csv_io import write_csv_dicts  # noqa: E402

RNG = random.Random(42)

SPECIALTIES = [
    "Oncology",
    "Cardiology",
    "Endocrinology",
    "Neurology",
    "Rheumatology",
    "Hematology",
    "Internal Medicine",
    "Pulmonology",
]
STATES = ["MA", "NY", "CA", "IL", "TX", "FL", "PA", "WA", "NJ", "OH"]
CITIES = {
    "MA": ["Boston", "Cambridge", "Worcester"],
    "NY": ["New York", "Buffalo", "Rochester"],
    "CA": ["San Francisco", "Los Angeles", "San Diego"],
    "IL": ["Chicago", "Evanston"],
    "TX": ["Houston", "Dallas", "Austin"],
    "FL": ["Miami", "Tampa"],
    "PA": ["Philadelphia", "Pittsburgh"],
    "WA": ["Seattle", "Tacoma"],
    "NJ": ["Newark", "Princeton"],
    "OH": ["Cleveland", "Columbus"],
}
FIRST = [
    "James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David", "Jennifer",
    "William", "Elizabeth", "Richard", "Barbara", "Joseph", "Susan", "Thomas", "Jessica",
    "Charles", "Sarah", "Christopher", "Karen", "Daniel", "Nancy", "Matthew", "Lisa",
    "Anthony", "Betty", "Mark", "Margaret", "Donald", "Sandra", "Steven", "Ashley",
    "Paul", "Dorothy", "Andrew", "Kimberly", "Joshua", "Emily", "Kenneth", "Donna",
]
LAST = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]
ORGS = [
    "Riverbend Medical Center", "Summit Care Clinic", "Harborview Specialists",
    "Northside Oncology Group", "Cedar Grove Hospital", "Pacific Health Partners",
    "Lakeside Physician Associates", "Metro Cardiology Associates", "Sunrise Rheumatology",
    "Pioneer Hematology Clinic", "Evergreen Neurology", "Atlas Internal Medicine",
]


def iso_dt(d: datetime) -> str:
    return d.replace(tzinfo=timezone.utc, microsecond=0).isoformat().replace("+00:00", "Z")


def iso_date(d: date) -> str:
    return d.isoformat()


def doctor_id(n: int) -> str:
    return f"HCP-{n:06d}"


def make_doc(doc_id: str, title: str, doc_type: str, source_id: str, version: str,
             document_date: str, submitted_at: str, submitted_by: Optional[str],
             submitted_to: Optional[str], pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "document_id": doc_id,
        "title": title,
        "document_type": doc_type,
        "source_id": source_id,
        "version": version,
        "document_date": document_date,
        "submitted_at": submitted_at,
        "submitted_by": submitted_by,
        "submitted_to": submitted_to,
        "pages": pages,
    }


def block(page: int, idx: int, text: str, kind: str = "paragraph") -> Dict[str, Any]:
    return {"block_id": f"p{page}-b{idx}", "kind": kind, "text": text, "highlightable": True}


def main() -> None:
    csv_dir = BACKEND_ROOT / "data" / "csv"
    docs_dir = BACKEND_ROOT / "data" / "documents"
    mock_dir = BACKEND_ROOT / "data" / "mock"
    csv_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    mock_dir.mkdir(parents=True, exist_ok=True)
    for existing in docs_dir.glob("*.json"):
        existing.unlink()

    sources = [
        {"source_id": "SRC-CRM", "source_name": "CRM Directory", "source_type": "crm_directory",
         "description": "Commercial CRM HCP directory extract", "snapshot_version": "2026.09.01",
         "updated_at": "2026-09-01T12:00:00Z"},
        {"source_id": "SRC-SPEAKER", "source_name": "Speaker & Event Registrations", "source_type": "speaker_events",
         "description": "Speaker bureau and event registration feeds", "snapshot_version": "2026.09.10",
         "updated_at": "2026-09-10T15:30:00Z"},
        {"source_id": "SRC-PAY", "source_name": "Payments & Invoices", "source_type": "payments_invoices",
         "description": "Speaker and consulting payment invoices", "snapshot_version": "2026.09.05",
         "updated_at": "2026-09-05T09:00:00Z"},
        {"source_id": "SRC-RX", "source_name": "Prescriber Activity", "source_type": "prescriber_activity",
         "description": "Doctor-only aggregate prescribing activity", "snapshot_version": "2026.08.31",
         "updated_at": "2026-08-31T18:00:00Z"},
        {"source_id": "SRC-CRED", "source_name": "Credential & Practice Forms", "source_type": "credential_forms",
         "description": "Credential updates and practice-change forms", "snapshot_version": "2026.09.12",
         "updated_at": "2026-09-12T11:20:00Z"},
        {"source_id": "SRC-NOTES", "source_name": "Medical & Rep Notes", "source_type": "rep_notes",
         "description": "Field notes without patient information", "snapshot_version": "2026.09.08",
         "updated_at": "2026-09-08T14:45:00Z"},
    ]

    doctors: List[Dict[str, Any]] = []
    aliases: List[Dict[str, Any]] = []
    affiliations: List[Dict[str, Any]] = []
    source_records: List[Dict[str, Any]] = []
    source_links: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []
    field_provenance: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    reviews: List[Dict[str, Any]] = []
    review_candidates: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    documents_meta: List[Dict[str, Any]] = []
    audit_events: List[Dict[str, Any]] = []
    documents_content: Dict[str, Dict[str, Any]] = {}
    recommendations: Dict[str, Any] = {}

    alias_n = aff_n = sr_n = link_n = obs_n = prov_n = ev_n = evid_n = rev_n = aud_n = 1

    def add_alias(did: str, name: str, atype: str, obs_date: str, evid: Optional[str] = None) -> str:
        nonlocal alias_n
        aid = f"ALS-{alias_n:05d}"
        alias_n += 1
        aliases.append({
            "alias_id": aid, "doctor_id": did, "name": name, "alias_type": atype,
            "observation_date": obs_date, "evidence_id": evid,
        })
        return aid

    def add_aff(did: str, org: str, city: str, state: str, status: str, primary: bool,
                eff_from: Optional[str], eff_to: Optional[str], observed: str,
                evid: Optional[str] = None, address: Optional[str] = None) -> str:
        nonlocal aff_n
        aid = f"AFF-{aff_n:05d}"
        aff_n += 1
        affiliations.append({
            "affiliation_id": aid, "doctor_id": did, "organization_name": org,
            "address_line": address or f"100 Main St", "city": city, "state": state,
            "relationship_status": status, "is_primary": "true" if primary else "false",
            "effective_from": eff_from, "effective_to": eff_to, "observed_at": observed,
            "evidence_id": evid,
        })
        return aid

    def add_sr(**kwargs: Any) -> str:
        nonlocal sr_n
        sid = kwargs.get("source_record_id") or f"SR-{sr_n:06d}"
        sr_n += 1
        row = {
            "source_record_id": sid,
            "source_id": kwargs["source_id"],
            "record_kind": kwargs["record_kind"],
            "recorded_name": kwargs.get("recorded_name"),
            "specialty": kwargs.get("specialty"),
            "practice_name": kwargs.get("practice_name"),
            "address_line": kwargs.get("address_line"),
            "city": kwargs.get("city"),
            "state": kwargs.get("state"),
            "email": kwargs.get("email"),
            "phone": kwargs.get("phone"),
            "credential_reference": kwargs.get("credential_reference"),
            "document_id": kwargs.get("document_id"),
            "record_date": kwargs.get("record_date"),
            "submitted_at": kwargs.get("submitted_at"),
            "submitted_by": kwargs.get("submitted_by"),
            "submitted_to": kwargs.get("submitted_to"),
            "resolution_status": kwargs.get("resolution_status", "linked"),
        }
        source_records.append(row)
        return sid

    def add_link(srid: str, did: Optional[str], status: str, basis: str,
                 score: Optional[float] = None, review_id: Optional[str] = None) -> str:
        nonlocal link_n
        lid = f"LNK-{link_n:06d}"
        link_n += 1
        source_links.append({
            "link_id": lid, "source_record_id": srid, "doctor_id": did,
            "link_status": status, "decision_basis": basis,
            "demo_score": "" if score is None else f"{score:.2f}",
            "review_id": review_id,
        })
        return lid

    def add_obs(did: str, srid: str, field: str, value: str, recorded: str,
                evid: Optional[str] = None, eff_from: Optional[str] = None,
                eff_to: Optional[str] = None) -> str:
        nonlocal obs_n
        oid = f"OBS-{obs_n:06d}"
        obs_n += 1
        observations.append({
            "observation_id": oid, "doctor_id": did, "source_record_id": srid,
            "field_name": field, "observed_value": value, "effective_from": eff_from,
            "effective_to": eff_to, "recorded_at": recorded, "evidence_id": evid,
        })
        return oid

    def add_prov(did: str, field: str, value: str, obs_id: str, reason: str,
                 review_id: Optional[str] = None, version: int = 1) -> str:
        nonlocal prov_n
        pid = f"PRV-{prov_n:06d}"
        prov_n += 1
        field_provenance.append({
            "provenance_id": pid, "doctor_id": did, "field_name": field,
            "selected_value": value, "observation_id": obs_id,
            "selection_reason": reason, "review_id": review_id, "version": version,
        })
        return pid

    def add_event(**kwargs: Any) -> str:
        nonlocal ev_n
        eid = f"EVT-{ev_n:06d}"
        ev_n += 1
        events.append({
            "event_id": eid,
            "doctor_id": kwargs["doctor_id"],
            "event_type": kwargs["event_type"],
            "title": kwargs["title"],
            "description": kwargs.get("description"),
            "previous_value": kwargs.get("previous_value"),
            "new_value": kwargs.get("new_value"),
            "document_date": kwargs.get("document_date"),
            "submitted_at": kwargs.get("submitted_at"),
            "submitted_to": kwargs.get("submitted_to"),
            "effective_date": kwargs.get("effective_date"),
            "recorded_at": kwargs.get("recorded_at"),
            "review_status": kwargs.get("review_status"),
            "evidence_id": kwargs.get("evidence_id"),
        })
        return eid

    def add_evidence(**kwargs: Any) -> str:
        nonlocal evid_n
        eid = kwargs.get("evidence_id") or f"EVD-{evid_n:05d}"
        evid_n += 1
        evidence.append({
            "evidence_id": eid,
            "source_record_id": kwargs.get("source_record_id"),
            "document_id": kwargs.get("document_id"),
            "document_version": kwargs.get("document_version"),
            "page_number": kwargs.get("page_number"),
            "block_id": kwargs.get("block_id"),
            "quoted_text": kwargs.get("quoted_text"),
            "source_field": kwargs.get("source_field"),
            "source_snapshot": kwargs.get("source_snapshot"),
            "citation_label": kwargs.get("citation_label"),
        })
        return eid

    def add_review(**kwargs: Any) -> str:
        nonlocal rev_n
        rid = kwargs.get("review_id") or f"REV-{rev_n:05d}"
        rev_n += 1
        reviews.append({
            "review_id": rid,
            "doctor_id": kwargs.get("doctor_id"),
            "case_type": kwargs["case_type"],
            "title": kwargs["title"],
            "severity": kwargs.get("severity", "medium"),
            "status": kwargs.get("status", "pending"),
            "source_record_id": kwargs.get("source_record_id"),
            "candidate_doctor_id": kwargs.get("candidate_doctor_id"),
            "proposed_field": kwargs.get("proposed_field"),
            "proposed_value": kwargs.get("proposed_value"),
            "recommendation_id": kwargs.get("recommendation_id"),
            "created_at": kwargs.get("created_at"),
            "updated_at": kwargs.get("updated_at"),
            "version": kwargs.get("version", 1),
        })
        return rid

    def add_audit(**kwargs: Any) -> str:
        nonlocal aud_n
        aid = f"AUD-{aud_n:05d}"
        aud_n += 1
        audit_events.append({
            "audit_id": aid,
            "doctor_id": kwargs.get("doctor_id"),
            "review_id": kwargs.get("review_id"),
            "action": kwargs["action"],
            "actor_label": kwargs.get("actor_label", "Demo Steward"),
            "summary": kwargs["summary"],
            "occurred_at": kwargs["occurred_at"],
            "is_seeded": "true" if kwargs.get("is_seeded", True) else "false",
        })
        return aid

    def store_doc(content: Dict[str, Any]) -> None:
        did = content["document_id"]
        documents_content[did] = content
        documents_meta.append({
            "document_id": did,
            "title": content["title"],
            "document_type": content["document_type"],
            "source_id": content["source_id"],
            "version": content["version"],
            "document_date": content["document_date"],
            "submitted_at": content["submitted_at"],
            "submitted_by": content.get("submitted_by"),
            "submitted_to": content.get("submitted_to"),
            "content_file": f"{did}.json",
        })

    # ---------- Showcase: Sarah Lee-Kim HCP-000123 ----------
    sarah_id = "HCP-000123"
    oakridge_aff = "AFF-SARAH-OAK"
    lakeshore_aff = "AFF-SARAH-LAKE"
    doctors.append({
        "doctor_id": sarah_id,
        "preferred_name": "Sarah Lee-Kim",
        "given_name": "Sarah",
        "family_name": "Lee-Kim",
        "specialty": "Oncology",
        "primary_affiliation_id": oakridge_aff,
        "city": "Boston",
        "state": "MA",
        "professional_email": "sarah.lee-kim@example.com",
        "professional_phone": "+1-555-010-1234",
        "official_npi": None,
        "npi_status": "Not verified",
        "identity_status": "active",
        "updated_at": "2026-09-02T16:00:00Z",
        "version": 3,
    })

    # Documents DOC-001..004
    doc1_quote_name = "Dr. Sarah Lee"
    doc1_quote_cred = "Credential: MA-DEMO-7421"
    doc1 = make_doc(
        "DOC-001", "Speaker Invoice — Sarah Lee", "invoice", "SRC-PAY", "1",
        "2024-02-12", "2024-02-12T10:00:00Z", "Speaker Bureau Ops", "Finance",
        [{"page_number": 1, "label": "Page 1", "blocks": [
            block(1, 1, "SPEAKER HONORARIUM INVOICE", "heading"),
            block(1, 2, "Invoice Date: 2024-02-12"),
            block(1, 3, f"Payee: {doc1_quote_name}"),
            block(1, 4, "Practice: Oakridge Oncology"),
            block(1, 5, doc1_quote_cred),
            block(1, 6, "Service: Advisory board presentation (synthetic demo content)"),
            block(1, 7, "Amount: $2,500.00 (fictional)"),
        ]}],
    )
    store_doc(doc1)

    doc2_quote = "Registrant: S. Lee"
    doc2_email = "Email: sarah.lee-kim@example.com"
    doc2 = make_doc(
        "DOC-002", "Event Registration — S. Lee", "event_registration", "SRC-SPEAKER", "1",
        "2025-06-18", "2025-06-18T14:22:00Z", "Event Portal", "Medical Affairs",
        [{"page_number": 1, "label": "Page 1", "blocks": [
            block(1, 1, "ONCOLOGY SYMPOSIUM REGISTRATION", "heading"),
            block(1, 2, "Event Date: 2025-06-18"),
            block(1, 3, doc2_quote),
            block(1, 4, "Affiliation: Oakridge Oncology"),
            block(1, 5, doc2_email),
            block(1, 6, "Role: Faculty speaker (synthetic)"),
        ]}],
    )
    store_doc(doc2)

    doc3_quote = "Dr. Sarah Lee-Kim, formerly Dr. Sarah Lee"
    doc3 = make_doc(
        "DOC-003", "Credential Update — Lee-Kim", "credential_update", "SRC-CRED", "1",
        "2026-08-10", "2026-08-10T09:15:00Z", "Dr. Sarah Lee-Kim", "Credentialing Office",
        [{"page_number": 1, "label": "Page 1", "blocks": [
            block(1, 1, "CREDENTIAL UPDATE FORM", "heading"),
            block(1, 2, "Document Date: 2026-08-10"),
            block(1, 3, doc3_quote),
            block(1, 4, "Credential Reference: MA-DEMO-7421"),
            block(1, 5, "Specialty: Oncology"),
            block(1, 6, "Preferred professional email: sarah.lee-kim@example.com"),
        ]}],
    )
    store_doc(doc3)

    doc4_quote = "New affiliation: Lakeshore Cancer Institute. Effective September 1, 2026."
    doc4 = make_doc(
        "DOC-004", "Practice Change Form — Lakeshore", "practice_change", "SRC-CRED", "1",
        "2026-09-02", "2026-09-02T11:40:00Z", "Dr. Sarah Lee-Kim", "Provider Relations",
        [{"page_number": 1, "label": "Page 1", "blocks": [
            block(1, 1, "PRACTICE CHANGE NOTIFICATION", "heading"),
            block(1, 2, "Document Date: 2026-09-02"),
            block(1, 3, "Physician: Dr. Sarah Lee-Kim"),
            block(1, 4, doc4_quote),
            block(1, 5, "Current known affiliation on file: Oakridge Oncology"),
            block(1, 6, "No cessation date provided for prior affiliation."),
        ]}],
    )
    store_doc(doc4)

    # Sarah source records
    sr_pay = add_sr(
        source_record_id="SR-SARAH-PAY", source_id="SRC-PAY", record_kind="supporting_transaction",
        recorded_name="Dr. Sarah Lee", specialty="Oncology", practice_name="Oakridge Oncology",
        address_line="200 Oakridge Ave", city="Boston", state="MA",
        email="sarah.lee-kim@example.com", phone="+1-555-010-1234",
        credential_reference="MA-DEMO-7421", document_id="DOC-001",
        record_date="2024-02-12", submitted_at="2024-02-12T10:00:00Z",
        submitted_by="Speaker Bureau Ops", submitted_to="Finance", resolution_status="linked",
    )
    sr_evt = add_sr(
        source_record_id="SR-SARAH-EVT", source_id="SRC-SPEAKER", record_kind="identity_entry",
        recorded_name="S. Lee", specialty="Oncology", practice_name="Oakridge",
        city="Boston", state="MA", email="sarah.lee-kim@example.com",
        credential_reference="MA-DEMO-7421", document_id="DOC-002",
        record_date="2025-06-18", submitted_at="2025-06-18T14:22:00Z",
        submitted_by="Event Portal", submitted_to="Medical Affairs", resolution_status="linked",
    )
    sr_cred = add_sr(
        source_record_id="SR-SARAH-CRED", source_id="SRC-CRED", record_kind="identity_entry",
        recorded_name="Dr. Sarah Lee-Kim", specialty="Oncology", practice_name="Oakridge Oncology",
        city="Boston", state="MA", email="sarah.lee-kim@example.com",
        credential_reference="MA-DEMO-7421", document_id="DOC-003",
        record_date="2026-08-10", submitted_at="2026-08-10T09:15:00Z",
        submitted_by="Dr. Sarah Lee-Kim", submitted_to="Credentialing Office",
        resolution_status="linked",
    )
    sr_prac = add_sr(
        source_record_id="SR-SARAH-PRAC", source_id="SRC-CRED", record_kind="identity_entry",
        recorded_name="Dr. Sarah Lee-Kim", specialty="Oncology",
        practice_name="Lakeshore Cancer Institute", city="Boston", state="MA",
        email="sarah.lee-kim@example.com", credential_reference="MA-DEMO-7421",
        document_id="DOC-004", record_date="2026-09-02",
        submitted_at="2026-09-02T11:40:00Z", submitted_by="Dr. Sarah Lee-Kim",
        submitted_to="Provider Relations", resolution_status="linked",
    )
    sr_crm = add_sr(
        source_record_id="SR-SARAH-CRM", source_id="SRC-CRM", record_kind="identity_entry",
        recorded_name="Sarah Lee-Kim", specialty="Oncology", practice_name="Oakridge Oncology",
        city="Boston", state="MA", email="sarah.lee-kim@example.com",
        credential_reference="MA-DEMO-7421", record_date="2026-07-01",
        submitted_at="2026-07-01T08:00:00Z", resolution_status="linked",
    )

    evid_pay_name = add_evidence(
        evidence_id="EVD-SARAH-01", source_record_id=sr_pay, document_id="DOC-001",
        document_version="1", page_number=1, block_id="p1-b3", quoted_text=doc1_quote_name,
        source_field="recorded_name", source_snapshot="2026.09.05",
        citation_label="DOC-001 p.1 — Payee name",
    )
    evid_pay_cred = add_evidence(
        evidence_id="EVD-SARAH-02", source_record_id=sr_pay, document_id="DOC-001",
        document_version="1", page_number=1, block_id="p1-b5", quoted_text=doc1_quote_cred,
        source_field="credential_reference", source_snapshot="2026.09.05",
        citation_label="DOC-001 p.1 — Credential",
    )
    evid_evt = add_evidence(
        evidence_id="EVD-SARAH-03", source_record_id=sr_evt, document_id="DOC-002",
        document_version="1", page_number=1, block_id="p1-b3", quoted_text=doc2_quote,
        source_field="recorded_name", source_snapshot="2026.09.10",
        citation_label="DOC-002 p.1 — Registrant",
    )
    evid_evt_email = add_evidence(
        evidence_id="EVD-SARAH-04", source_record_id=sr_evt, document_id="DOC-002",
        document_version="1", page_number=1, block_id="p1-b5", quoted_text=doc2_email,
        source_field="email", source_snapshot="2026.09.10",
        citation_label="DOC-002 p.1 — Email",
    )
    evid_cred = add_evidence(
        evidence_id="EVD-SARAH-05", source_record_id=sr_cred, document_id="DOC-003",
        document_version="1", page_number=1, block_id="p1-b3", quoted_text=doc3_quote,
        source_field="recorded_name", source_snapshot="2026.09.12",
        citation_label="DOC-003 p.1 — Name change",
    )
    evid_prac = add_evidence(
        evidence_id="EVD-SARAH-06", source_record_id=sr_prac, document_id="DOC-004",
        document_version="1", page_number=1, block_id="p1-b4", quoted_text=doc4_quote,
        source_field="practice_name", source_snapshot="2026.09.12",
        citation_label="DOC-004 p.1 — New affiliation",
    )
    evid_crm = add_evidence(
        evidence_id="EVD-SARAH-07", source_record_id=sr_crm, document_id=None,
        document_version=None, page_number=None, block_id=None,
        quoted_text="Sarah Lee-Kim", source_field="recorded_name",
        source_snapshot="2026.09.01", citation_label="CRM row SR-SARAH-CRM",
    )

    for srid, basis, score in [
        (sr_pay, "supporting_transaction_link", 0.91),
        (sr_evt, "email_and_credential", 0.94),
        (sr_cred, "documented_name_change", 0.98),
        (sr_prac, "practice_change_form", 0.96),
        (sr_crm, "directory_match", 0.93),
    ]:
        add_link(srid, sarah_id, "accepted", basis, score)

    affiliations.append({
        "affiliation_id": oakridge_aff, "doctor_id": sarah_id,
        "organization_name": "Oakridge Oncology", "address_line": "200 Oakridge Ave",
        "city": "Boston", "state": "MA", "relationship_status": "current",
        "is_primary": "true", "effective_from": "2020-01-15", "effective_to": None,
        "observed_at": "2026-07-01", "evidence_id": evid_crm,
    })
    affiliations.append({
        "affiliation_id": lakeshore_aff, "doctor_id": sarah_id,
        "organization_name": "Lakeshore Cancer Institute", "address_line": "88 Lakeshore Dr",
        "city": "Boston", "state": "MA", "relationship_status": "proposed",
        "is_primary": "false", "effective_from": "2026-09-01", "effective_to": None,
        "observed_at": "2026-09-02", "evidence_id": evid_prac,
    })
    aff_n = max(aff_n, 100)

    add_alias(sarah_id, "Sarah Lee-Kim", "preferred", "2026-08-10", evid_cred)
    add_alias(sarah_id, "Sarah Lee", "previous_name", "2024-02-12", evid_pay_name)
    add_alias(sarah_id, "S. Lee", "abbreviation", "2025-06-18", evid_evt)
    add_alias(sarah_id, "Dr. Sarah Lee", "spelling_variant", "2024-02-12", evid_pay_name)

    obs_name = add_obs(sarah_id, sr_cred, "preferred_name", "Sarah Lee-Kim",
                       "2026-08-10T09:15:00Z", evid_cred, eff_from="2026-08-10")
    add_prov(sarah_id, "preferred_name", "Sarah Lee-Kim", obs_name,
             "Approved from credential update form", version=2)
    obs_aff = add_obs(sarah_id, sr_crm, "primary_affiliation", "Oakridge Oncology",
                      "2026-07-01T08:00:00Z", evid_crm, eff_from="2020-01-15")
    add_prov(sarah_id, "primary_affiliation", "Oakridge Oncology", obs_aff,
             "Current known affiliation pending Lakeshore review")
    add_obs(sarah_id, sr_prac, "primary_affiliation", "Lakeshore Cancer Institute",
            "2026-09-02T11:40:00Z", evid_prac, eff_from="2026-09-01")

    add_event(
        doctor_id=sarah_id, event_type="name_variation_observed",
        title="Name variation observed", description="Invoice recorded Dr. Sarah Lee",
        previous_value=None, new_value="Dr. Sarah Lee", document_date="2024-02-12",
        submitted_at="2024-02-12T10:00:00Z", submitted_to="Finance",
        effective_date=None, recorded_at="2024-02-12T10:00:00Z",
        review_status="accepted", evidence_id=evid_pay_name,
    )
    add_event(
        doctor_id=sarah_id, event_type="record_entry",
        title="Event registration linked", description="S. Lee registered for symposium",
        previous_value=None, new_value="S. Lee", document_date="2025-06-18",
        submitted_at="2025-06-18T14:22:00Z", submitted_to="Medical Affairs",
        effective_date=None, recorded_at="2025-06-18T14:22:00Z",
        review_status="accepted", evidence_id=evid_evt,
    )
    add_event(
        doctor_id=sarah_id, event_type="name_change_documented",
        title="Name change documented",
        description="Credential update documents preferred name Sarah Lee-Kim",
        previous_value="Sarah Lee", new_value="Sarah Lee-Kim",
        document_date="2026-08-10", submitted_at="2026-08-10T09:15:00Z",
        submitted_to="Credentialing Office", effective_date="2026-08-10",
        recorded_at="2026-08-10T09:15:00Z", review_status="approved",
        evidence_id=evid_cred,
    )
    add_event(
        doctor_id=sarah_id, event_type="affiliation_observed",
        title="Affiliation observed",
        description="Practice-change form proposes Lakeshore Cancer Institute",
        previous_value="Oakridge Oncology", new_value="Lakeshore Cancer Institute",
        document_date="2026-09-02", submitted_at="2026-09-02T11:40:00Z",
        submitted_to="Provider Relations", effective_date="2026-09-01",
        recorded_at="2026-09-02T11:40:00Z", review_status="pending",
        evidence_id=evid_prac,
    )

    sarah_review = add_review(
        review_id="REV-SARAH-AFF", doctor_id=sarah_id, case_type="affiliation_update",
        title="Proposed affiliation: Lakeshore Cancer Institute",
        severity="high", status="pending", source_record_id=sr_prac,
        proposed_field="primary_affiliation",
        proposed_value="Lakeshore Cancer Institute",
        recommendation_id="REC-SARAH-AFF",
        created_at="2026-09-02T12:00:00Z", updated_at="2026-09-02T12:00:00Z", version=1,
    )
    recommendations["REC-SARAH-AFF"] = {
        "recommendation_id": "REC-SARAH-AFF",
        "doctor_id": sarah_id,
        "summary": "Practice-change form documents a new Lakeshore affiliation effective 2026-09-01 while Oakridge remains observed without cessation evidence.",
        "simulated_recommendation": "Approve affiliation update; retain Oakridge as historical observation until cessation evidence exists.",
        "demo_match_score": 0.96,
        "decision_method": "steward_review",
        "ambiguities": ["No explicit end date for Oakridge Oncology"],
        "constraints": ["Do not invent affiliation end dates"],
        "evidence_refs": [evid_prac, evid_cred],
        "side_by_side": [
            {"label": "Current known", "affiliation": "Oakridge Oncology", "name": "Sarah Lee-Kim"},
            {"label": "Proposed", "affiliation": "Lakeshore Cancer Institute", "name": "Sarah Lee-Kim",
             "effective_from": "2026-09-01"},
        ],
        "evidence_rows": [
            {"observation": "New affiliation statement", "supports": True,
             "explanation": "Form explicitly states Lakeshore effective Sept 1, 2026",
             "citation": evid_prac},
            {"observation": "Oakridge cessation", "supports": False,
             "explanation": "No cessation language present", "citation": evid_prac},
        ],
    }
    recommendations[sarah_id] = {
        "recommendation_id": "REC-SARAH-MATCH",
        "doctor_id": sarah_id,
        "summary": "Multiple identity entries share credential MA-DEMO-7421 and professional email across name variations Sarah Lee / S. Lee / Sarah Lee-Kim.",
        "simulated_recommendation": "Treat records as one doctor identity; keep supporting invoice as transaction, not a duplicate profile.",
        "demo_match_score": 0.95,
        "decision_method": "precomputed_demo",
        "review_status": "partially_reviewed",
        "ambiguities": ["Abbreviation S. Lee alone would be weak without email corroboration"],
        "constraints": ["Official NPI not verified in this demo"],
        "side_by_side": [
            {"source": "SRC-PAY", "name": "Dr. Sarah Lee", "credentials": "MA-DEMO-7421",
             "specialty": "Oncology", "email": "sarah.lee-kim@example.com",
             "practice": "Oakridge Oncology", "observed_date": "2024-02-12"},
            {"source": "SRC-SPEAKER", "name": "S. Lee", "credentials": "MA-DEMO-7421",
             "specialty": "Oncology", "email": "sarah.lee-kim@example.com",
             "practice": "Oakridge", "observed_date": "2025-06-18"},
            {"source": "SRC-CRED", "name": "Dr. Sarah Lee-Kim", "credentials": "MA-DEMO-7421",
             "specialty": "Oncology", "email": "sarah.lee-kim@example.com",
             "practice": "Oakridge Oncology", "observed_date": "2026-08-10"},
        ],
        "evidence_rows": [
            {"observation": "Shared credential", "supports": True,
             "explanation": "MA-DEMO-7421 appears across invoice and credential form",
             "citation": evid_pay_cred},
            {"observation": "Documented name change", "supports": True,
             "explanation": doc3_quote, "citation": evid_cred},
        ],
    }
    add_audit(
        doctor_id=sarah_id, review_id=None, action="preferred_name_approved",
        actor_label="Demo Steward", summary="Approved preferred name Sarah Lee-Kim from DOC-003",
        occurred_at="2026-08-11T10:00:00Z", is_seeded=True,
    )

    # ---------- Two Priya Sharmas ----------
    priya_a = "HCP-000201"
    priya_b = "HCP-000202"
    doctors.append({
        "doctor_id": priya_a, "preferred_name": "Priya Sharma", "given_name": "Priya",
        "family_name": "Sharma", "specialty": "Cardiology",
        "primary_affiliation_id": "AFF-PRIYA-A", "city": "Chicago", "state": "IL",
        "professional_email": "priya.sharma.cardio@example.com",
        "professional_phone": "+1-555-020-1001", "official_npi": None,
        "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-20T12:00:00Z", "version": 1,
    })
    doctors.append({
        "doctor_id": priya_b, "preferred_name": "Priya Sharma", "given_name": "Priya",
        "family_name": "Sharma", "specialty": "Endocrinology",
        "primary_affiliation_id": "AFF-PRIYA-B", "city": "Houston", "state": "TX",
        "professional_email": "priya.sharma.endo@example.com",
        "professional_phone": "+1-555-020-2002", "official_npi": None,
        "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-21T12:00:00Z", "version": 1,
    })
    affiliations.append({
        "affiliation_id": "AFF-PRIYA-A", "doctor_id": priya_a,
        "organization_name": "Metro Cardiology Associates", "address_line": "10 Loop St",
        "city": "Chicago", "state": "IL", "relationship_status": "current",
        "is_primary": "true", "effective_from": "2019-03-01", "effective_to": None,
        "observed_at": "2026-08-01", "evidence_id": None,
    })
    affiliations.append({
        "affiliation_id": "AFF-PRIYA-B", "doctor_id": priya_b,
        "organization_name": "Gulf Coast Endocrine Clinic", "address_line": "55 Bayou Rd",
        "city": "Houston", "state": "TX", "relationship_status": "current",
        "is_primary": "true", "effective_from": "2018-06-15", "effective_to": None,
        "observed_at": "2026-08-01", "evidence_id": None,
    })
    for did, cred, city, state, org, email, src_suffix in [
        (priya_a, "IL-DEMO-1101", "Chicago", "IL", "Metro Cardiology Associates",
         "priya.sharma.cardio@example.com", "A"),
        (priya_b, "TX-DEMO-2202", "Houston", "TX", "Gulf Coast Endocrine Clinic",
         "priya.sharma.endo@example.com", "B"),
    ]:
        s1 = add_sr(
            source_record_id=f"SR-PRIYA-{src_suffix}-1", source_id="SRC-CRM",
            record_kind="identity_entry", recorded_name="Priya Sharma",
            specialty="Cardiology" if src_suffix == "A" else "Endocrinology",
            practice_name=org, city=city, state=state, email=email,
            credential_reference=cred, record_date="2026-05-01",
            resolution_status="linked",
        )
        s2 = add_sr(
            source_record_id=f"SR-PRIYA-{src_suffix}-2", source_id="SRC-SPEAKER",
            record_kind="identity_entry", recorded_name="P. Sharma",
            specialty="Cardiology" if src_suffix == "A" else "Endocrinology",
            practice_name=org, city=city, state=state, email=email,
            credential_reference=cred, record_date="2026-06-15",
            resolution_status="linked",
        )
        add_link(s1, did, "accepted", "credential_location", 0.9)
        add_link(s2, did, "accepted", "email_match", 0.88)
        add_alias(did, "Priya Sharma", "preferred", "2026-05-01")
        add_alias(did, "P. Sharma", "abbreviation", "2026-06-15")
        add_event(
            doctor_id=did, event_type="record_entry", title="Directory entry linked",
            description=f"CRM identity entry for {org}", new_value="Priya Sharma",
            document_date="2026-05-01", recorded_at="2026-05-01T12:00:00Z",
            review_status="accepted",
        )

    # Unresolved name-only Priya
    sr_priya_unk = add_sr(
        source_record_id="SR-PRIYA-UNK", source_id="SRC-NOTES",
        record_kind="note_observation", recorded_name="Priya Sharma",
        specialty=None, practice_name=None, city=None, state=None,
        record_date="2026-07-20", submitted_by="Field Rep Demo",
        resolution_status="unresolved",
    )
    add_link(sr_priya_unk, None, "unresolved", "name_only_insufficient", 0.35)
    priya_amb = add_review(
        review_id="REV-PRIYA-AMB", doctor_id=None, case_type="same_name_ambiguity",
        title="Same-name ambiguity: Priya Sharma (name-only note)",
        severity="high", status="pending", source_record_id=sr_priya_unk,
        recommendation_id="REC-PRIYA-AMB",
        created_at="2026-07-21T09:00:00Z", updated_at="2026-07-21T09:00:00Z", version=1,
    )
    review_candidates.append({
        "review_id": priya_amb, "candidate_doctor_id": priya_a,
        "demo_score": "0.42", "evidence_summary": "Shared name only; different likely specialty context",
    })
    review_candidates.append({
        "review_id": priya_amb, "candidate_doctor_id": priya_b,
        "demo_score": "0.40", "evidence_summary": "Shared name only; Houston vs unknown location",
    })
    recommendations["REC-PRIYA-AMB"] = {
        "recommendation_id": "REC-PRIYA-AMB",
        "summary": "Name-only note lacks credential, email, and location corroboration.",
        "simulated_recommendation": "Leave unresolved pending additional evidence; do not auto-assign.",
        "demo_match_score": 0.35,
        "decision_method": "steward_review",
        "ambiguities": ["Two distinct Priya Sharma masters already exist"],
        "constraints": ["Name alone is insufficient for linkage"],
        "evidence_refs": [],
        "side_by_side": [],
        "evidence_rows": [],
    }

    # ---------- Jr/Sr hard conflict ----------
    jr_id = "HCP-000301"
    sr_id = "HCP-000302"
    doctors.append({
        "doctor_id": jr_id, "preferred_name": "Robert Chen Jr", "given_name": "Robert",
        "family_name": "Chen", "specialty": "Neurology",
        "primary_affiliation_id": "AFF-CHEN-JR", "city": "Seattle", "state": "WA",
        "professional_email": "robert.chen.jr@example.com", "professional_phone": "+1-555-030-3001",
        "official_npi": None, "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-01T10:00:00Z", "version": 1,
    })
    doctors.append({
        "doctor_id": sr_id, "preferred_name": "Robert Chen Sr", "given_name": "Robert",
        "family_name": "Chen", "specialty": "Neurology",
        "primary_affiliation_id": "AFF-CHEN-SR", "city": "Seattle", "state": "WA",
        "professional_email": "robert.chen.sr@example.com", "professional_phone": "+1-555-030-3002",
        "official_npi": None, "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-01T10:00:00Z", "version": 1,
    })
    for did, aff, gen, cred, email in [
        (jr_id, "AFF-CHEN-JR", "Jr", "WA-DEMO-JR01", "robert.chen.jr@example.com"),
        (sr_id, "AFF-CHEN-SR", "Sr", "WA-DEMO-SR01", "robert.chen.sr@example.com"),
    ]:
        affiliations.append({
            "affiliation_id": aff, "doctor_id": did,
            "organization_name": "Evergreen Neurology", "address_line": "1 Pine St",
            "city": "Seattle", "state": "WA", "relationship_status": "current",
            "is_primary": "true", "effective_from": "2015-01-01", "effective_to": None,
            "observed_at": "2026-07-01", "evidence_id": None,
        })
        s1 = add_sr(
            source_record_id=f"SR-CHEN-{gen}-1", source_id="SRC-CRM",
            record_kind="identity_entry", recorded_name=f"Robert Chen {gen}",
            specialty="Neurology", practice_name="Evergreen Neurology",
            city="Seattle", state="WA", email=email, credential_reference=cred,
            record_date="2026-04-01", resolution_status="linked",
        )
        s2 = add_sr(
            source_record_id=f"SR-CHEN-{gen}-2", source_id="SRC-CRED",
            record_kind="identity_entry", recorded_name=f"Robert Chen {gen}",
            specialty="Neurology", practice_name="Evergreen Neurology",
            city="Seattle", state="WA", email=email, credential_reference=cred,
            record_date="2026-05-01", resolution_status="linked",
        )
        add_link(s1, did, "accepted", "generational_suffix", 0.92)
        add_link(s2, did, "accepted", "credential_match", 0.93)
        add_alias(did, f"Robert Chen {gen}", "preferred", "2026-04-01")
        add_event(
            doctor_id=did, event_type="record_entry", title="Identity entry linked",
            description=f"Robert Chen {gen} directory record", new_value=f"Robert Chen {gen}",
            document_date="2026-04-01", recorded_at="2026-04-01T12:00:00Z",
            review_status="accepted",
        )

    sr_chen_conflict = add_sr(
        source_record_id="SR-CHEN-CONFLICT", source_id="SRC-SPEAKER",
        record_kind="identity_entry", recorded_name="Robert Chen",
        specialty="Neurology", practice_name="Evergreen Neurology",
        city="Seattle", state="WA", credential_reference=None,
        record_date="2026-08-15", resolution_status="identifier_conflict",
    )
    add_link(sr_chen_conflict, None, "identifier_conflict", "jr_sr_hard_conflict", 0.55,
             review_id="REV-CHEN-CONFLICT")
    add_review(
        review_id="REV-CHEN-CONFLICT", doctor_id=jr_id, case_type="identifier_conflict",
        title="Jr/Sr identity conflict for Robert Chen",
        severity="critical", status="pending", source_record_id=sr_chen_conflict,
        candidate_doctor_id=sr_id, recommendation_id="REC-CHEN-CONFLICT",
        created_at="2026-08-16T10:00:00Z", updated_at="2026-08-16T10:00:00Z", version=1,
    )
    review_candidates.append({
        "review_id": "REV-CHEN-CONFLICT", "candidate_doctor_id": jr_id,
        "demo_score": "0.55", "evidence_summary": "Same city/specialty; missing generational suffix",
    })
    review_candidates.append({
        "review_id": "REV-CHEN-CONFLICT", "candidate_doctor_id": sr_id,
        "demo_score": "0.54", "evidence_summary": "Same city/specialty; missing generational suffix",
    })
    recommendations["REC-CHEN-CONFLICT"] = {
        "recommendation_id": "REC-CHEN-CONFLICT",
        "summary": "Hard conflict: Jr and Sr profiles share name stem without disambiguating credential on the new record.",
        "simulated_recommendation": "Leave unresolved; do not override hard identity conflict.",
        "demo_match_score": 0.55,
        "decision_method": "constraint_rule",
        "ambiguities": ["Missing Jr/Sr suffix on inbound record"],
        "constraints": ["Hard identity conflicts cannot be auto-linked or overridden via generic merge"],
        "evidence_refs": [],
        "side_by_side": [],
        "evidence_rows": [],
    }

    # ---------- Dual concurrent affiliations ----------
    dual_id = "HCP-000401"
    doctors.append({
        "doctor_id": dual_id, "preferred_name": "Elena Vargas", "given_name": "Elena",
        "family_name": "Vargas", "specialty": "Hematology",
        "primary_affiliation_id": "AFF-DUAL-1", "city": "Philadelphia", "state": "PA",
        "professional_email": "elena.vargas@example.com", "professional_phone": "+1-555-040-4001",
        "official_npi": None, "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-25T10:00:00Z", "version": 1,
    })
    affiliations.append({
        "affiliation_id": "AFF-DUAL-1", "doctor_id": dual_id,
        "organization_name": "Pioneer Hematology Clinic", "address_line": "12 Broad St",
        "city": "Philadelphia", "state": "PA", "relationship_status": "current",
        "is_primary": "true", "effective_from": "2017-04-01", "effective_to": None,
        "observed_at": "2026-08-01", "evidence_id": None,
    })
    affiliations.append({
        "affiliation_id": "AFF-DUAL-2", "doctor_id": dual_id,
        "organization_name": "University Teaching Hospital", "address_line": "900 Campus Blvd",
        "city": "Philadelphia", "state": "PA", "relationship_status": "current",
        "is_primary": "false", "effective_from": "2021-09-01", "effective_to": None,
        "observed_at": "2026-08-01", "evidence_id": None,
    })
    for i, org in enumerate(["Pioneer Hematology Clinic", "University Teaching Hospital"], start=1):
        s = add_sr(
            source_record_id=f"SR-DUAL-{i}", source_id="SRC-CRM" if i == 1 else "SRC-CRED",
            record_kind="identity_entry", recorded_name="Elena Vargas",
            specialty="Hematology", practice_name=org, city="Philadelphia", state="PA",
            email="elena.vargas@example.com", credential_reference="PA-DEMO-4401",
            record_date=f"2026-0{i+3}-01", resolution_status="linked",
        )
        add_link(s, dual_id, "accepted", "concurrent_affiliation", 0.9)
    add_alias(dual_id, "Elena Vargas", "preferred", "2026-04-01")
    add_event(
        doctor_id=dual_id, event_type="affiliation_observed",
        title="Concurrent affiliation observed",
        description="Second current affiliation at teaching hospital",
        new_value="University Teaching Hospital", document_date="2026-05-01",
        recorded_at="2026-05-01T12:00:00Z", effective_date="2021-09-01",
        review_status="accepted",
    )

    # ---------- Misspelled name + email corroboration ----------
    miss_id = "HCP-000501"
    doctors.append({
        "doctor_id": miss_id, "preferred_name": "Jonathan Brooks", "given_name": "Jonathan",
        "family_name": "Brooks", "specialty": "Rheumatology",
        "primary_affiliation_id": "AFF-MISS-1", "city": "Austin", "state": "TX",
        "professional_email": "jonathan.brooks@example.com", "professional_phone": "+1-555-050-5001",
        "official_npi": None, "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-18T10:00:00Z", "version": 1,
    })
    affiliations.append({
        "affiliation_id": "AFF-MISS-1", "doctor_id": miss_id,
        "organization_name": "Sunrise Rheumatology", "address_line": "44 Congress Ave",
        "city": "Austin", "state": "TX", "relationship_status": "current",
        "is_primary": "true", "effective_from": "2016-02-01", "effective_to": None,
        "observed_at": "2026-07-15", "evidence_id": None,
    })
    s_miss_good = add_sr(
        source_record_id="SR-MISS-GOOD", source_id="SRC-CRM", record_kind="identity_entry",
        recorded_name="Jonathan Brooks", specialty="Rheumatology",
        practice_name="Sunrise Rheumatology", city="Austin", state="TX",
        email="jonathan.brooks@example.com", credential_reference="TX-DEMO-5501",
        record_date="2026-03-01", resolution_status="linked",
    )
    s_miss_spell = add_sr(
        source_record_id="SR-MISS-SPELL", source_id="SRC-SPEAKER", record_kind="identity_entry",
        recorded_name="Jonathon Brooks", specialty="Rheumatology",
        practice_name="Sunrise Rheumatology", city="Austin", state="TX",
        email="jonathan.brooks@example.com", credential_reference="TX-DEMO-5501",
        record_date="2026-06-10", resolution_status="linked",
    )
    add_link(s_miss_good, miss_id, "accepted", "directory_match", 0.95)
    add_link(s_miss_spell, miss_id, "accepted", "email_corroborated_spelling_variant", 0.89)
    add_alias(miss_id, "Jonathan Brooks", "preferred", "2026-03-01")
    add_alias(miss_id, "Jonathon Brooks", "spelling_variant", "2026-06-10")
    add_event(
        doctor_id=miss_id, event_type="name_variation_observed",
        title="Name variation observed",
        description="Spelling Jonathon corroborated by matching professional email",
        previous_value="Jonathan Brooks", new_value="Jonathon Brooks",
        document_date="2026-06-10", recorded_at="2026-06-10T12:00:00Z",
        effective_date=None, review_status="accepted",
    )

    # ---------- Unknown effective date showcase ----------
    unk_eff_id = "HCP-000601"
    doctors.append({
        "doctor_id": unk_eff_id, "preferred_name": "Amelia Grant", "given_name": "Amelia",
        "family_name": "Grant", "specialty": "Pulmonology",
        "primary_affiliation_id": "AFF-UNK-1", "city": "Miami", "state": "FL",
        "professional_email": "amelia.grant@example.com", "professional_phone": "+1-555-060-6001",
        "official_npi": None, "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-12T10:00:00Z", "version": 1,
    })
    affiliations.append({
        "affiliation_id": "AFF-UNK-1", "doctor_id": unk_eff_id,
        "organization_name": "Coastal Pulmonary Group", "address_line": "7 Ocean Dr",
        "city": "Miami", "state": "FL", "relationship_status": "current",
        "is_primary": "true", "effective_from": None, "effective_to": None,
        "observed_at": "2026-07-22", "evidence_id": None,
    })
    s_unk1 = add_sr(
        source_record_id="SR-UNK-1", source_id="SRC-CRM", record_kind="identity_entry",
        recorded_name="Amelia Grant", specialty="Pulmonology",
        practice_name="Coastal Pulmonary Group", city="Miami", state="FL",
        email="amelia.grant@example.com", record_date="2026-07-22",
        resolution_status="linked",
    )
    s_unk2 = add_sr(
        source_record_id="SR-UNK-2", source_id="SRC-NOTES", record_kind="note_observation",
        recorded_name="Amelia Grant", specialty="Pulmonology",
        practice_name="Coastal Pulmonary Group", city="Miami", state="FL",
        record_date="2026-07-22", resolution_status="linked",
    )
    add_link(s_unk1, unk_eff_id, "accepted", "directory_match", 0.9)
    add_link(s_unk2, unk_eff_id, "accepted", "note_observation", 0.8)
    add_alias(unk_eff_id, "Amelia Grant", "preferred", "2026-07-22")
    add_event(
        doctor_id=unk_eff_id, event_type="affiliation_observed",
        title="Affiliation observed",
        description="Affiliation observed on document date; effective date unknown",
        new_value="Coastal Pulmonary Group", document_date="2026-07-22",
        recorded_at="2026-07-22T15:00:00Z", effective_date=None,
        review_status="accepted",
    )

    # ---------- Low-evidence candidate (leave unresolved) ----------
    low_id = "HCP-000701"
    doctors.append({
        "doctor_id": low_id, "preferred_name": "Marcus Hale", "given_name": "Marcus",
        "family_name": "Hale", "specialty": "Internal Medicine",
        "primary_affiliation_id": "AFF-LOW-1", "city": "Columbus", "state": "OH",
        "professional_email": "marcus.hale@example.com", "professional_phone": "+1-555-070-7001",
        "official_npi": None, "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-05T10:00:00Z", "version": 1,
    })
    affiliations.append({
        "affiliation_id": "AFF-LOW-1", "doctor_id": low_id,
        "organization_name": "Atlas Internal Medicine", "address_line": "300 High St",
        "city": "Columbus", "state": "OH", "relationship_status": "current",
        "is_primary": "true", "effective_from": "2014-08-01", "effective_to": None,
        "observed_at": "2026-06-01", "evidence_id": None,
    })
    s_low1 = add_sr(
        source_record_id="SR-LOW-1", source_id="SRC-CRM", record_kind="identity_entry",
        recorded_name="Marcus Hale", specialty="Internal Medicine",
        practice_name="Atlas Internal Medicine", city="Columbus", state="OH",
        email="marcus.hale@example.com", credential_reference="OH-DEMO-7701",
        record_date="2026-02-01", resolution_status="linked",
    )
    s_low2 = add_sr(
        source_record_id="SR-LOW-2", source_id="SRC-RX", record_kind="supporting_transaction",
        recorded_name="Marcus Hale", specialty="Internal Medicine",
        practice_name="Atlas Internal Medicine", city="Columbus", state="OH",
        record_date="2026-03-15", resolution_status="linked",
    )
    add_link(s_low1, low_id, "accepted", "directory_match", 0.91)
    add_link(s_low2, low_id, "accepted", "supporting_transaction", 0.7)
    add_alias(low_id, "Marcus Hale", "preferred", "2026-02-01")
    add_event(
        doctor_id=low_id, event_type="record_entry", title="Directory entry linked",
        new_value="Marcus Hale", document_date="2026-02-01",
        recorded_at="2026-02-01T12:00:00Z", review_status="accepted",
    )
    sr_low_cand = add_sr(
        source_record_id="SR-LOW-CAND", source_id="SRC-NOTES",
        record_kind="note_observation", recorded_name="M. Hale",
        specialty=None, practice_name=None, city="Columbus", state="OH",
        record_date="2026-08-01", resolution_status="review_required",
    )
    add_link(sr_low_cand, None, "review_required", "low_evidence_candidate", 0.48,
             review_id="REV-LOW-EVID")
    add_review(
        review_id="REV-LOW-EVID", doctor_id=low_id, case_type="possible_duplicate",
        title="Low-evidence candidate: M. Hale note",
        severity="low", status="pending", source_record_id=sr_low_cand,
        candidate_doctor_id=low_id, recommendation_id="REC-LOW-EVID",
        created_at="2026-08-02T09:00:00Z", updated_at="2026-08-02T09:00:00Z", version=1,
    )
    recommendations["REC-LOW-EVID"] = {
        "recommendation_id": "REC-LOW-EVID",
        "summary": "Abbreviation and city only; no email or credential.",
        "simulated_recommendation": "Leave unresolved until stronger corroboration is available.",
        "demo_match_score": 0.48,
        "decision_method": "steward_review",
        "ambiguities": ["Common surname abbreviation"],
        "constraints": [],
        "evidence_refs": [],
        "side_by_side": [],
        "evidence_rows": [],
    }

    # ---------- Linkable unassigned identity entry ----------
    linkable_target = "HCP-000801"
    doctors.append({
        "doctor_id": linkable_target, "preferred_name": "Diana Patel", "given_name": "Diana",
        "family_name": "Patel", "specialty": "Oncology",
        "primary_affiliation_id": "AFF-LINK-1", "city": "Newark", "state": "NJ",
        "professional_email": "diana.patel@example.com", "professional_phone": "+1-555-080-8001",
        "official_npi": None, "npi_status": "Not verified", "identity_status": "active",
        "updated_at": "2026-08-28T10:00:00Z", "version": 1,
    })
    affiliations.append({
        "affiliation_id": "AFF-LINK-1", "doctor_id": linkable_target,
        "organization_name": "Northside Oncology Group", "address_line": "18 Market St",
        "city": "Newark", "state": "NJ", "relationship_status": "current",
        "is_primary": "true", "effective_from": "2019-11-01", "effective_to": None,
        "observed_at": "2026-07-01", "evidence_id": None,
    })
    s_link1 = add_sr(
        source_record_id="SR-LINK-1", source_id="SRC-CRM", record_kind="identity_entry",
        recorded_name="Diana Patel", specialty="Oncology",
        practice_name="Northside Oncology Group", city="Newark", state="NJ",
        email="diana.patel@example.com", credential_reference="NJ-DEMO-8801",
        record_date="2026-04-01", resolution_status="linked",
    )
    s_link2 = add_sr(
        source_record_id="SR-LINK-2", source_id="SRC-PAY", record_kind="supporting_transaction",
        recorded_name="Diana Patel", specialty="Oncology",
        practice_name="Northside Oncology Group", city="Newark", state="NJ",
        email="diana.patel@example.com", credential_reference="NJ-DEMO-8801",
        record_date="2026-05-20", resolution_status="linked",
    )
    sr_unassigned = add_sr(
        source_record_id="SR-LINK-UNASSIGNED", source_id="SRC-SPEAKER",
        record_kind="identity_entry", recorded_name="Diana Patel", specialty="Oncology",
        practice_name="Northside Oncology Group", city="Newark", state="NJ",
        email="diana.patel@example.com", credential_reference="NJ-DEMO-8801",
        record_date="2026-09-01", resolution_status="review_required",
    )
    add_link(s_link1, linkable_target, "accepted", "directory_match", 0.94)
    add_link(s_link2, linkable_target, "accepted", "supporting_transaction", 0.86)
    add_link(sr_unassigned, None, "review_required", "eligible_unassigned_identity", 0.92,
             review_id="REV-LINK-UNASSIGNED")
    add_alias(linkable_target, "Diana Patel", "preferred", "2026-04-01")
    add_event(
        doctor_id=linkable_target, event_type="record_entry", title="Directory entry linked",
        new_value="Diana Patel", document_date="2026-04-01",
        recorded_at="2026-04-01T12:00:00Z", review_status="accepted",
    )
    add_review(
        review_id="REV-LINK-UNASSIGNED", doctor_id=linkable_target,
        case_type="possible_duplicate",
        title="Link eligible unassigned speaker registration to Diana Patel",
        severity="medium", status="pending", source_record_id=sr_unassigned,
        candidate_doctor_id=linkable_target, recommendation_id="REC-LINK-UNASSIGNED",
        created_at="2026-09-01T14:00:00Z", updated_at="2026-09-01T14:00:00Z", version=1,
    )
    recommendations["REC-LINK-UNASSIGNED"] = {
        "recommendation_id": "REC-LINK-UNASSIGNED",
        "summary": "Unassigned identity entry matches email and credential for Diana Patel.",
        "simulated_recommendation": "Link records to existing master HCP-000801.",
        "demo_match_score": 0.92,
        "decision_method": "steward_review",
        "ambiguities": [],
        "constraints": ["Link applies unassigned source record to existing master; no master-master merge"],
        "evidence_refs": [],
        "side_by_side": [],
        "evidence_rows": [],
    }

    # Extra showcase docs for remaining showcase identities (bring total docs >= 12)
    extra_docs = [
        ("DOC-005", "Priya Sharma Cardiology CRM Snapshot", "directory_extract", "SRC-CRM",
         "Priya Sharma — Metro Cardiology Associates", "IL-DEMO-1101"),
        ("DOC-006", "Priya Sharma Endocrinology Registration", "event_registration", "SRC-SPEAKER",
         "P. Sharma — Gulf Coast Endocrine Clinic", "TX-DEMO-2202"),
        ("DOC-007", "Robert Chen Jr Credential", "credential_update", "SRC-CRED",
         "Robert Chen Jr — WA-DEMO-JR01", "WA-DEMO-JR01"),
        ("DOC-008", "Robert Chen Sr Credential", "credential_update", "SRC-CRED",
         "Robert Chen Sr — WA-DEMO-SR01", "WA-DEMO-SR01"),
        ("DOC-009", "Elena Vargas Dual Affiliation Memo", "rep_note", "SRC-NOTES",
         "Elena Vargas maintains concurrent affiliations", "PA-DEMO-4401"),
        ("DOC-010", "Jonathan Brooks Speaker Badge", "event_registration", "SRC-SPEAKER",
         "Jonathon Brooks — jonathan.brooks@example.com", "TX-DEMO-5501"),
        ("DOC-011", "Amelia Grant Field Note", "rep_note", "SRC-NOTES",
         "Amelia Grant observed at Coastal Pulmonary Group", None),
        ("DOC-012", "Diana Patel Speaker Registration", "event_registration", "SRC-SPEAKER",
         "Diana Patel — NJ-DEMO-8801", "NJ-DEMO-8801"),
    ]
    for doc_id, title, dtype, src, quote, cred in extra_docs:
        pages = [{"page_number": 1, "label": "Page 1", "blocks": [
            block(1, 1, title.upper(), "heading"),
            block(1, 2, f"Synthetic document for demonstration ({doc_id})"),
            block(1, 3, quote),
            block(1, 4, f"Credential: {cred}" if cred else "Credential: Not recorded"),
        ]}]
        store_doc(make_doc(
            doc_id, title, dtype, src, "1", "2026-06-01", "2026-06-01T12:00:00Z",
            "Demo Generator", "Medical Affairs", pages,
        ))
        add_evidence(
            evidence_id=f"EVD-{doc_id}", source_record_id=None, document_id=doc_id,
            document_version="1", page_number=1, block_id="p1-b3", quoted_text=quote,
            source_field="recorded_name", source_snapshot="2026.09.01",
            citation_label=f"{doc_id} p.1",
        )

    # ---------- Bulk population to reach 120 doctors / 500+ source records ----------
    used_ids = {d["doctor_id"] for d in doctors}
    next_num = 1000
    while len(doctors) < 120:
        while doctor_id(next_num) in used_ids:
            next_num += 1
        did = doctor_id(next_num)
        used_ids.add(did)
        next_num += 1
        first = RNG.choice(FIRST)
        last = RNG.choice(LAST)
        specialty = RNG.choice(SPECIALTIES)
        state = RNG.choice(STATES)
        city = RNG.choice(CITIES[state])
        org = RNG.choice(ORGS)
        email = f"{first.lower()}.{last.lower()}{RNG.randint(1,99)}@example.com"
        phone = f"+1-555-{RNG.randint(100,999):03d}-{RNG.randint(1000,9999)}"
        cred = f"{state}-DEMO-{RNG.randint(1000,9999)}"
        aff_id = f"AFF-{did}"
        updated = datetime(2026, RNG.randint(1, 9), RNG.randint(1, 28), RNG.randint(8, 18), 0, 0)
        doctors.append({
            "doctor_id": did, "preferred_name": f"{first} {last}", "given_name": first,
            "family_name": last, "specialty": specialty, "primary_affiliation_id": aff_id,
            "city": city, "state": state, "professional_email": email,
            "professional_phone": phone, "official_npi": None, "npi_status": "Not verified",
            "identity_status": "active", "updated_at": iso_dt(updated), "version": 1,
        })
        affiliations.append({
            "affiliation_id": aff_id, "doctor_id": did, "organization_name": org,
            "address_line": f"{RNG.randint(10,900)} Demo Ave", "city": city, "state": state,
            "relationship_status": "current", "is_primary": "true",
            "effective_from": iso_date(date(2010 + RNG.randint(0, 10), RNG.randint(1, 12), 1)),
            "effective_to": None, "observed_at": iso_date(updated.date()), "evidence_id": None,
        })
        add_alias(did, f"{first} {last}", "preferred", iso_date(updated.date()))
        if RNG.random() < 0.25:
            add_alias(did, f"{first[0]}. {last}", "abbreviation", iso_date(updated.date()))
        if RNG.random() < 0.15:
            prev = f"{first} {RNG.choice(LAST)}"
            add_alias(did, prev, "previous_name", iso_date((updated - timedelta(days=400)).date()))

        n_records = RNG.randint(2, 5)
        for i in range(n_records):
            src = RNG.choice(sources)["source_id"]
            kind = "identity_entry"
            if src == "SRC-PAY" or src == "SRC-RX":
                kind = "supporting_transaction" if RNG.random() < 0.7 else "identity_entry"
            if src == "SRC-NOTES":
                kind = "note_observation"
            rec_date = updated - timedelta(days=RNG.randint(10, 900))
            recorded = f"{first} {last}" if RNG.random() > 0.15 else f"{first[0]}. {last}"
            srid = add_sr(
                source_id=src, record_kind=kind, recorded_name=recorded, specialty=specialty,
                practice_name=org, city=city, state=state,
                email=email if RNG.random() > 0.2 else None,
                phone=phone if RNG.random() > 0.4 else None,
                credential_reference=cred if RNG.random() > 0.3 else None,
                record_date=iso_date(rec_date.date()),
                submitted_at=iso_dt(rec_date),
                resolution_status="linked",
            )
            add_link(srid, did, "accepted", "bulk_seed_match", round(RNG.uniform(0.75, 0.98), 2))
            if i == 0:
                add_evidence(
                    source_record_id=srid, document_id=None, quoted_text=recorded,
                    source_field="recorded_name", source_snapshot="2026.09.01",
                    citation_label=f"CSV {srid}",
                )
        add_event(
            doctor_id=did, event_type="record_entry", title="Profile seeded",
            description="Golden profile created from demo seed",
            new_value=f"{first} {last}", document_date=iso_date(updated.date()),
            recorded_at=iso_dt(updated), review_status="accepted",
        )
        if RNG.random() < 0.35:
            add_event(
                doctor_id=did, event_type="affiliation_observed",
                title="Affiliation observed", new_value=org,
                document_date=iso_date((updated - timedelta(days=60)).date()),
                recorded_at=iso_dt(updated - timedelta(days=60)),
                effective_date=None if RNG.random() < 0.3 else iso_date(date(2018, 1, 1)),
                review_status="accepted",
            )

    # Additional unlinked / review / unresolved rows to enrich sources
    for i in range(40):
        src = RNG.choice(sources)["source_id"]
        status = RNG.choice(["unresolved", "review_required", "unresolved", "review_required"])
        name = f"{RNG.choice(FIRST)} {RNG.choice(LAST)}"
        srid = add_sr(
            source_id=src, record_kind="identity_entry", recorded_name=name,
            specialty=RNG.choice(SPECIALTIES), practice_name=RNG.choice(ORGS),
            city=RNG.choice(CITIES["NY"]), state="NY",
            record_date=iso_date(date(2026, RNG.randint(1, 9), RNG.randint(1, 28))),
            resolution_status=status,
        )
        add_link(srid, None, status, "bulk_unassigned", round(RNG.uniform(0.2, 0.6), 2))

    # Pad supporting transactions
    while len(source_records) < 500:
        d = RNG.choice(doctors)
        src = RNG.choice(["SRC-PAY", "SRC-RX"])
        srid = add_sr(
            source_id=src, record_kind="supporting_transaction",
            recorded_name=d["preferred_name"], specialty=d["specialty"],
            practice_name=next(
                (a["organization_name"] for a in affiliations if a["doctor_id"] == d["doctor_id"] and a["is_primary"] == "true"),
                "Unknown Practice",
            ),
            city=d["city"], state=d["state"],
            record_date=iso_date(date(2025, RNG.randint(1, 12), RNG.randint(1, 28))),
            resolution_status="linked",
        )
        add_link(srid, d["doctor_id"], "accepted", "supporting_transaction", 0.7)

    # Additional reviews to reach >= 30
    case_types = [
        "possible_duplicate", "same_name_ambiguity", "identifier_conflict",
        "name_update", "address_update", "affiliation_update",
    ]
    statuses = ["pending", "pending", "deferred", "completed", "pending"]
    while len(reviews) < 35:
        d = RNG.choice(doctors)
        ctype = RNG.choice(case_types)
        status = RNG.choice(statuses)
        created = datetime(2026, RNG.randint(5, 9), RNG.randint(1, 28), 10, 0, 0)
        rid = add_review(
            doctor_id=d["doctor_id"], case_type=ctype,
            title=f"{ctype.replace('_', ' ').title()} for {d['preferred_name']}",
            severity=RNG.choice(["low", "medium", "high"]),
            status=status,
            proposed_field="preferred_name" if ctype == "name_update" else (
                "address" if ctype == "address_update" else (
                    "primary_affiliation" if ctype == "affiliation_update" else None
                )
            ),
            proposed_value="Proposed value demo" if ctype.endswith("update") else None,
            recommendation_id=None,
            created_at=iso_dt(created), updated_at=iso_dt(created), version=1,
        )
        if status == "completed":
            add_audit(
                doctor_id=d["doctor_id"], review_id=rid, action="review_completed",
                summary=f"Seeded completed decision for {rid}",
                occurred_at=iso_dt(created + timedelta(days=1)), is_seeded=True,
            )
        elif status == "deferred":
            add_audit(
                doctor_id=d["doctor_id"], review_id=rid, action="review_deferred",
                summary=f"Seeded deferred case {rid}",
                occurred_at=iso_dt(created + timedelta(hours=5)), is_seeded=True,
            )

    # Name/address update pending examples for KPI "profiles with proposed changes"
    for d in doctors[10:18]:
        if any(r["doctor_id"] == d["doctor_id"] and r["case_type"] in ("name_update", "address_update", "affiliation_update") and r["status"] == "pending" for r in reviews):
            continue
        add_review(
            doctor_id=d["doctor_id"], case_type="name_update",
            title=f"Name update proposal for {d['preferred_name']}",
            severity="medium", status="pending", proposed_field="preferred_name",
            proposed_value=d["preferred_name"] + " MD",
            created_at="2026-09-01T12:00:00Z", updated_at="2026-09-01T12:00:00Z", version=1,
        )

    # Match explanations for showcase doctors
    for did in [sarah_id, priya_a, priya_b, jr_id, dual_id, miss_id, unk_eff_id, low_id, linkable_target]:
        if did not in recommendations:
            recommendations[did] = {
                "recommendation_id": f"REC-{did}",
                "doctor_id": did,
                "summary": f"Precomputed simulated match explanation for {did}.",
                "simulated_recommendation": "Maintain current linkage based on prepared demo evidence.",
                "demo_match_score": 0.9,
                "decision_method": "precomputed_demo",
                "review_status": "accepted",
                "ambiguities": [],
                "constraints": [],
                "side_by_side": [],
                "evidence_rows": [],
            }

    # Write CSVs
    write_csv_dicts(csv_dir / "sources.csv",
                    ["source_id", "source_name", "source_type", "description", "snapshot_version", "updated_at"],
                    sources)
    write_csv_dicts(csv_dir / "doctors.csv",
                    ["doctor_id", "preferred_name", "given_name", "family_name", "specialty",
                     "primary_affiliation_id", "city", "state", "professional_email",
                     "professional_phone", "official_npi", "npi_status", "identity_status",
                     "updated_at", "version"],
                    doctors)
    write_csv_dicts(csv_dir / "source_records.csv",
                    ["source_record_id", "source_id", "record_kind", "recorded_name", "specialty",
                     "practice_name", "address_line", "city", "state", "email", "phone",
                     "credential_reference", "document_id", "record_date", "submitted_at",
                     "submitted_by", "submitted_to", "resolution_status"],
                    source_records)
    write_csv_dicts(csv_dir / "source_links.csv",
                    ["link_id", "source_record_id", "doctor_id", "link_status", "decision_basis",
                     "demo_score", "review_id"],
                    source_links)
    write_csv_dicts(csv_dir / "aliases.csv",
                    ["alias_id", "doctor_id", "name", "alias_type", "observation_date", "evidence_id"],
                    aliases)
    write_csv_dicts(csv_dir / "affiliations.csv",
                    ["affiliation_id", "doctor_id", "organization_name", "address_line", "city",
                     "state", "relationship_status", "is_primary", "effective_from", "effective_to",
                     "observed_at", "evidence_id"],
                    affiliations)
    write_csv_dicts(csv_dir / "observations.csv",
                    ["observation_id", "doctor_id", "source_record_id", "field_name",
                     "observed_value", "effective_from", "effective_to", "recorded_at", "evidence_id"],
                    observations)
    write_csv_dicts(csv_dir / "field_provenance.csv",
                    ["provenance_id", "doctor_id", "field_name", "selected_value", "observation_id",
                     "selection_reason", "review_id", "version"],
                    field_provenance)
    write_csv_dicts(csv_dir / "events.csv",
                    ["event_id", "doctor_id", "event_type", "title", "description", "previous_value",
                     "new_value", "document_date", "submitted_at", "submitted_to", "effective_date",
                     "recorded_at", "review_status", "evidence_id"],
                    events)
    write_csv_dicts(csv_dir / "reviews.csv",
                    ["review_id", "doctor_id", "case_type", "title", "severity", "status",
                     "source_record_id", "candidate_doctor_id", "proposed_field", "proposed_value",
                     "recommendation_id", "created_at", "updated_at", "version"],
                    reviews)
    write_csv_dicts(csv_dir / "review_candidates.csv",
                    ["review_id", "candidate_doctor_id", "demo_score", "evidence_summary"],
                    review_candidates)
    write_csv_dicts(csv_dir / "evidence.csv",
                    ["evidence_id", "source_record_id", "document_id", "document_version",
                     "page_number", "block_id", "quoted_text", "source_field", "source_snapshot",
                     "citation_label"],
                    evidence)
    write_csv_dicts(csv_dir / "documents.csv",
                    ["document_id", "title", "document_type", "source_id", "version",
                     "document_date", "submitted_at", "submitted_by", "submitted_to", "content_file"],
                    documents_meta)
    write_csv_dicts(csv_dir / "audit_events.csv",
                    ["audit_id", "doctor_id", "review_id", "action", "actor_label", "summary",
                     "occurred_at", "is_seeded"],
                    audit_events)

    for did, content in documents_content.items():
        (docs_dir / f"{did}.json").write_text(json.dumps(content, indent=2), encoding="utf-8")

    (mock_dir / "recommendations.json").write_text(
        json.dumps(recommendations, indent=2), encoding="utf-8"
    )

    baseline = {
        "run_id": "DEMO-RUN-001",
        "mode": "simulation",
        "status": "completed",
        "current_step": "complete",
        "completed_steps": 7,
        "total_steps": 7,
        "progress_percent": 100,
        "message": "Seeded completed processing demo using prepared outcomes.",
        "started_at": "2026-09-10T08:00:00Z",
        "updated_at": "2026-09-10T08:05:00Z",
        "result_url": "/sources?tab=processing",
        "errors": [],
        "step_labels": [
            "Read source snapshots",
            "Standardize example records",
            "Load prepared candidate groups",
            "Show simulated evidence assessment",
            "Assemble prepared golden profiles",
            "Prepare review cases",
            "Complete",
        ],
        "result_counts": {
            "doctors": len(doctors),
            "source_records": len(source_records),
            "reviews": len(reviews),
            "linked_records": sum(1 for l in source_links if l["link_status"] == "accepted"),
        },
    }
    (mock_dir / "processing_baseline.json").write_text(
        json.dumps(baseline, indent=2), encoding="utf-8"
    )

    manifest = {
        "seed_version": "1.0.0",
        "demonstration_mode": True,
        "analysis_mode": "mock",
        "generated_at": "2026-09-12T12:00:00Z",
        "counts": {
            "doctors": len(doctors),
            "source_records": len(source_records),
            "reviews": len(reviews),
            "documents": len(documents_meta),
            "evidence": len(evidence),
            "events": len(events),
        },
        "date_range": {"start": "2024-02-12", "end": "2026-09-12"},
        "showcase_ids": {
            "sarah": "HCP-000123",
            "priya_a": priya_a,
            "priya_b": priya_b,
            "chen_jr": jr_id,
            "chen_sr": sr_id,
            "dual_affiliation": dual_id,
            "misspelling": miss_id,
            "unknown_effective": unk_eff_id,
            "low_evidence": low_id,
            "linkable": linkable_target,
            "sarah_affiliation_review": "REV-SARAH-AFF",
            "link_review": "REV-LINK-UNASSIGNED",
        },
    }
    (BACKEND_ROOT / "data" / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"Seeded {len(doctors)} doctors, {len(source_records)} source records, "
          f"{len(reviews)} reviews, {len(documents_meta)} documents.")


if __name__ == "__main__":
    main()
