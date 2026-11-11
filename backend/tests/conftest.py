from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _disable_live_models(monkeypatch):
    """Unit tests stay deterministic and never call Azure embeddings or AI Search."""
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    monkeypatch.setenv("AI_SEARCH_ENABLED", "false")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("RUNTIME_DIRECTORY", str(runtime_dir.relative_to(BACKEND_ROOT)) if False else str(runtime_dir))
    # Use absolute override via settings fields
    from app.core import settings as settings_mod
    from app.api import dependencies as deps

    settings_mod.get_settings.cache_clear()
    deps.get_runtime_store.cache_clear()
    deps.get_repository.cache_clear()
    deps.get_doctor_service.cache_clear()
    deps.get_review_service.cache_clear()
    deps.get_dashboard_service.cache_clear()
    deps.get_evidence_service.cache_clear()
    deps.get_source_service.cache_clear()
    deps.get_run_service.cache_clear()
    deps.get_quality_service.cache_clear()
    deps.get_export_service.cache_clear()
    deps.get_ai_service.cache_clear()
    if hasattr(deps, "get_payment_service"):
        deps.get_payment_service.cache_clear()
    if hasattr(deps, "get_notes_service"):
        deps.get_notes_service.cache_clear()
    if hasattr(deps, "get_upload_service"):
        deps.get_upload_service.cache_clear()
    if hasattr(deps, "get_ask_service"):
        deps.get_ask_service.cache_clear()

    monkeypatch.setenv("RUNTIME_DIRECTORY", str(runtime_dir))
    monkeypatch.setenv("ANALYSIS_MODE", "mock")
    # Patch Settings properties by setting env relative path that resolves under backend
    # Instead, monkeypatch RuntimeStore path after settings load:
    settings = settings_mod.Settings()
    object.__setattr__(settings, "runtime_directory", str(runtime_dir))

    # Rebuild settings singleton
    settings_mod.get_settings.cache_clear()

    class TestSettings(settings_mod.Settings):
        @property
        def runtime_path(self):  # type: ignore[override]
            return runtime_dir

    monkeypatch.setattr(settings_mod, "Settings", TestSettings)
    settings_mod.get_settings.cache_clear()
    deps.get_runtime_store.cache_clear()
    deps.get_repository.cache_clear()
    deps.get_doctor_service.cache_clear()
    deps.get_review_service.cache_clear()
    deps.get_dashboard_service.cache_clear()
    deps.get_evidence_service.cache_clear()
    deps.get_source_service.cache_clear()
    deps.get_run_service.cache_clear()
    deps.get_quality_service.cache_clear()
    deps.get_export_service.cache_clear()
    deps.get_ai_service.cache_clear()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    settings_mod.get_settings.cache_clear()
    deps.get_runtime_store.cache_clear()
    deps.get_repository.cache_clear()
