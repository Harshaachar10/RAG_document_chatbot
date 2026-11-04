from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceDetail(BaseModel):
    evidence_id: str
    source_record_id: Optional[str] = None
    document_id: Optional[str] = None
    document_version: Optional[str] = None
    page_number: Optional[int] = None
    block_id: Optional[str] = None
    quoted_text: Optional[str] = None
    source_field: Optional[str] = None
    source_snapshot: Optional[str] = None
    citation_label: Optional[str] = None
    preview_kind: str = "document"
    source_row: Optional[Dict[str, Any]] = None
    document_title: Optional[str] = None
    document_type: Optional[str] = None
    associated_fields: List[str] = Field(default_factory=list)


class DocumentBlock(BaseModel):
    block_id: str
    kind: str = "paragraph"
    text: str
    highlightable: bool = True


class DocumentPage(BaseModel):
    page_number: int
    label: Optional[str] = None
    blocks: List[DocumentBlock] = Field(default_factory=list)


class DocumentDetail(BaseModel):
    document_id: str
    title: str
    document_type: str
    source_id: Optional[str] = None
    version: str
    document_date: Optional[str] = None
    submitted_at: Optional[str] = None
    submitted_by: Optional[str] = None
    submitted_to: Optional[str] = None
    pages: List[DocumentPage] = Field(default_factory=list)
    download_filename: str
