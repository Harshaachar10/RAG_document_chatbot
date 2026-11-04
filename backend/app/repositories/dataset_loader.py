"""Load and validate the supplied doctor CSV dataset.

Source files are read once and never rewritten. evaluation_only/ is not an input.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.exceptions import DatasetValidationError
from app.utils.csv_io import parse_bool, read_csv_rows

# Files that are original evidence or prepared presentation outputs.
# evaluation_only answer keys are intentionally absent.
EXPECTED_FILES = (
    "sources.csv",
    "doctors.csv",
    "source_records.csv",
    "source_links.csv",
    "aliases.csv",
    "affiliations.csv",
    "observations.csv",
    "field_provenance.csv",
    "events.csv",
    "reviews.csv",
    "review_candidates.csv",
    "evidence.csv",
    "documents.csv",
    "document_content.csv",
    "audit_events.csv",
    "link_history.csv",
    "identity_constraints.csv",
)

TABLE_COLUMNS: Dict[str, Sequence[str]] = {
    "sources": (
        "source_id", "source_name", "source_type", "description", "snapshot_version", "updated_at",
    ),
    "doctors": (
        "doctor_id", "preferred_name", "given_name", "family_name", "specialty",
        "primary_affiliation_id", "city", "state", "professional_email", "professional_phone",
        "official_npi", "npi_status", "mock_npi_ref", "identity_status", "updated_at", "version",
    ),
    "source_records": (
        "source_record_id", "source_id", "record_kind", "recorded_name", "specialty", "practice_name",
        "address_line", "city", "state", "postal_code", "email", "phone", "credential_reference",
        "provider_identifier", "identifier_kind", "document_id", "record_date", "submitted_at",
        "submitted_by", "submitted_to", "ingested_at", "resolution_status", "amount_cents",
        "currency", "prescription_count", "original_transaction_id", "note_text", "duplicate_of_record_id",
    ),
    "source_links": (
        "link_id", "source_record_id", "doctor_id", "link_status", "decision_basis", "demo_score", "review_id",
    ),
    "aliases": ("alias_id", "doctor_id", "name", "alias_type", "observation_date", "evidence_id"),
    "affiliations": (
        "affiliation_id", "doctor_id", "organization_name", "address_line", "city", "state",
        "relationship_status", "is_primary", "effective_from", "effective_to", "observed_at", "evidence_id",
    ),
    "observations": (
        "observation_id", "doctor_id", "source_record_id", "field_name", "observed_value",
        "effective_from", "effective_to", "recorded_at", "evidence_id",
    ),
    "field_provenance": (
        "provenance_id", "doctor_id", "field_name", "selected_value", "observation_id",
        "selection_reason", "review_id", "version",
    ),
    "events": (
        "event_id", "doctor_id", "event_type", "title", "description", "previous_value", "new_value",
        "document_date", "submitted_at", "submitted_to", "effective_date", "recorded_at",
        "review_status", "evidence_id",
    ),
    "reviews": (
        "review_id", "doctor_id", "case_type", "title", "severity", "status", "source_record_id",
        "candidate_doctor_id", "proposed_field", "proposed_value", "recommendation_id",
        "created_at", "updated_at", "version",
    ),
    "review_candidates": ("review_id", "candidate_doctor_id", "demo_score", "evidence_summary"),
    "evidence": (
        "evidence_id", "source_record_id", "document_id", "document_version", "page_number",
        "block_id", "quoted_text", "source_field", "source_snapshot", "citation_label",
    ),
    "documents": (
        "document_id", "title", "document_type", "source_id", "version", "document_date",
        "submitted_at", "submitted_by", "submitted_to", "content_table",
    ),
    "document_content": (
        "document_id", "document_version", "page_number", "block_order", "block_id",
        "block_type", "text", "is_synthetic",
    ),
    "audit_events": (
        "audit_id", "doctor_id", "review_id", "action", "actor_label", "summary", "occurred_at", "is_seeded",
    ),
    "link_history": (
        "change_id", "source_record_id", "doctor_id", "state", "valid_from", "valid_to", "reason",
    ),
    "identity_constraints": (
        "constraint_id", "left_doctor_id", "right_doctor_id", "constraint_type", "basis",
        "left_record_id", "right_record_id",
    ),
}

PRIMARY_KEYS: Dict[str, Sequence[str]] = {
    "sources": ("source_id",),
    "doctors": ("doctor_id",),
    "source_records": ("source_record_id",),
    "source_links": ("link_id",),
    "aliases": ("alias_id",),
    "affiliations": ("affiliation_id",),
    "observations": ("observation_id",),
    "field_provenance": ("provenance_id",),
    "events": ("event_id",),
    "reviews": ("review_id",),
    "review_candidates": ("review_id", "candidate_doctor_id"),
    "evidence": ("evidence_id",),
    "documents": ("document_id",),
    "document_content": ("document_id", "document_version", "page_number", "block_order"),
    "audit_events": ("audit_id",),
    "link_history": ("change_id",),
    "identity_constraints": ("constraint_id",),
}

INT_COLUMNS = {
    "doctors": {"version"},
    "source_records": {"amount_cents", "prescription_count"},
    "affiliations": set(),
    "field_provenance": {"version"},
    "reviews": {"version"},
    "evidence": {"page_number"},
    "documents": {"version"},
    "document_content": {"page_number", "block_order"},
}

BOOL_COLUMNS = {
    "affiliations": {"is_primary"},
    "audit_events": {"is_seeded"},
    "document_content": {"is_synthetic"},
}

DATE_COLUMNS = {
    "aliases": {"observation_date"},
    "affiliations": {"effective_from", "effective_to"},
    "observations": {"effective_from", "effective_to"},
    "events": {"document_date", "effective_date"},
    "documents": {"document_date"},
    "source_records": {"record_date"},
}

TIMESTAMP_COLUMNS = {
    "sources": {"updated_at"},
    "doctors": {"updated_at"},
    "source_records": {"submitted_at", "ingested_at"},
    "affiliations": {"observed_at"},
    "observations": {"recorded_at"},
    "events": {"submitted_at", "recorded_at"},
    "reviews": {"created_at", "updated_at"},
    "documents": {"submitted_at"},
    "audit_events": {"occurred_at"},
    "link_history": {"valid_from", "valid_to"},
}

# Observed categorical values. Unknown values are kept and reported, not dropped.
KNOWN_ENUMS = {
    ("aliases", "alias_type"): {"previous_name", "abbreviation", "spelling_variant", "nickname", "format_variant"},
    ("events", "event_type"): {
        "record_entry", "name_update", "possible_duplicate", "identifier_conflict",
        "same_name_ambiguity", "affiliation_update", "contact_update", "duplicate_ingestion",
        "link_correction", "review_decision",
    },
    ("reviews", "case_type"): {
        "name_update", "possible_duplicate", "identifier_conflict", "same_name_ambiguity",
        "affiliation_update", "contact_update", "duplicate_ingestion", "link_correction",
        "address_update",
    },
    ("source_records", "resolution_status"): {
        "linked", "identifier_conflict", "unresolved", "review_required", "duplicate_ingestion",
    },
    ("source_links", "link_status"): {"linked", "accepted"},
}

FOREIGN_KEYS = (
    ("affiliations", "doctor_id", "doctors", "doctor_id", False),
    ("affiliations", "evidence_id", "evidence", "evidence_id", False),
    ("aliases", "doctor_id", "doctors", "doctor_id", False),
    ("aliases", "evidence_id", "evidence", "evidence_id", False),
    ("audit_events", "doctor_id", "doctors", "doctor_id", False),
    ("audit_events", "review_id", "reviews", "review_id", False),
    ("doctors", "primary_affiliation_id", "affiliations", "affiliation_id", True),
    ("documents", "source_id", "sources", "source_id", False),
    ("events", "doctor_id", "doctors", "doctor_id", False),
    ("events", "evidence_id", "evidence", "evidence_id", False),
    ("evidence", "source_record_id", "source_records", "source_record_id", False),
    ("evidence", "document_id", "documents", "document_id", True),
    ("field_provenance", "doctor_id", "doctors", "doctor_id", False),
    ("field_provenance", "observation_id", "observations", "observation_id", False),
    ("field_provenance", "review_id", "reviews", "review_id", True),
    ("identity_constraints", "left_doctor_id", "doctors", "doctor_id", False),
    ("identity_constraints", "right_doctor_id", "doctors", "doctor_id", False),
    ("identity_constraints", "left_record_id", "source_records", "source_record_id", False),
    ("identity_constraints", "right_record_id", "source_records", "source_record_id", False),
    ("link_history", "source_record_id", "source_records", "source_record_id", False),
    ("link_history", "doctor_id", "doctors", "doctor_id", False),
    ("observations", "doctor_id", "doctors", "doctor_id", True),
    ("observations", "source_record_id", "source_records", "source_record_id", False),
    ("observations", "evidence_id", "evidence", "evidence_id", False),
    ("review_candidates", "review_id", "reviews", "review_id", False),
    ("review_candidates", "candidate_doctor_id", "doctors", "doctor_id", False),
    ("reviews", "doctor_id", "doctors", "doctor_id", True),
    ("reviews", "source_record_id", "source_records", "source_record_id", False),
    ("reviews", "candidate_doctor_id", "doctors", "doctor_id", True),
    ("source_links", "source_record_id", "source_records", "source_record_id", False),
    ("source_links", "doctor_id", "doctors", "doctor_id", False),
    ("source_links", "review_id", "reviews", "review_id", True),
    ("source_records", "source_id", "sources", "source_id", False),
    ("source_records", "document_id", "documents", "document_id", True),
    ("source_records", "duplicate_of_record_id", "source_records", "source_record_id", True),
    ("document_content", "document_id", "documents", "document_id", False),
)


@dataclass
class LoadedDataset:
    tables: Dict[str, List[Dict[str, Any]]]
    fingerprint: str
    csv_directory: str
    row_counts: Dict[str, int] = field(default_factory=dict)


def _error(filename: str, line: Optional[int], reason: str) -> Dict[str, Any]:
    return {"filename": filename, "line": line, "reason": reason}


def _parse_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    text = str(value)
    if not re.fullmatch(r"-?\d+", text):
        raise ValueError(f"expected an integer, found {value!r}")
    return int(text)


def _parse_date(value: str) -> str:
    datetime.strptime(value, "%Y-%m-%d")
    return value


def _parse_timestamp(value: str) -> str:
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _convert_row(table: str, row: Dict[str, Optional[str]]) -> Dict[str, Any]:
    data: Dict[str, Any] = dict(row)
    for column in INT_COLUMNS.get(table, ()):
        raw = data.get(column)
        data[column] = None if raw is None else _parse_int(raw)
    for column in BOOL_COLUMNS.get(table, ()):
        raw = data.get(column)
        data[column] = None if raw is None else parse_bool(str(raw))
    for column in DATE_COLUMNS.get(table, ()):
        raw = data.get(column)
        if raw is not None:
            data[column] = _parse_date(str(raw))
    for column in TIMESTAMP_COLUMNS.get(table, ()):
        raw = data.get(column)
        if raw is not None:
            data[column] = _parse_timestamp(str(raw))
    if table == "source_links" or table == "review_candidates":
        raw = data.get("demo_score")
        if raw is None:
            data["demo_score"] = None
        else:
            data["demo_score"] = float(str(raw))
    # Identifiers and postal codes remain strings.
    for column in ("postal_code", "official_npi", "mock_npi_ref", "provider_identifier"):
        if column in data and data[column] is not None:
            data[column] = str(data[column])
    return data


def _pk_tuple(row: Dict[str, Any], columns: Sequence[str]) -> Tuple[str, ...]:
    return tuple("" if row.get(column) is None else str(row.get(column)) for column in columns)


def load_dataset(csv_directory: Path) -> LoadedDataset:
    errors: List[Dict[str, Any]] = []
    raw_tables: Dict[str, List[Dict[str, Any]]] = {}
    hasher = hashlib.sha256()

    if not csv_directory.is_dir():
        raise DatasetValidationError([
            _error(str(csv_directory), None, "CSV directory does not exist. Set CSV_DIRECTORY to the supplied csv folder."),
        ])

    for filename in EXPECTED_FILES:
        path = csv_directory / filename
        hasher.update(filename.encode("utf-8"))
        if not path.exists():
            errors.append(_error(filename, None, "Required CSV file is missing."))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hasher.update(digest.encode("utf-8"))
        table = filename.replace(".csv", "")
        try:
            fieldnames, numbered_rows = read_csv_rows(path)
        except Exception as exc:  # noqa: BLE001 - surface as a dataset error
            errors.append(_error(filename, None, f"Could not parse CSV: {exc}"))
            continue
        expected = list(TABLE_COLUMNS[table])
        missing = [column for column in expected if column not in fieldnames]
        if missing:
            errors.append(_error(filename, 1, f"Missing required columns: {', '.join(missing)}"))
        seen: Dict[Tuple[str, ...], int] = {}
        converted: List[Dict[str, Any]] = []
        pk_cols = PRIMARY_KEYS[table]
        for line, row in numbered_rows:
            try:
                item = _convert_row(table, row)
            except ValueError as exc:
                errors.append(_error(filename, line, str(exc)))
                continue
            for column in pk_cols:
                if item.get(column) is None:
                    errors.append(_error(filename, line, f"Primary key column {column} is empty."))
            for column, allowed in KNOWN_ENUMS.items():
                if column[0] != table:
                    continue
                value = item.get(column[1])
                if value is not None and value not in allowed:
                    errors.append(_error(
                        filename,
                        line,
                        f"Unrecognized {column[1]} value {value!r}. Add it to the allowed set before loading.",
                    ))
            pk = _pk_tuple(item, pk_cols)
            if all(pk) and pk in seen:
                errors.append(_error(
                    filename,
                    line,
                    f"Duplicate primary key {pk} (first seen on line {seen[pk]}).",
                ))
            elif all(pk):
                seen[pk] = line
            item["_source_line"] = line
            converted.append(item)
        raw_tables[table] = converted

    if errors:
        raise DatasetValidationError(errors)

    indexes: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for table, pk_cols in PRIMARY_KEYS.items():
        if len(pk_cols) != 1:
            continue
        indexes[table] = {str(row[pk_cols[0]]): row for row in raw_tables.get(table, [])}

    for table, column, target, target_col, optional in FOREIGN_KEYS:
        target_ids = {str(row[target_col]) for row in raw_tables.get(target, []) if row.get(target_col) is not None}
        for row in raw_tables.get(table, []):
            value = row.get(column)
            if value is None:
                if not optional and column in PRIMARY_KEYS.get(table, ()):
                    errors.append(_error(f"{table}.csv", row.get("_source_line"), f"{column} is required."))
                continue
            if str(value) not in target_ids:
                errors.append(_error(
                    f"{table}.csv",
                    row.get("_source_line"),
                    f"{column}={value} does not match {target}.{target_col}.",
                ))

    _validate_document_citations(raw_tables, errors)
    if errors:
        raise DatasetValidationError(errors)

    for rows in raw_tables.values():
        for row in rows:
            row.pop("_source_line", None)

    return LoadedDataset(
        tables=raw_tables,
        fingerprint=hasher.hexdigest(),
        csv_directory=str(csv_directory),
        row_counts={name: len(rows) for name, rows in raw_tables.items()},
    )


def _validate_document_citations(tables: Dict[str, List[Dict[str, Any]]], errors: List[Dict[str, Any]]) -> None:
    blocks: Dict[Tuple[str, str, int, str], Dict[str, Any]] = {}
    versions_for_doc: Dict[str, set] = {}
    for block in tables.get("document_content", []):
        key = (
            str(block["document_id"]),
            str(block["document_version"]),
            int(block["page_number"]),
            str(block["block_id"]),
        )
        blocks[key] = block
        versions_for_doc.setdefault(str(block["document_id"]), set()).add(str(block["document_version"]))

    documents = {str(doc["document_id"]): doc for doc in tables.get("documents", [])}
    records = {str(row["source_record_id"]): row for row in tables.get("source_records", [])}

    for doc_id, doc in documents.items():
        version = str(doc.get("version"))
        if version not in versions_for_doc.get(doc_id, set()):
            errors.append(_error(
                "documents.csv",
                None,
                f"{doc_id} version {version} has no rows in document_content.csv.",
            ))

    for evid in tables.get("evidence", []):
        line = evid.get("_source_line")
        quoted = evid.get("quoted_text") or ""
        doc_id = evid.get("document_id")
        if doc_id:
            version = evid.get("document_version")
            page = evid.get("page_number")
            block_id = evid.get("block_id")
            if version is None or page is None or not block_id:
                errors.append(_error(
                    "evidence.csv",
                    line,
                    f"{evid.get('evidence_id')} cites a document without version, page, or block.",
                ))
                continue
            block = blocks.get((str(doc_id), str(version), int(page), str(block_id)))
            if not block:
                errors.append(_error(
                    "evidence.csv",
                    line,
                    f"{evid.get('evidence_id')} cites missing block {doc_id} v{version} page {page} {block_id}.",
                ))
                continue
            text = block.get("text") or ""
            if quoted and quoted not in text:
                errors.append(_error(
                    "evidence.csv",
                    line,
                    f"{evid.get('evidence_id')} quoted text is not in the cited document block.",
                ))
            continue
        record = records.get(str(evid.get("source_record_id")))
        field_name = evid.get("source_field")
        if record and field_name:
            original = record.get(field_name)
            original_text = "" if original is None else str(original)
            if quoted and quoted != original_text and quoted not in original_text and original_text not in quoted:
                note = record.get("note_text") or ""
                if quoted not in str(note):
                    errors.append(_error(
                        "evidence.csv",
                        line,
                        f"{evid.get('evidence_id')} quote does not match source field {field_name}.",
                    ))


def dataset_error_lines(errors: Iterable[Dict[str, Any]]) -> List[str]:
    lines = []
    for item in errors:
        location = item.get("filename") or "dataset"
        if item.get("line"):
            location = f"{location}:{item['line']}"
        lines.append(f"{location}: {item.get('reason')}")
    return lines
