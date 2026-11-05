from __future__ import annotations

from functools import lru_cache

from app.core.settings import Settings, get_settings
from app.providers.mock_recommendations import MockRecommendationProvider
from app.providers.mock_resolution import MockResolutionProvider
from app.repositories.identity_repository import IdentityRepository
from app.repositories.runtime_store import RuntimeStore
from app.services.dashboard_service import DashboardService
from app.services.doctor_service import DoctorService
from app.services.evidence_service import EvidenceService
from app.services.export_service import ExportService
from app.services.quality_service import QualityService
from app.services.review_service import ReviewService
from app.services.run_service import RunService
from app.ai.provider import build_llm_client
from app.ai.service import AiService
from app.services.source_service import SourceService


@lru_cache
def get_runtime_store() -> RuntimeStore:
    settings = get_settings()
    return RuntimeStore(settings.runtime_path)


@lru_cache
def get_repository() -> IdentityRepository:
    return IdentityRepository(get_settings(), get_runtime_store())


@lru_cache
def get_doctor_service() -> DoctorService:
    repo = get_repository()
    return DoctorService(repo, MockResolutionProvider(repo))


@lru_cache
def get_review_service() -> ReviewService:
    repo = get_repository()
    return ReviewService(repo, MockRecommendationProvider(repo))


@lru_cache
def get_dashboard_service() -> DashboardService:
    return DashboardService(get_repository())


@lru_cache
def get_evidence_service() -> EvidenceService:
    return EvidenceService(get_repository())


@lru_cache
def get_source_service() -> SourceService:
    return SourceService(get_repository())


@lru_cache
def get_run_service() -> RunService:
    return RunService(get_repository(), get_settings())


@lru_cache
def get_quality_service() -> QualityService:
    return QualityService(get_repository())


@lru_cache
def get_export_service() -> ExportService:
    return ExportService(get_repository())


@lru_cache
def get_ai_service() -> AiService:
    settings = get_settings()
    return AiService(get_repository(), settings, build_llm_client(settings))


@lru_cache
def get_payment_service():
    from app.services.payment_service import PaymentService

    return PaymentService(get_repository())


@lru_cache
def get_notes_service():
    from app.services.notes_service import NotesService

    return NotesService(get_repository())


@lru_cache
def get_upload_service():
    from app.services.upload_service import UploadService

    return UploadService(get_repository(), get_settings())
