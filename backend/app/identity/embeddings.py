"""Azure OpenAI embeddings with hash cache, batching, and backoff.

Descriptions never include NPI, license numbers, phone, email, or patient data.
If the deployment is missing or the call fails, semantic search is skipped and
the rest of the pipeline still finishes.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.identity.descriptions import content_hash


def embeddings_requested() -> bool:
    flag = os.environ.get("EMBEDDINGS_ENABLED", "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    return True


def _settings():
    from app.core.settings import get_settings

    return get_settings()


def _cache_path() -> Path:
    settings = _settings()
    path = settings.runtime_path / "embedding_cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_cache() -> Dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {"items": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"items": {}}


def _save_cache(cache: Dict[str, Any]) -> None:
    path = _cache_path()
    path.write_text(json.dumps({"items": cache.get("items") or {}}), encoding="utf-8")


def embed_texts(texts: List[str]) -> Dict[str, Any]:
    """Return vectors aligned with texts. Cached by content hash. No secrets in the result."""
    if not embeddings_requested():
        return {"status": "skipped", "reason": "Embeddings are disabled.", "vectors": [None] * len(texts), "model": "", "deployment": "", "embedded": 0, "cached": 0}
    settings = _settings()
    deployment = (settings.embedding_deployment or "").strip()
    endpoint = (settings.azure_openai_endpoint or "").strip().rstrip("/")
    api_key = settings.azure_openai_api_key or ""
    api_version = (settings.azure_openai_api_version or "").strip()
    model_name = (settings.embedding_model_name or "").strip()
    if not deployment or not endpoint or not api_key or not api_version:
        return {
            "status": "skipped",
            "reason": "Embedding deployment is not configured.",
            "vectors": [None] * len(texts),
            "model": model_name,
            "deployment": deployment,
            "embedded": 0,
            "cached": 0,
        }

    cache = _load_cache()
    items: Dict[str, Any] = cache.setdefault("items", {})
    vectors: List[Optional[List[float]]] = [None] * len(texts)
    missing: List[tuple[int, str, str]] = []
    cached = 0
    for index, text in enumerate(texts):
        digest = content_hash(text)
        hit = items.get(digest)
        if hit and hit.get("deployment") == deployment and isinstance(hit.get("vector"), list):
            vectors[index] = hit["vector"]
            cached += 1
        else:
            missing.append((index, digest, text))

    embedded = 0
    error = ""
    batch_size = 16
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        payload = {"input": [text for _, _, text in batch]}
        if model_name:
            payload["model"] = model_name
        url = f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
        response = None
        for attempt in range(max(1, int(settings.azure_openai_max_retries) + 1)):
            try:
                response = httpx.post(
                    url,
                    headers={"api-key": api_key, "Content-Type": "application/json"},
                    json=payload,
                    timeout=float(settings.azure_openai_timeout_seconds),
                )
            except httpx.HTTPError:
                response = None
            if response is not None and response.status_code == 200:
                break
            if response is not None and response.status_code not in {408, 429, 500, 502, 503, 504}:
                break
            time.sleep(min(8.0, 0.5 * (2**attempt)))
        if response is None or response.status_code != 200:
            # Do not include response body; it can echo the key.
            code = response.status_code if response is not None else 0
            error = f"Embedding request failed ({code})."
            break
        body = response.json()
        data = body.get("data") or []
        for slot, row in enumerate(data):
            index, digest, _text = batch[slot]
            vector = row.get("embedding")
            if not isinstance(vector, list):
                continue
            vectors[index] = vector
            items[digest] = {
                "vector": vector,
                "deployment": deployment,
                "model": model_name,
                "hash": digest,
            }
            embedded += 1
        _save_cache(cache)

    status = "ready" if not error else ("partial" if embedded or cached else "skipped")
    return {
        "status": status if not error or cached or embedded else "skipped",
        "reason": error,
        "vectors": vectors,
        "model": model_name,
        "deployment": deployment,
        "embedded": embedded,
        "cached": cached,
        "dimension": next((len(v) for v in vectors if v), 0),
    }


def vector_key(kind: str, identifier: str) -> str:
    return hashlib.sha1(f"{kind}|{identifier}".encode("utf-8")).hexdigest()[:16]
