"""Read-only Ask assistant and a non-committing record preview."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_ask_service
from app.services.ask_service import AskService

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str
    doctor_id: Optional[str] = None


class PreviewRequest(BaseModel):
    text: str


@router.post("/ask", operation_id="askAssistant")
def ask(body: AskRequest, service: AskService = Depends(get_ask_service)) -> Dict[str, Any]:
    return service.ask(body.question, doctor_id=body.doctor_id)


@router.post("/match/preview", operation_id="previewMatch")
def preview(body: PreviewRequest, service: AskService = Depends(get_ask_service)) -> Dict[str, Any]:
    return service.preview(body.text)
