from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    snapshot_version: int = 1


class HealthResponse(BaseModel):
    status: str
    version: str
    data_mode: str
    analysis_mode: str
    ready: bool
    snapshot_version: int
    dataset_updated_at: Optional[str] = None
    ai_ready: bool = False
    missing_ai_settings: List[str] = Field(default_factory=list)
    data_classification: str = "synthetic"
    search_mode: str = "local"
    chat_ready: bool = False
    embeddings_ready: bool = False
    search_ready: bool = False


class ReferenceDataResponse(BaseModel):
    specialties: List[str]
    states: List[str]
    sources: List[Dict[str, Any]]
    review_statuses: List[str]
    review_case_types: List[str]
    severities: List[str]
    resolution_statuses: List[str]
    record_kinds: List[str]
    defaults: Dict[str, Any] = Field(default_factory=dict)
