from __future__ import annotations

from pathlib import Path

from app.core.settings import Settings
from app.repositories.dataset_loader import load_dataset
from app.utils.csv_io import read_csv_dicts

BACKEND = Path(__file__).resolve().parents[1]


def _csv_dir() -> Path:
    return Settings().csv_path


def test_minimum_counts():
    csv_dir = _csv_dir()
    doctors = read_csv_dicts(csv_dir / "doctors.csv")
    records = read_csv_dicts(csv_dir / "source_records.csv")
    reviews = read_csv_dicts(csv_dir / "reviews.csv")
    documents = read_csv_dicts(csv_dir / "documents.csv")
    content = read_csv_dicts(csv_dir / "document_content.csv")
    assert len(doctors) >= 120
    assert len(records) >= 500
    assert len(reviews) >= 30
    assert len(documents) >= 12
    assert len(content) >= len(documents)


def test_sarah_showcase():
    csv_dir = _csv_dir()
    doctors = {d["doctor_id"]: d for d in read_csv_dicts(csv_dir / "doctors.csv")}
    sarah = doctors["HCP-000123"]
    assert sarah["preferred_name"] == "Sarah Lee-Kim"
    assert sarah["official_npi"] is None
    assert sarah["mock_npi_ref"] == "SYN-NPI-000001"
    reviews = {r["review_id"]: r for r in read_csv_dicts(csv_dir / "reviews.csv")}
    assert reviews["REV-021"]["status"] == "pending"
    assert reviews["REV-021"]["proposed_value"] == "Lakeshore Cancer Institute"


def test_dataset_loader_is_referentially_valid_once():
    first = load_dataset(_csv_dir())
    second = load_dataset(_csv_dir())
    assert first.row_counts == second.row_counts
    assert first.fingerprint == second.fingerprint
    assert "evaluation_only" not in first.csv_directory.replace("\\", "/")


def test_document_content_joins_and_quotes():
    csv_dir = _csv_dir()
    content = read_csv_dicts(csv_dir / "document_content.csv")
    by_block = {
        (row["document_id"], row["document_version"], row["page_number"], row["block_id"]): row["text"]
        for row in content
    }
    for evid in read_csv_dicts(csv_dir / "evidence.csv"):
        if not evid.get("document_id"):
            continue
        key = (
            evid["document_id"],
            evid["document_version"],
            evid["page_number"],
            evid["block_id"],
        )
        assert key in by_block, evid["evidence_id"]
        assert evid["quoted_text"] in (by_block[key] or "")


def test_every_doctor_has_linked_records():
    csv_dir = _csv_dir()
    links = read_csv_dicts(csv_dir / "source_links.csv")
    counts = {}
    for link in links:
        if link.get("link_status") in {"linked", "accepted"} and link.get("doctor_id"):
            counts[link["doctor_id"]] = counts.get(link["doctor_id"], 0) + 1
    doctors = read_csv_dicts(csv_dir / "doctors.csv")
    for doctor in doctors:
        assert counts.get(doctor["doctor_id"], 0) >= 1, doctor["doctor_id"]


def test_postal_codes_stay_strings():
    records = read_csv_dicts(_csv_dir() / "source_records.csv")
    coded = [row["postal_code"] for row in records if row.get("postal_code")]
    assert coded
    assert all(isinstance(value, str) for value in coded)
