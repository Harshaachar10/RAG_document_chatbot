from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from fastapi import BackgroundTasks

from app.api.dependencies import get_ai_service, get_doctor_service
from app.ai.service import AiService
from app.schemas.ai import RefreshRequest
from app.schemas.common import PaginatedResponse
from app.schemas.doctor import (
    AffiliationItem,
    AliasItem,
    DoctorListItem,
    DoctorSummary,
    HistoryEvent,
    MatchExplanation,
    ProvenanceItem,
    SourceRecordItem,
    AuditEventItem,
)
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", operation_id="listDoctors")
def list_doctors(
    search: Optional[str] = None,
    specialty: Optional[str] = None,
    state: Optional[str] = None,
    affiliation: Optional[str] = None,
    source_id: Optional[str] = None,
    pending_review: Optional[bool] = None,
    missing_core: Optional[bool] = None,
    sort_by: str = Query("preferred_name"),
    sort_direction: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    service: DoctorService = Depends(get_doctor_service),
) -> Dict[str, Any]:
    result = service.list_doctors(
        search=search,
        specialty=specialty,
        state=state,
        affiliation=affiliation,
        source_id=source_id,
        pending_review=pending_review,
        missing_core=missing_core,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )
    result["items"] = [DoctorListItem(**i).model_dump() for i in result["items"]]
    return result


@router.get("/{doctor_id}", response_model=DoctorSummary, operation_id="getDoctor")
def get_doctor(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> DoctorSummary:
    return DoctorSummary(**service.get_doctor(doctor_id))


@router.get("/{doctor_id}/source-records", operation_id="getDoctorSourceRecords")
def doctor_source_records(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> Dict[str, Any]:
    result = service.list_source_records(doctor_id)
    result["items"] = [SourceRecordItem(**i).model_dump() for i in result["items"]]
    return result


@router.get("/{doctor_id}/aliases", response_model=List[AliasItem], operation_id="getDoctorAliases")
def doctor_aliases(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> List[AliasItem]:
    return [AliasItem(**a) for a in service.list_aliases(doctor_id)]


@router.get("/{doctor_id}/affiliations", response_model=List[AffiliationItem], operation_id="getDoctorAffiliations")
def doctor_affiliations(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> List[AffiliationItem]:
    return [AffiliationItem(**a) for a in service.list_affiliations(doctor_id)]


@router.get("/{doctor_id}/history", operation_id="getDoctorHistory")
def doctor_history(
    doctor_id: str,
    event_type: Optional[str] = None,
    field: Optional[str] = None,
    sort_direction: str = "desc",
    service: DoctorService = Depends(get_doctor_service),
) -> Dict[str, Any]:
    result = service.history(doctor_id, event_type=event_type, field=field, sort_direction=sort_direction)
    result["items"] = [HistoryEvent(**i).model_dump() for i in result["items"]]
    return result


@router.get("/{doctor_id}/provenance", operation_id="getDoctorProvenance")
def doctor_provenance(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> Dict[str, Any]:
    result = service.provenance(doctor_id)
    result["items"] = [ProvenanceItem(**i).model_dump() for i in result["items"]]
    return result


@router.get("/{doctor_id}/match-explanation", response_model=MatchExplanation, operation_id="getMatchExplanation")
def match_explanation(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> MatchExplanation:
    return MatchExplanation(**service.match_explanation(doctor_id))


@router.get("/{doctor_id}/ai-summary", operation_id="getDoctorAiSummary")
def get_doctor_ai_summary(doctor_id: str, service: AiService = Depends(get_ai_service)) -> Dict[str, Any]:
    return service.latest_summary(doctor_id)


@router.post("/{doctor_id}/ai-summary", status_code=202, operation_id="createDoctorAiSummary")
async def create_doctor_ai_summary(
    doctor_id: str,
    background: BackgroundTasks,
    body: RefreshRequest | None = None,
    service: AiService = Depends(get_ai_service),
) -> Dict[str, Any]:
    force = bool(body.force_refresh) if body else False
    job = service.submit_summary(doctor_id, force_refresh=force)
    if job.pop("should_run", False):
        background.add_task(service.execute, job["job_id"])
    return job


@router.get("/{doctor_id}/known-values", operation_id="getDoctorKnownValues")
def doctor_known_values(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> Dict[str, Any]:
    doctor = service.get_doctor(doctor_id)
    return {"doctor_id": doctor_id, "items": doctor.get("known_values") or []}


@router.get("/{doctor_id}/lineage", operation_id="getDoctorLineage")
def doctor_lineage(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> Dict[str, Any]:
    return service.lineage_graph(doctor_id)


@router.get("/{doctor_id}/similar", operation_id="getDoctorSimilar")
def doctor_similar(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> Dict[str, Any]:
    return service.similar_records(doctor_id)


@router.get("/{doctor_id}/review-history", operation_id="getDoctorReviewHistory")
def doctor_review_history(doctor_id: str, service: DoctorService = Depends(get_doctor_service)) -> Dict[str, Any]:
    result = service.review_history(doctor_id)
    result["items"] = [AuditEventItem(**i).model_dump() for i in result["items"]]
    return result
