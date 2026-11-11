from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_repository
from app.core.settings import Settings, get_settings
from app.schemas.common import HealthResponse, ReferenceDataResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health(
    settings: Settings = Depends(get_settings),
    repo: Any = Depends(get_repository),
) -> HealthResponse:
    manifest = repo.manifest()
    sources = repo.list_sources()
    dataset_updated_at = manifest.get("generated_at")
    if not dataset_updated_at and sources:
        dataset_updated_at = max((s.get("updated_at") or "" for s in sources), default=None)
    run = (repo.state().get("pipeline_run") or {})
    dataset_updated_at = dataset_updated_at or run.get("finished_at")
    search_configured = bool((settings.ai_search_endpoint or "").strip() and (settings.ai_search_key or "").strip() and settings.ai_search_enabled)
    embeddings_ready = bool(
        settings.embeddings_enabled
        and (settings.embedding_deployment or settings.embedding_model_name)
        and settings.azure_openai_endpoint.strip()
        and settings.azure_openai_api_key.strip()
    )
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
        search_mode="azure" if search_configured else "local",
        chat_ready=settings.ai_ready,
        embeddings_ready=embeddings_ready,
        search_ready=search_configured,
    )


@router.get("/reference-data", response_model=ReferenceDataResponse, operation_id="getReferenceData")
def get_reference_data(repo: Any = Depends(get_repository)) -> ReferenceDataResponse:
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
        review_statuses=["pending", "deferred", "completed", "resolved"],
        review_case_types=[
            "probable_match",
            "compliance_review",
            "possible_duplicate",
            "same_name_ambiguity",
            "identifier_conflict",
            "npi_assignment",
            "unmatched",
            "not_a_person",
        ],
        severities=["low", "medium", "high", "critical"],
        resolution_statuses=[
            "linked",
            "pending_review",
            "unresolved",
            "rejected",
            "informational",
        ],
        record_kinds=[
            "legacy_master",
            "crm",
            "claims",
            "events",
            "payments",
            "hub",
            "notes",
        ],
        defaults={"page_size": 25, "sort_by": "preferred_name", "sort_direction": "asc"},
    )
