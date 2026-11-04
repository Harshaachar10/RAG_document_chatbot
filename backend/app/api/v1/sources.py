from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_source_service
from app.services.source_service import SourceService

router = APIRouter(tags=["sources"])


@router.get("/sources", operation_id="listSources")
def list_sources(service: SourceService = Depends(get_source_service)) -> Dict[str, Any]:
    return service.list_sources()


@router.get("/sources/{source_id}/records", operation_id="listSourceRecords")
def list_source_records(
    source_id: str,
    search: Optional[str] = None,
    status: Optional[str] = None,
    record_kind: Optional[str] = None,
    sort_by: str = "record_date",
    sort_direction: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    service: SourceService = Depends(get_source_service),
) -> Dict[str, Any]:
    return service.list_records(
        source_id,
        search=search,
        status=status,
        record_kind=record_kind,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.get("/source-records/{record_id}", operation_id="getSourceRecord")
def get_source_record(record_id: str, service: SourceService = Depends(get_source_service)) -> Dict[str, Any]:
    return service.get_record(record_id)
