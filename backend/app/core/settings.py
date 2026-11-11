from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Doctor Intelligence"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    data_mode: str = "identity"
    # Explicit provider. Azure is the only live provider used by this app.
    analysis_mode: str = "azure"
    # Heterogeneous historical CSVs (01_nppes_reference.csv … 08_*.csv) live here.
    csv_directory: str = "data"
    runtime_directory: str = "data/runtime"
    documents_directory: str = "data/documents"
    mock_directory: str = "data/mock"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = ""
    azure_openai_deployment: str = ""
    azure_openai_timeout_seconds: float = 45
    azure_openai_max_retries: int = 2
    azure_openai_max_concurrency: int = 2
    # Chat model deployment is AZURE_OPENAI_DEPLOYMENT.
    # Embedding model name and deployment use the names present in .env.
    embedding_model_name: str = ""
    embedding_deployment: str = ""
    ai_search_endpoint: str = ""
    ai_search_key: str = ""
    ai_search_index: str = "doctor-identity"
    embeddings_enabled: bool = True
    ai_search_enabled: bool = True
    match_max_rounds: int = 5
    supervised_model_enabled: bool = False
    ai_max_source_records: int = 8
    ai_max_evidence: int = 80
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )
    demo_run_step_delay_ms: int = 400
    # Upload & Match
    upload_directory: str = "data/uploads"
    upload_max_bytes: int = 20_000_000
    upload_retention_days: int = 90
    upload_allow_llm_images: bool = False
    upload_ocr_enabled: bool = True

    @property
    def upload_path(self) -> Path:
        return (BACKEND_ROOT / self.upload_directory).resolve()

    @property
    def backend_root(self) -> Path:
        return BACKEND_ROOT

    @property
    def csv_path(self) -> Path:
        return (BACKEND_ROOT / self.csv_directory).resolve()

    @property
    def runtime_path(self) -> Path:
        return (BACKEND_ROOT / self.runtime_directory).resolve()

    @property
    def documents_path(self) -> Path:
        return (BACKEND_ROOT / self.documents_directory).resolve()

    @property
    def mock_path(self) -> Path:
        return (BACKEND_ROOT / self.mock_directory).resolve()

    @property
    def manifest_path(self) -> Path:
        return (BACKEND_ROOT / "data" / "manifest.json").resolve()

    def missing_azure_settings(self) -> list[str]:
        missing: list[str] = []
        if not self.azure_openai_endpoint.strip():
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.azure_openai_api_key.strip():
            missing.append("AZURE_OPENAI_API_KEY")
        if not self.azure_openai_api_version.strip():
            missing.append("AZURE_OPENAI_API_VERSION")
        if not self.azure_openai_deployment.strip():
            missing.append("AZURE_OPENAI_DEPLOYMENT")
        return missing

    @property
    def ai_ready(self) -> bool:
        if self.analysis_mode == "mock":
            return True
        if self.analysis_mode == "azure":
            return not self.missing_azure_settings()
        return False


def _stripped_dotenv() -> dict[str, str]:
    """Read .env with stripped keys. Values are never logged."""
    path = BACKEND_ROOT / ".env"
    if not path.exists():
        return {}
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        found[key.strip()] = value.strip().strip('"').strip("'")
    return found


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    extra = _stripped_dotenv()
    mapping = {
        "embedding_model_name": "embedding_model_name",
        "EMBEDDING_MODEL_NAME": "embedding_model_name",
        "AZURE_OPENAI_EMBEDDING_MODEL": "embedding_model_name",
        "embedding_deployment": "embedding_deployment",
        "EMBEDDING_DEPLOYMENT": "embedding_deployment",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding_deployment",
        "ai_search_endpoint": "ai_search_endpoint",
        "AI_SEARCH_ENDPOINT": "ai_search_endpoint",
        "AZURE_SEARCH_ENDPOINT": "ai_search_endpoint",
        "ai_search_key": "ai_search_key",
        "AI_SEARCH_KEY": "ai_search_key",
        "AZURE_SEARCH_KEY": "ai_search_key",
        "ai_search_index": "ai_search_index",
        "AI_SEARCH_INDEX": "ai_search_index",
        "AZURE_SEARCH_INDEX": "ai_search_index",
    }
    updates: dict[str, str] = {}
    for source, dest in mapping.items():
        if extra.get(source) and not str(getattr(settings, dest) or "").strip():
            updates[dest] = extra[source]
    if updates:
        settings = settings.model_copy(update=updates)
    return settings
