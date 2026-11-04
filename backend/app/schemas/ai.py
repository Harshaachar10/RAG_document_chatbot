from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IdentityAnalysisRequest(BaseModel):
    source_record_ids: List[str] = Field(min_length=2)
    force_refresh: bool = False


class ChangeExtractionRequest(BaseModel):
    source_record_ids: List[str] = Field(min_length=1)
    force_refresh: bool = False


class RefreshRequest(BaseModel):
    force_refresh: bool = False
