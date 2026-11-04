from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

import httpx

from app.core.exceptions import AppError
from app.core.settings import Settings


TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
AUTH_STATUS = {401, 403}


@dataclass
class LlmCompletion:
    content: str
    request_id: str
    usage: Optional[Dict[str, int]]
    provider: str
    deployment: str


class LlmClient(Protocol):
    async def complete_json(self, *, system: str, user: str, request_id: str) -> LlmCompletion:
        ...


def sanitize_error(message: str, secret: str = "") -> str:
    text = message or "The model request failed."
    if secret:
        text = text.replace(secret, "[redacted]")
    lowered = text.lower()
    if "api-key" in lowered or "api_key" in lowered:
        return "The model request failed. Credential material was removed from this error."
    return text[:500]


class MockLlmClient:
    """Deterministic stand-in for tests. It never reads evaluation answer keys."""

    provider = "mock"
    deployment = "mock"

    def __init__(self, scripted: Optional[Dict[str, Any]] = None) -> None:
        self.scripted = scripted or {}
        self.calls = 0
        self.last_user = ""

    async def complete_json(self, *, system: str, user: str, request_id: str) -> LlmCompletion:
        del system
        self.calls += 1
        self.last_user = user
        if "scripted_json" in self.scripted:
            payload = self.scripted["scripted_json"]
        elif "cannot_link" in user and "identity" in user.lower() or (
            "cannot_link" in user and "Compare these source records" in user
        ):
            payload = {
                "recommendation": "different_doctors",
                "summary": "A verified cannot-link constraint applies to these records.",
                "supporting_evidence_ids": [],
                "conflicting_evidence_ids": [],
                "missing_information": [],
                "proposed_changes": [],
                "requires_human_review": True,
            }
        elif "Summarize this accepted doctor profile" in user:
            payload = _summary_from_user(user)
        elif "Explain why this review case" in user:
            payload = {
                "summary": "The supplied source evidence does not settle the case by itself.",
                "why_review": "A person needs to compare the cited source values.",
                "support_for_candidates": [],
                "contradictions": [],
                "missing_information": ["Corroborating professional identifier"],
                "supporting_evidence_ids": [],
                "conflicting_evidence_ids": [],
                "requires_human_review": True,
            }
        elif "Extract proposed changes" in user:
            payload = {
                "summary": "No change was copied because the mock provider does not invent values.",
                "proposed_changes": [],
                "conflicting_observations": [],
                "requires_human_review": True,
            }
        else:
            payload = {
                "recommendation": "insufficient_evidence",
                "summary": "The shared attributes in the supplied evidence do not establish one doctor.",
                "supporting_evidence_ids": [],
                "conflicting_evidence_ids": [],
                "missing_information": ["Corroborating professional identifier"],
                "proposed_changes": [],
                "requires_human_review": True,
            }
        return LlmCompletion(
            content=json.dumps(payload),
            request_id=request_id,
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            provider=self.provider,
            deployment=self.deployment,
        )


def _summary_from_user(user: str) -> Dict[str, Any]:
    return {
        "summary": "Accepted profile summary from the supplied history. Pending items are not treated as fact.",
        "current_profile": "See the accepted profile fields in the input.",
        "previous_names": [],
        "affiliation_summary": "Affiliations are listed in the accepted profile section.",
        "supporting_evidence_ids": [],
        "outstanding_proposals": [],
        "conflicts": [],
    }


