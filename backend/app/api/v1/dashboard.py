from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_dashboard_service
from app.schemas.dashboard import DashboardSummary, SourceBreakdownResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary, operation_id="getDashboardSummary")
def dashboard_summary(
    source_id: Optional[str] = None,
    specialty: Optional[str] = None,
    state: Optional[str] = None,
    review_state: Optional[str] = None,
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSummary:
    return DashboardSummary(**service.summary(
        source_id=source_id,
        specialty=specialty,
        state=state,
        review_state=review_state,
    ))


@router.get("/source-breakdown", response_model=SourceBreakdownResponse, operation_id="getSourceBreakdown")
def source_breakdown(
    source_id: Optional[str] = None,
    specialty: Optional[str] = None,
    state: Optional[str] = None,
    service: DashboardService = Depends(get_dashboard_service),
) -> SourceBreakdownResponse:
    return SourceBreakdownResponse(**service.source_breakdown(
        source_id=source_id, specialty=specialty, state=state,
    ))
