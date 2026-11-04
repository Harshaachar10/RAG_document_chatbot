from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SourceSummary(BaseModel):
    source_id: str
    source_name: str
    source_type: str
    description: Optional[str] = None
    snapshot_version: Optional[str] = None
    updated_at: Optional[str] = None
    row_count: int = 0
    linked_count: int = 0
    pending_count: int = 0
    unresolved_count: int = 0
    review_required_count: int = 0
    identifier_conflict_count: int = 0
    completeness: Optional[float] = None
    latest_data_date: Optional[str] = None
