from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import get_upload_service
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("", operation_id="listUploadBatches")
def list_batches(service: UploadService = Depends(get_upload_service)) -> Dict[str, Any]:
    return service.list_batches()


@router.get("/{batch_id}", operation_id="getUploadBatch")
def get_batch(batch_id: str, service: UploadService = Depends(get_upload_service)) -> Dict[str, Any]:
    return service.get_batch(batch_id)


@router.post("", operation_id="createUploadBatch")
async def create_batch(
    mode: str = Form(...),
    file: UploadFile = File(...),
    uploaded_by: str = Form("Steward"),
    service: UploadService = Depends(get_upload_service),
) -> Dict[str, Any]:
    content = await file.read()
    return service.upload_file(
        filename=file.filename or "upload.bin",
        content=content,
        mode=mode,
        uploaded_by=uploaded_by,
    )


@router.post("/{batch_id}/mapping", operation_id="confirmUploadMapping")
def confirm_mapping(
    batch_id: str,
    payload: Dict[str, Any],
    service: UploadService = Depends(get_upload_service),
) -> Dict[str, Any]:
    return service.confirm_mapping(batch_id, payload.get("mapping") or payload)


@router.post("/{batch_id}/extract", operation_id="confirmUploadExtract")
def confirm_extract(
    batch_id: str,
    payload: Dict[str, Any],
    service: UploadService = Depends(get_upload_service),
) -> Dict[str, Any]:
    return service.confirm_document_extract(batch_id, payload.get("extracted") or payload)


@router.post("/{batch_id}/commit", operation_id="commitUploadBatch")
def commit_batch(batch_id: str, service: UploadService = Depends(get_upload_service)) -> Dict[str, Any]:
    return service.commit(batch_id)


@router.post("/{batch_id}/rollback", operation_id="rollbackUploadBatch")
def rollback_batch(batch_id: str, service: UploadService = Depends(get_upload_service)) -> Dict[str, Any]:
    return service.rollback(batch_id)
