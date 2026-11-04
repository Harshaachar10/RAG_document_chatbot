from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

from app.core.exceptions import NotFoundError, ValidationAppError
from app.repositories.csv_repository import CsvDemoRepository
from app.utils.csv_io import escape_csv_cell


ALLOWLIST = {"doctors", "source_records", "reviews", "doctor_history", "activity"}


class ExportService:
    def __init__(self, repo: CsvDemoRepository) -> None:
        self.repo = repo

    def export(self, dataset: str) -> tuple[str, str]:
        if dataset not in ALLOWLIST:
            raise ValidationAppError(
                f"Unsupported export dataset: {dataset}",
                details={"allowlist": sorted(ALLOWLIST)},
            )
        if dataset == "doctors":
            rows = self.repo.list_doctors()
            fields = [
                "doctor_id", "preferred_name", "specialty", "city", "state",
                "professional_email", "identity_status", "updated_at", "version",
            ]
        elif dataset == "source_records":
            rows = self.repo.list_source_records()
            fields = [
                "source_record_id", "source_id", "record_kind", "recorded_name",
                "practice_name", "city", "state", "record_date", "resolution_status",
            ]
        elif dataset == "reviews":
            rows = self.repo.list_reviews()
            fields = [
                "review_id", "doctor_id", "case_type", "title", "severity", "status",
                "proposed_field", "proposed_value", "created_at", "updated_at", "version",
            ]
        elif dataset == "doctor_history":
            rows = self.repo.list_events()
            fields = [
                "event_id", "doctor_id", "event_type", "title", "previous_value",
                "new_value", "document_date", "effective_date", "recorded_at", "review_status",
            ]
        else:
            rows = self.repo.list_audit()
            fields = [
                "audit_id", "doctor_id", "review_id", "action", "actor_label",
                "summary", "occurred_at", "is_seeded",
            ]

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: escape_csv_cell(row.get(f)) for f in fields})
        return f"{dataset}.csv", buffer.getvalue()
