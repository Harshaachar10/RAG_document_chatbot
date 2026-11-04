from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.dependencies import get_ai_service
from app.ai.service import AiService
from app.schemas.ai import ChangeExtractionRequest, IdentityAnalysisRequest

router = APIRouter(prefix="/ai", tags=["ai"])


def _queue(job: Dict[str, Any], background: BackgroundTasks, service: AiService) -> Dict[str, Any]:
    if job.pop("should_run", False):
        background.add_task(service.execute, job["job_id"])
    return job


@router.post("/identity-analyses", status_code=202, operation_id="createIdentityAnalysis")
async def create_identity_analysis(
    body: IdentityAnalysisRequest,
    background: BackgroundTasks,
    service: AiService = Depends(get_ai_service),
) -> Dict[str, Any]:
    job = service.submit_identity(body.source_record_ids, force_refresh=body.force_refresh)
    return _queue(job, background, service)


@router.post("/change-extractions", status_code=202, operation_id="createChangeExtraction")
async def create_change_extraction(
    body: ChangeExtractionRequest,
    background: BackgroundTasks,
    service: AiService = Depends(get_ai_service),
) -> Dict[str, Any]:
    job = service.submit_changes(body.source_record_ids, force_refresh=body.force_refresh)
    return _queue(job, background, service)


@router.get("/jobs", operation_id="listAiJobs")
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    service: AiService = Depends(get_ai_service),
) -> Dict[str, Any]:
    return service.list_jobs(limit)


@router.get("/jobs/{job_id}", operation_id="getAiJob")
def get_job(job_id: str, service: AiService = Depends(get_ai_service)) -> Dict[str, Any]:
    return service.get_job(job_id)


@router.get("/analyses", operation_id="listAiAnalyses")
def list_analyses(
    operation: Optional[str] = None,
    doctor_id: Optional[str] = None,
    service: AiService = Depends(get_ai_service),
) -> Dict[str, Any]:
    return service.list_analyses(operation=operation, doctor_id=doctor_id)


@router.get("/analyses/{analysis_id}", operation_id="getAiAnalysis")
def get_analysis(analysis_id: str, service: AiService = Depends(get_ai_service)) -> Dict[str, Any]:
    return service.get_analysis(analysis_id)
