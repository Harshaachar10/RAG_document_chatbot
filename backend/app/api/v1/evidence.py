from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.dependencies import get_evidence_service
from app.schemas.evidence import DocumentDetail, EvidenceDetail
from app.services.evidence_service import EvidenceService

router = APIRouter(tags=["evidence"])


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetail, operation_id="getEvidence")
def get_evidence(evidence_id: str, service: EvidenceService = Depends(get_evidence_service)) -> EvidenceDetail:
    return EvidenceDetail(**service.get_evidence(evidence_id))


@router.get("/documents/{document_id}", response_model=DocumentDetail, operation_id="getDocument")
def get_document(
    document_id: str,
    version: str | None = None,
    service: EvidenceService = Depends(get_evidence_service),
) -> DocumentDetail:
    return DocumentDetail(**service.get_document(document_id, version))


@router.get("/documents/{document_id}/download", operation_id="downloadDocument")
def download_document(document_id: str, service: EvidenceService = Depends(get_evidence_service)) -> Response:
    filename, content = service.document_text(document_id)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
