from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(extra="allow")

    dataset_updated_at: Optional[str] = None
    last_simulated_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    view: Optional[str] = None
    snapshot_version: int
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    kpis: List[KpiCard]
    npi_issue_buckets: Dict[str, int] = Field(default_factory=dict)
    action_counts: Dict[str, Any] = Field(default_factory=dict)
    scorecard_available: bool = False
    priority_reviews: List[Dict[str, Any]] = Field(default_factory=list)
    recent_changes: List[Dict[str, Any]] = Field(default_factory=list)
    source_coverage: List[Dict[str, Any]] = Field(default_factory=list)
    recent_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    upload_batch_count: int = 0


class SourceBreakdownSegment(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    count: int
    label: Optional[str] = None


class SourceBreakdownRow(BaseModel):
    source_id: str
    source_name: str
    segments: List[SourceBreakdownSegment]


class SourceBreakdownResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: List[SourceBreakdownRow]
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    text_summary: str
    legend: List[Dict[str, str]] = Field(default_factory=list)


class QualitySummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    snapshot_version: int
    source_completeness: List[Dict[str, Any]] = Field(default_factory=list)
    missing_fields: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_records: int = 0
    conflicting_cases: int = 0
    pending_review_volume: int = 0
    inconsistent_evidence_refs: int = 0
    matching_accuracy_note: str = "Matching accuracy is not scored unless an answer-key scorecard is available."
    drilldowns: Dict[str, Any] = Field(default_factory=dict)
    audit_events: List[Dict[str, Any]] = Field(default_factory=list)
    pipeline_runs: List[Dict[str, Any]] = Field(default_factory=list)
