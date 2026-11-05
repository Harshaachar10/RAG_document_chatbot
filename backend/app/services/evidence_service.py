from __future__ import annotations

from typing import Any, Dict, List

from app.core.exceptions import NotFoundError, ValidationAppError
from app.utils.csv_io import assert_safe_id


class EvidenceService:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def get_evidence(self, evidence_id: str) -> Dict[str, Any]:
        assert_safe_id(evidence_id, "evidence_id")
        evid = self.repo.get_evidence(evidence_id)
        if not evid:
            raise NotFoundError(f"Evidence {evidence_id} not found")
        preview_kind = "document" if evid.get("document_id") else "source_row"
        source_row = None
        if evid.get("source_record_id"):
            rec = self.repo.get_source_record(evid["source_record_id"])
            if rec:
                source_row = {
                    "source_record_id": rec["source_record_id"],
                    "source_id": rec.get("source_id"),
                    "snapshot_version": evid.get("source_snapshot"),
                    "fields": {
                        k: rec.get(k)
                        for k in (
                            "recorded_name", "specialty", "practice_name", "address_line",
                            "city", "state", "email", "phone", "credential_reference",
                            "record_date",
                        )
                    },
                }
        doc = self.repo.get_document(evid["document_id"]) if evid.get("document_id") else None
        associated = []
        if evid.get("source_field"):
            associated.append(evid["source_field"])
        return {
            **evid,
            "preview_kind": preview_kind,
            "source_row": source_row,
            "document_title": doc.get("title") if doc else None,
            "document_type": doc.get("document_type") if doc else None,
            "associated_fields": associated,
        }

    def get_document(self, document_id: str, version: str | None = None) -> Dict[str, Any]:
        assert_safe_id(document_id, "document_id")
        meta = self.repo.get_document(document_id)
        if not meta:
            raise NotFoundError(f"Document {document_id} not found")
        selected_version = str(version if version is not None else meta.get("version"))
        content = self.repo.get_document_content(document_id, selected_version)
        pages = (content or {}).get("pages") or []
        if not pages:
            raise NotFoundError(
                f"Document {document_id} version {selected_version} has no content rows in document_content.csv."
            )
        return {
            "document_id": document_id,
            "title": meta.get("title"),
            "document_type": meta.get("document_type"),
            "source_id": meta.get("source_id"),
            "version": selected_version,
            "document_date": meta.get("document_date"),
            "submitted_at": meta.get("submitted_at"),
            "submitted_by": meta.get("submitted_by") or "Not recorded",
            "submitted_to": meta.get("submitted_to") or "Not recorded",
            "pages": pages,
            "download_filename": f"{document_id}.txt",
        }

    def document_text(self, document_id: str) -> tuple[str, str]:
        detail = self.get_document(document_id)
        lines: List[str] = [
            detail["title"],
            f"Document ID: {document_id}",
            f"Type: {detail.get('document_type')}",
            f"Version: {detail.get('version')}",
            f"Date: {detail.get('document_date')}",
            "NOTE: Synthetic source text from document_content.csv. Not a scanned PDF.",
            "",
        ]
        for page in detail.get("pages") or []:
            label = page.get("label") or f"Page {page.get('page_number')}"
            lines.append(f"--- {label} ---")
            for block in page.get("blocks") or []:
                lines.append(block.get("text") or "")
            lines.append("")
        return detail["download_filename"], "\n".join(lines)
