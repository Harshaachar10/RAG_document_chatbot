"""Vector search. Local cosine index by default. Azure AI Search when configured.

pgvector is used only when DATABASE_URL points at PostgreSQL and the driver imports.
Semantic search is never required for the pipeline to finish.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Optional, Protocol


def safe_key(value: str) -> str:
    """Azure AI Search keys allow letters, digits, underscore, dash, and equal sign."""
    return re.sub(r"[^A-Za-z0-9_\-=]", "_", value or "")[:128] or "row"


class VectorStore(Protocol):
    def upsert(self, rows: List[Dict[str, Any]]) -> None: ...

    def search(
        self,
        vector: List[float],
        *,
        k: int = 20,
        state: str = "",
        specialty: str = "",
        kind: str = "",
    ) -> List[Dict[str, Any]]: ...


def _cosine(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for a, b in zip(left, right):
        dot += a * b
        na += a * a
        nb += b * b
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / math.sqrt(na * nb)


class LocalVectorIndex:
    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def upsert(self, rows: List[Dict[str, Any]]) -> None:
        by_id = {row["id"]: row for row in self.rows}
        for row in rows:
            if row.get("vector"):
                by_id[row["id"]] = row
        self.rows = list(by_id.values())

    def search(
        self,
        vector: List[float],
        *,
        k: int = 20,
        state: str = "",
        specialty: str = "",
        kind: str = "",
    ) -> List[Dict[str, Any]]:
        scored = []
        state_norm = (state or "").upper()
        specialty_norm = (specialty or "").lower()
        for row in self.rows:
            if kind and row.get("kind") != kind:
                continue
            if state_norm and row.get("state") and row.get("state").upper() != state_norm:
                continue
            if specialty_norm and row.get("specialty") and specialty_norm not in str(row.get("specialty")).lower():
                continue
            score = _cosine(vector, row.get("vector") or [])
            scored.append({**{key: value for key, value in row.items() if key != "vector"}, "similarity": round(score, 4)})
        scored.sort(key=lambda item: item["similarity"], reverse=True)
        return scored[:k]


class AzureSearchIndex:
    """Configurable. A failure leaves the local index in place."""

    def __init__(self, endpoint: str, key: str, index_name: str, dimension: int) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.key = key
        self.index_name = index_name
        self.dimension = dimension

    def _headers(self) -> Dict[str, str]:
        return {"api-key": self.key, "Content-Type": "application/json"}

    def ensure(self) -> None:
        import httpx

        url = f"{self.endpoint}/indexes/{self.index_name}?api-version=2024-07-01"
        body = {
            "name": self.index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
                {"name": "ref", "type": "Edm.String", "filterable": True},
                {"name": "kind", "type": "Edm.String", "filterable": True},
                {"name": "label", "type": "Edm.String"},
                {"name": "text", "type": "Edm.String"},
                {"name": "state", "type": "Edm.String", "filterable": True},
                {"name": "specialty", "type": "Edm.String", "filterable": True},
                {
                    "name": "embedding",
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "dimensions": self.dimension,
                    "vectorSearchProfile": "doctor-profile",
                },
            ],
            "vectorSearch": {
                "algorithms": [{"name": "doctor-hnsw", "kind": "hnsw", "hnswParameters": {"metric": "cosine"}}],
                "profiles": [{"name": "doctor-profile", "algorithm": "doctor-hnsw"}],
            },
        }
        response = httpx.put(url, headers=self._headers(), json=body, timeout=60)
        if response.status_code not in {200, 201, 204}:
            raise RuntimeError(f"Azure AI Search index was not created ({response.status_code}).")

    def upsert(self, rows: List[Dict[str, Any]]) -> None:
        import httpx

        url = f"{self.endpoint}/indexes/{self.index_name}/docs/index?api-version=2024-07-01"
        documents = []
        for row in rows:
            vector = row.get("vector")
            if not vector:
                continue
            documents.append(
                {
                    "@search.action": "mergeOrUpload",
                    "id": safe_key(str(row["id"])),
                    "ref": str(row["id"]),
                    "kind": row.get("kind") or "",
                    "label": row.get("label") or "",
                    "text": (row.get("text") or "")[:4000],
                    "state": row.get("state") or "",
                    "specialty": row.get("specialty") or "",
                    "embedding": vector,
                }
            )
        for start in range(0, len(documents), 100):
            batch = documents[start : start + 100]
            response = httpx.post(url, headers=self._headers(), json={"value": batch}, timeout=120)
            if response.status_code not in {200, 201}:
                raise RuntimeError(f"Azure AI Search upload failed ({response.status_code}).")

    def search(
        self,
        vector: List[float],
        *,
        k: int = 20,
        state: str = "",
        specialty: str = "",
        kind: str = "",
    ) -> List[Dict[str, Any]]:
        import httpx

        filters = []
        if kind:
            filters.append(f"kind eq '{kind}'")
        if state:
            filters.append(f"state eq '{state}'")
        url = f"{self.endpoint}/indexes/{self.index_name}/docs/search?api-version=2024-07-01"
        body: Dict[str, Any] = {
            "vectorQueries": [
                {"kind": "vector", "vector": vector, "fields": "embedding", "k": k},
            ],
            "select": "id,ref,kind,label,state,specialty",
            "top": k,
        }
        if filters:
            body["filter"] = " and ".join(filters)
        response = httpx.post(url, headers=self._headers(), json=body, timeout=60)
        if response.status_code != 200:
            return []
        hits = []
        for row in (response.json().get("value") or []):
            hits.append(
                {
                    "id": row.get("ref") or row.get("id"),
                    "kind": row.get("kind"),
                    "label": row.get("label"),
                    "state": row.get("state"),
                    "specialty": row.get("specialty"),
                    "similarity": round(float(row.get("@search.score") or 0), 4),
                }
            )
        return hits


def search_enabled() -> bool:
    flag = os.environ.get("AI_SEARCH_ENABLED", "").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def build_azure_store(dimension: int) -> Optional[AzureSearchIndex]:
    stores = build_azure_stores(dimension)
    return stores[0] if stores else None


def build_azure_stores(dimension: int) -> List[AzureSearchIndex]:
    """Two indexes: source-records and golden-doctors. Empty when search is not configured."""
    if not search_enabled() or dimension <= 0:
        return []
    from app.core.settings import get_settings

    settings = get_settings()
    endpoint = (settings.ai_search_endpoint or "").strip()
    key = (settings.ai_search_key or "").strip()
    if not endpoint or not key:
        return []
    return [
        AzureSearchIndex(endpoint, key, "source-records", dimension),
        AzureSearchIndex(endpoint, key, "golden-doctors", dimension),
    ]
