from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ProposedChange(BaseModel):
    field: str
    proposed_value: str
    change_type: str
    effective_date: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)


class IdentityAnalysisResult(BaseModel):
    recommendation: Literal[
        "same_doctor",
        "different_doctors",
        "insufficient_evidence",
        "conflicting_identifier",
    ]
    summary: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    conflicting_evidence_ids: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    proposed_changes: List[ProposedChange] = Field(default_factory=list)
    requires_human_review: bool = True


class ChangeExtractionResult(BaseModel):
    summary: str
    proposed_changes: List[ProposedChange] = Field(default_factory=list)
    conflicting_observations: List[str] = Field(default_factory=list)
    requires_human_review: bool = True


class ProfileSummaryResult(BaseModel):
    summary: str
    current_profile: str
    previous_names: List[str] = Field(default_factory=list)
    affiliation_summary: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    outstanding_proposals: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)


class ReviewExplanationResult(BaseModel):
    summary: str
    why_review: str
    support_for_candidates: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    conflicting_evidence_ids: List[str] = Field(default_factory=list)
    requires_human_review: bool = True


RESULT_MODELS = {
    "identity_analysis": IdentityAnalysisResult,
    "change_extraction": ChangeExtractionResult,
    "profile_summary": ProfileSummaryResult,
    "review_explanation": ReviewExplanationResult,
}
