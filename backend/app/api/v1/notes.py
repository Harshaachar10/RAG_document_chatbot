from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_notes_service
from app.services.notes_service import NotesService

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/insights", operation_id="listNotesInsights")
def list_notes_insights(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    service: NotesService = Depends(get_notes_service),
) -> Dict[str, Any]:
    return service.list_insights(search=search, page=page, page_size=page_size)