class AzureOpenAIClient:
    """Azure OpenAI Chat Completions client.

    The configured deployment name is sent as the model, matching the
    Azure OpenAI Python SDK (AsyncAzureOpenAI.chat.completions.create).
    Requests go only to the configured Azure endpoint.
    """

    provider = "azure"

    def __init__(self, settings: Settings) -> None:
        missing = settings.missing_azure_settings()
        if missing:
            raise AppError(
                "AI_NOT_CONFIGURED",
                "Azure OpenAI settings are missing.",
                status_code=503,
                details={"missing": missing},
            )
        self._settings = settings
        self._secret = settings.azure_openai_api_key
        self.deployment = settings.azure_openai_deployment.strip()
        self._endpoint = settings.azure_openai_endpoint.strip().rstrip("/")
        self._api_version = settings.azure_openai_api_version.strip()
        self._timeout = settings.azure_openai_timeout_seconds
        self._max_retries = max(0, settings.azure_openai_max_retries)
        self._semaphore = asyncio.Semaphore(max(1, settings.azure_openai_max_concurrency))
        self._client: Optional[httpx.AsyncClient] = None

    async def complete_json(self, *, system: str, user: str, request_id: str) -> LlmCompletion:
        body = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        async with self._semaphore:
            return await self._send(body, request_id, allow_format_fallback=True)

    async def _send(self, body: Dict[str, Any], request_id: str, *, allow_format_fallback: bool) -> LlmCompletion:
        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._post(body, request_id)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._backoff(attempt))
                continue
            except httpx.TransportError as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._backoff(attempt))
                continue
            status = response.status_code
            if status in AUTH_STATUS or status in {400, 404, 422}:
                if status == 400 and allow_format_fallback and "response_format" in response.text:
                    reduced = dict(body)
                    reduced.pop("response_format", None)
                    return await self._send(reduced, request_id, allow_format_fallback=False)
                raise AppError(
                    "AI_REQUEST_FAILED",
                    sanitize_error(_azure_message(response), self._secret),
                    status_code=503 if status != 400 else 502,
                    details={"status_code": status, "request_id": request_id},
                )
            if status in TRANSIENT_STATUS:
                last_error = AppError(
                    "AI_TRANSIENT",
                    sanitize_error(_azure_message(response), self._secret),
                    status_code=503,
                    details={"status_code": status, "request_id": request_id},
                )
                if attempt >= self._max_retries:
                    raise last_error
                await asyncio.sleep(self._backoff(attempt))
                continue
            if status >= 400:
                raise AppError(
                    "AI_REQUEST_FAILED",
                    sanitize_error(_azure_message(response), self._secret),
                    status_code=502,
                    details={"status_code": status, "request_id": request_id},
                )
            payload = response.json()
            try:
                content = payload["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise AppError(
                    "AI_RESPONSE_INVALID",
                    "The model response did not include message content.",
                    status_code=502,
                    details={"request_id": request_id},
                ) from exc
            usage = payload.get("usage") or None
            if isinstance(usage, dict):
                usage = {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            provider_request = response.headers.get("x-request-id") or response.headers.get("apim-request-id")
            return LlmCompletion(
                content=content or "",
                request_id=provider_request or request_id,
                usage=usage,
                provider=self.provider,
                deployment=self.deployment,
            )
        raise AppError(
            "AI_TIMEOUT",
            sanitize_error(str(last_error or "The model request timed out."), self._secret),
            status_code=504,
            details={"request_id": request_id},
        )

    async def _post(self, body: Dict[str, Any], request_id: str) -> httpx.Response:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout))
        url = (
            f"{self._endpoint}/openai/deployments/{self.deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )
        return await self._client.post(
            url,
            headers={
                "api-key": self._secret,
                "Content-Type": "application/json",
                "x-ms-client-request-id": request_id,
            },
            json=body,
        )

    def _backoff(self, attempt: int) -> float:
        return min(8.0, (0.4 * (2 ** attempt)) + random.random() * 0.2)


def _azure_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return f"Azure OpenAI returned HTTP {response.status_code}."
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = error.get("message") or error.get("code") or "request failed"
        return f"Azure OpenAI returned HTTP {response.status_code}: {message}"
    return f"Azure OpenAI returned HTTP {response.status_code}."


def build_llm_client(settings: Settings) -> LlmClient:
    if settings.analysis_mode == "mock":
        return MockLlmClient()
    if settings.analysis_mode != "azure":
        raise AppError(
            "AI_PROVIDER_UNSUPPORTED",
            "This application sends live analysis only to the configured Azure OpenAI deployment.",
            status_code=503,
            details={"analysis_mode": settings.analysis_mode},
        )
    return AzureOpenAIClient(settings)
