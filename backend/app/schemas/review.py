from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReviewListItem(BaseModel):
    review_id: str
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    case_type: str
    title: str
    severity: str
    status: str
    source_record_id: Optional[str] = None
    candidate_doctor_id: Optional[str] = None
    proposed_field: Optional[str] = None
    proposed_value: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    age_days: Optional[int] = None
    candidates_summary: Optional[str] = None
    assigned_reviewer: Optional[str] = None
    assignment_status: Optional[str] = None
    assignment_comment: Optional[str] = None
    assigned_at: Optional[str] = None


class ReviewCandidate(BaseModel):
    candidate_doctor_id: str
    doctor_name: Optional[str] = None
    demo_score: Optional[float] = None
    evidence_summary: Optional[str] = None


class ReviewDetail(BaseModel):
    review_id: str
    doctor_id: Optional[str] = None
    case_type: str
    title: str
    severity: str
    status: str
    source_record_id: Optional[str] = None
    candidate_doctor_id: Optional[str] = None
    proposed_field: Optional[str] = None
    proposed_value: Optional[str] = None
    recommendation_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: int = 1
    valid_actions: List[str] = Field(default_factory=list)
    comparison: Dict[str, Any] = Field(default_factory=dict)
    recommendation: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    impact: Dict[str, Any] = Field(default_factory=dict)
    candidates: List[ReviewCandidate] = Field(default_factory=list)
    current_state: Dict[str, Any] = Field(default_factory=dict)
    assigned_reviewer: Optional[str] = None
    assignment_status: Optional[str] = None
    assignment_comment: Optional[str] = None
    assigned_at: Optional[str] = None
    available_reviewers: List[str] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    decision: str
    action: str
    selected_doctor_id: Optional[str] = None
    comment: str
    expected_version: int
    idempotency_key: str


class DecisionResponse(BaseModel):
    review: ReviewDetail
    changed_doctor_ids: List[str] = Field(default_factory=list)
    snapshot_version: int
    audit_id: str


class AssignmentRequest(BaseModel):
    assign: bool = True
    assigned_reviewer: Optional[str] = None
    assignment_comment: Optional[str] = None
    expected_version: int


class AssignmentResponse(BaseModel):
    review: ReviewDetail
    changed_doctor_ids: List[str] = Field(default_factory=list)
    snapshot_version: int
    audit_id: str
