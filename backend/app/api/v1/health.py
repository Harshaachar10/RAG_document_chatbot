from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_repository
from app.core.settings import Settings, get_settings
from app.repositories.csv_repository import CsvDemoRepository
from app.schemas.common import HealthResponse, ReferenceDataResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health(
    settings: Settings = Depends(get_settings),
    repo: CsvDemoRepository = Depends(get_repository),
) -> HealthResponse:
    manifest = repo.manifest()
    sources = repo.list_sources()
    dataset_updated_at = manifest.get("generated_at")
    if not dataset_updated_at and sources:
        dataset_updated_at = max((s.get("updated_at") or "" for s in sources), default=None)
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        data_mode=settings.data_mode,
        analysis_mode=settings.analysis_mode,
        ready=True,
        snapshot_version=repo.snapshot_version(),
        dataset_updated_at=dataset_updated_at,
        ai_ready=settings.ai_ready,
        missing_ai_settings=settings.missing_azure_settings() if settings.analysis_mode == "azure" else [],
        data_classification="synthetic",
    )


@router.get("/reference-data", response_model=ReferenceDataResponse, operation_id="getReferenceData")
def get_reference_data(repo: CsvDemoRepository = Depends(get_repository)) -> ReferenceDataResponse:
    doctors = repo.list_doctors()
    specialties = sorted({d.get("specialty") for d in doctors if d.get("specialty")})
    states = sorted({d.get("state") for d in doctors if d.get("state")})
    sources = [
        {"source_id": s["source_id"], "source_name": s["source_name"], "source_type": s["source_type"]}
        for s in repo.list_sources()
    ]
    return ReferenceDataResponse(
        specialties=specialties,
        states=states,
        sources=sources,
        review_statuses=["pending", "deferred", "completed"],
        review_case_types=[
            "possible_duplicate",
            "same_name_ambiguity",
            "identifier_conflict",
            "name_update",
            "address_update",
            "affiliation_update",
            "contact_update",
            "duplicate_ingestion",
            "link_correction",
        ],
        severities=["low", "medium", "high", "critical"],
        resolution_statuses=[
            "linked", "review_required", "unresolved", "identifier_conflict", "duplicate_ingestion",
        ],
        record_kinds=["identity_entry", "supporting_transaction", "note_observation"],
        defaults={"page_size": 25, "sort_by": "preferred_name", "sort_direction": "asc"},
    )
