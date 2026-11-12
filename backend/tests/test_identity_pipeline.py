from __future__ import annotations

from pathlib import Path

from app.identity.npi import classify_npi, luhn_valid_npi
from app.identity.pipeline import run_identity_pipeline
from app.identity.standardize import parse_person_name, specialty_family

DATA = Path(__file__).resolve().parents[1] / "data"


def test_luhn_and_placeholders():
    assert luhn_valid_npi("1309803819")
    assert classify_npi("0000000000")["status"] == "placeholder"
    assert classify_npi("1309803819")["valid"] is True


def test_name_parsing_credentials_and_reversed():
    p = parse_person_name("Dr. Sarah Lee, MD")
    assert p["first_norm"] == "sarah"
    assert p["last_norm"] == "lee"
    assert "MD" in p["credentials"]
    rev = parse_person_name("LEE-KIM, SARAH")
    assert rev["first_norm"] == "sarah"
    assert rev["last_norm"] == "leekim"
    assert "lee" in rev["last_parts"]


def test_specialty_family():
    assert specialty_family("Hem/Onc") == "oncology"
    assert specialty_family("207RX0202X") == "oncology"


def test_pipeline_fixtures():
    result = run_identity_pipeline(DATA)
    counts = result["counts"]
    assert counts["sources"] == 8
    assert counts["nppes"] == 30
    assert counts["matchable"] >= 140
    assert counts["golden_records"] >= 10
    actions = counts["actions"]
    assert actions.get("AUTO_LINK", 0) >= 50
    assert actions.get("COMPLIANCE_REVIEW", 0) >= 1
    assert actions.get("NOT_A_PERSON", 0) >= 1

    by_id = {d["record_id"]: d for d in result["decisions"]}
    # Chicago Lee (CRM without NPI) → Chicago NPPES, not Houston
    crm = by_id["CRM-7781"]
    assert crm["action"] == "AUTO_LINK"
    assert crm["target_npi"] == "1848459463"
    assert not str(crm["target_id"]).startswith("npi:")

    pay = by_id["P-3301"]
    assert pay["action"] == "COMPLIANCE_REVIEW"

    staff = by_id["CRM-9622"]
    assert staff["action"] == "NOT_A_PERSON"

    dup = next(d for d in result["decisions"] if d["record_id"].startswith("CRM-9623") and "#dup" in d["record_id"])
    assert dup["action"] == "DEDUPE"

    # notes are ingested but not matchable decisions
    assert any(n["record_id"] == "N-0001" for n in result["notes"])
    assert "Maria" not in (next(n for n in result["notes"] if n["record_id"] == "N-0001")["redacted_note"])


def test_answer_key_excluded_from_matching():
    # There is no answer_key file in DEFAULT profiles; ensure nppes excluded
    result = run_identity_pipeline(DATA)
    assert all(not d["source_key"] == "nppes" for d in result["decisions"])
