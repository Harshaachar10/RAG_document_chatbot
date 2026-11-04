from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DoctorListItem(BaseModel):
    doctor_id: str
    preferred_name: str
    specialty: Optional[str] = None
    primary_affiliation: Optional[str] = None
    affiliation_count: int = 0
    city: Optional[str] = None
    state: Optional[str] = None
    linked_record_count: int = 0
    pending_item_count: int = 0
    identity_status: Optional[str] = None
    updated_at: Optional[str] = None
    npi_status: str = "Not verified"


class DoctorSummary(BaseModel):
    doctor_id: str
    preferred_name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    specialty: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    professional_email: Optional[str] = None
    professional_phone: Optional[str] = None
    official_npi: Optional[str] = None
    npi_status: str = "Not verified"
    mock_npi_ref: Optional[str] = None
    data_classification: str = "synthetic"
    identity_status: Optional[str] = None
    identity_review_status: Optional[str] = None
    pending_field_changes: int = 0
    linked_record_count: int = 0
    source_count: int = 0
    aliases: List[Dict[str, Any]] = Field(default_factory=list)
    primary_affiliation: Optional[Dict[str, Any]] = None
    affiliations: List[Dict[str, Any]] = Field(default_factory=list)
    previous_names: List[str] = Field(default_factory=list)
    pending_updates: List[Dict[str, Any]] = Field(default_factory=list)
    source_coverage: List[Dict[str, Any]] = Field(default_factory=list)
    credential_details: Optional[str] = None
    updated_at: Optional[str] = None
    version: int = 1


class AliasItem(BaseModel):
    alias_id: str
    doctor_id: str
    name: str
    alias_type: str
    observation_date: Optional[str] = None
    evidence_id: Optional[str] = None


class AffiliationItem(BaseModel):
    affiliation_id: str
    doctor_id: str
    organization_name: str
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    relationship_status: str
    is_primary: bool = False
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    observed_at: Optional[str] = None
    evidence_id: Optional[str] = None


class SourceRecordItem(BaseModel):
    source_record_id: str
    source_id: str
    source_name: Optional[str] = None
    record_kind: str
    recorded_name: Optional[str] = None
    specialty: Optional[str] = None
    practice_name: Optional[str] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    credential_reference: Optional[str] = None
    document_id: Optional[str] = None
    record_date: Optional[str] = None
    submitted_at: Optional[str] = None
    submitted_by: Optional[str] = None
    submitted_to: Optional[str] = None
    resolution_status: Optional[str] = None
    link_status: Optional[str] = None
    doctor_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    normalized: Dict[str, Any] = Field(default_factory=dict)
    linkage_explanation: Optional[str] = None


class HistoryEvent(BaseModel):
    event_id: str
    doctor_id: str
    event_type: str
    title: str
    description: Optional[str] = None
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    document_date: Optional[str] = None
    submitted_at: Optional[str] = None
    submitted_to: Optional[str] = None
    effective_date: Optional[str] = None
    recorded_at: Optional[str] = None
    review_status: Optional[str] = None
    evidence_id: Optional[str] = None
    date_label: Optional[str] = None
    date_meaning: Optional[str] = None
    source_type: Optional[str] = None
    actor: Optional[str] = None
    reason: Optional[str] = None
    evidence_quotation: Optional[str] = None


class ProvenanceItem(BaseModel):
    provenance_id: str
    doctor_id: str
    field_name: str
    selected_value: Optional[str] = None
    observation_id: Optional[str] = None
    selection_reason: Optional[str] = None
    review_id: Optional[str] = None
    version: int = 1
    evidence_ids: List[str] = Field(default_factory=list)


class MatchExplanation(BaseModel):
    doctor_id: str
    label: str = "Prepared result"
    summary: str
    simulated_recommendation: str
    demo_match_score: Optional[float] = None
    decision_method: str
    review_status: Optional[str] = None
    ambiguities: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    side_by_side: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_rows: List[Dict[str, Any]] = Field(default_factory=list)


class AuditEventItem(BaseModel):
    audit_id: str
    doctor_id: Optional[str] = None
    review_id: Optional[str] = None
    action: str
    actor_label: str
    summary: str
    occurred_at: str
    is_seeded: bool = False
    changed_fields: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    before_after: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)
