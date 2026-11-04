from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KpiCard(BaseModel):
    key: str
    label: str
    value: int
    secondary_value: Optional[int] = None
    display: str
    tooltip: str
    href: str
    filters: Dict[str, Any] = Field(default_factory=dict)


class DashboardSummary(BaseModel):
    dataset_updated_at: Optional[str] = None
    last_simulated_run_at: Optional[str] = None
    snapshot_version: int
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    kpis: List[KpiCard]
    priority_reviews: List[Dict[str, Any]] = Field(default_factory=list)
    recent_changes: List[Dict[str, Any]] = Field(default_factory=list)
    source_coverage: List[Dict[str, Any]] = Field(default_factory=list)
    recent_decisions: List[Dict[str, Any]] = Field(default_factory=list)


class SourceBreakdownSegment(BaseModel):
    status: str
    count: int


class SourceBreakdownRow(BaseModel):
    source_id: str
    source_name: str
    segments: List[SourceBreakdownSegment]


class SourceBreakdownResponse(BaseModel):
    rows: List[SourceBreakdownRow]
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    text_summary: str


class QualitySummary(BaseModel):
    snapshot_version: int
    source_completeness: List[Dict[str, Any]] = Field(default_factory=list)
    missing_fields: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_records: int = 0
    conflicting_cases: int = 0
    pending_review_volume: int = 0
    inconsistent_evidence_refs: int = 0
    matching_accuracy_note: str = "Matching accuracy: Not evaluated in mock-data mode"
    drilldowns: Dict[str, Any] = Field(default_factory=dict)
