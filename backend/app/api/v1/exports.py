from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import get_export_service
from app.services.export_service import ExportService

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{dataset}", operation_id="exportDataset")
def export_dataset(dataset: str, service: ExportService = Depends(get_export_service)) -> Response:
    filename, content = service.export(dataset)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
