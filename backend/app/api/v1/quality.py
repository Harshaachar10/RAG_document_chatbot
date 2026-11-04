from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_quality_service
from app.schemas.dashboard import QualitySummary
from app.services.quality_service import QualityService

router = APIRouter(tags=["quality"])


@router.get("/quality/summary", response_model=QualitySummary, operation_id="getQualitySummary")
def quality_summary(service: QualityService = Depends(get_quality_service)) -> QualitySummary:
    return QualitySummary(**service.summary())


@router.get("/activity", operation_id="listActivity")
def list_activity(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    service: QualityService = Depends(get_quality_service),
) -> Dict[str, Any]:
    return service.activity(search=search, page=page, page_size=page_size)
