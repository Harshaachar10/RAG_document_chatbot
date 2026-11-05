from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from fastapi import BackgroundTasks

from app.api.dependencies import get_ai_service, get_review_service
from app.ai.service import AiService
from app.schemas.ai import RefreshRequest
from app.schemas.review import (
    AssignmentRequest,
    AssignmentResponse,
    DecisionRequest,
    DecisionResponse,
    ReviewDetail,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/reviewers", operation_id="listReviewers")
def list_reviewers(service: ReviewService = Depends(get_review_service)) -> Dict[str, Any]:
    return service.list_reviewers()


@router.get("", operation_id="listReviews")
def list_reviews(
    search: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    severity: Optional[str] = None,
    source_id: Optional[str] = None,
    sort_by: str = "risk",
    sort_direction: str = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    service: ReviewService = Depends(get_review_service),
) -> Dict[str, Any]:
    return service.list_reviews(
        search=search,
        status=status,
        case_type=case_type,
        severity=severity,
        source_id=source_id,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.get("/{review_id}", response_model=ReviewDetail, operation_id="getReview")
def get_review(review_id: str, service: ReviewService = Depends(get_review_service)) -> ReviewDetail:
    return ReviewDetail(**service.get_review(review_id))


@router.post("/{review_id}/ai-explanation", status_code=202, operation_id="createReviewAiExplanation")
async def create_review_explanation(
    review_id: str,
    background: BackgroundTasks,
    body: RefreshRequest | None = None,
    service: AiService = Depends(get_ai_service),
) -> Dict[str, Any]:
    force = bool(body.force_refresh) if body else False
    job = service.submit_explanation(review_id, force_refresh=force)
    if job.pop("should_run", False):
        background.add_task(service.execute, job["job_id"])
    return job


@router.post("/{review_id}/decisions", response_model=DecisionResponse, operation_id="createReviewDecision")
def create_decision(
    review_id: str,
    body: DecisionRequest,
    service: ReviewService = Depends(get_review_service),
) -> DecisionResponse:
    result = service.decide(review_id, body.model_dump())
    return DecisionResponse(**result)


@router.post("/{review_id}/assignment", response_model=AssignmentResponse, operation_id="assignReviewForHumanEvaluation")
def assign_review(
    review_id: str,
    body: AssignmentRequest,
    service: ReviewService = Depends(get_review_service),
) -> AssignmentResponse:
    result = service.assign_for_human_review(review_id, body.model_dump())
    return AssignmentResponse(**result)
