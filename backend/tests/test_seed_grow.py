"""Seed-and-grow, profiles, and description safety. IDs here are fixtures, not product data."""

from __future__ import annotations

from pathlib import Path

from app.identity.descriptions import describe_doctor, describe_record
from app.identity.grow import assign_rounds
from app.identity.pipeline import run_identity_pipeline
from app.identity.profiles import ProfileStore, propose_profile, validate_profile
from app.identity.search_plan import validate_search_plan

DATA = Path(__file__).resolve().parents[1] / "data"


def _doctor():
    return {
        "doctor_id": "HCP-TEST",
        "npi": "1309803819",
        "name": {"first_norm": "sarah", "last_norm": "leekim", "first": "Sarah", "last": "Lee-Kim", "last_parts": ["lee"]},
        "former_lasts": ["lee"],
        "credentials": ["MD"],
        "state": "IL",
        "city": "Chicago",
        "organization": "Lakeshore Cancer Institute",
        "phone": "",
        "email": "",
        "postal": "60601",
        "specialty": "Medical Oncology",
        "specialty_family": "oncology",
        "licenses": [{"number": "IL-1", "state": "IL"}],
        "license_states": ["IL"],
        "display_name": "Sarah Lee-Kim",
        "former_names": ["Sarah Lee"],
    }


def test_learned_value_is_a_later_round_and_reviews_do_not_teach():
    doctor = _doctor()
    catalog = {"people": [doctor], "by_id": {doctor["doctor_id"]: doctor}, "phone_counts": {}}
    verified = {
        "uid": "a",
        "record_id": "A",
        "action": "AUTO_LINK",
        "npi_status": "VERIFIED",
        "target_id": doctor["doctor_id"],
        "target_npi": doctor["npi"],
        "stated_npi": doctor["npi"],
        "standardized": {"name": {"first_norm": "sarah", "last_norm": "leekim"}, "state": "IL", "phone": "3125550199", "organization": "North Clinic"},
    }
    phone_only = {
        "uid": "b",
        "record_id": "B",
        "action": "AUTO_LINK",
        "npi_status": "MISSING",
        "target_id": doctor["doctor_id"],
        "target_npi": doctor["npi"],
        "stated_npi": "",
        "standardized": {"name": {"first_norm": "", "last_norm": ""}, "phone": "3125550199"},
    }
    review = {
        "uid": "c",
        "record_id": "C",
        "action": "REVIEW",
        "npi_status": "MISSING",
        "target_id": doctor["doctor_id"],
        "target_npi": doctor["npi"],
        "stated_npi": "",
        "standardized": {"name": {"first_norm": "sarah", "last_norm": "lee"}, "state": "IL", "email": "new@example.test"},
    }
    email_only = {
        "uid": "d",
        "record_id": "D",
        "action": "AUTO_LINK",
        "npi_status": "MISSING",
        "target_id": doctor["doctor_id"],
        "target_npi": doctor["npi"],
        "stated_npi": "",
        "standardized": {"email": "new@example.test"},
    }
    result = assign_rounds([verified, phone_only, review, email_only], catalog, max_rounds=5)
    assert verified["round"] == 0
    assert phone_only["round"] >= 1
    assert phone_only["learned_value"] is True
    assert email_only["round"] is None
    assert result["search"]["semantic_status"] == "skipped"
    assert result["rounds"][-1]["stop_reason"]


def test_pipeline_is_deterministic_and_skips_semantic_when_disabled(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    first = run_identity_pipeline(DATA)
    second = run_identity_pipeline(DATA)
    left = [(d["record_id"], d["action"], d.get("round"), d.get("target_id")) for d in first["decisions"]]
    right = [(d["record_id"], d["action"], d.get("round"), d.get("target_id")) for d in second["decisions"]]
    assert left == right
    assert first["embedding"]["status"] == "skipped"
    assert any(d.get("learned_value") and isinstance(d.get("round"), int) and d["round"] >= 1 for d in first["decisions"])
    assert max(d.get("round") or 0 for d in first["decisions"]) <= 5


def test_invalid_search_plan_is_rejected():
    errors = validate_search_plan({"filters": [{"field": "patient_name", "value": "hidden"}], "query": "select *", "top_k": 20})
    assert errors
    assert any("patient_name" in error for error in errors)
    result = run_identity_pipeline(DATA)
    planned = [row for row in result["decisions"] if row.get("search_plan")]
    assert planned
    assert all(row["search_plan"]["valid"] for row in planned)
    assert all("query" not in row["search_plan"] for row in planned)


def test_descriptions_exclude_identifiers():
    doctor = _doctor()
    text = describe_doctor(doctor)
    lowered = text.lower()
    assert "1309803819" not in text
    assert "il-1" not in lowered
    assert "@" not in text
    assert "patient" not in lowered
    record = describe_record(
        {
            "source_key": "crm",
            "standardized": {
                "name": {"display": "Sarah Lee-Kim", "credentials": ["MD"], "first": "Sarah", "last": "Lee-Kim"},
                "specialty_label": "Medical Oncology",
                "organization": "Lakeshore Cancer Institute",
                "city": "Chicago",
                "state": "IL",
                "license_state": "IL",
                "phone": "3125550142",
                "email": "sarah@example.test",
            },
        }
    )
    assert "3125550142" not in record
    assert "example.test" not in record
    assert "Sarah" in record


def test_profiles_require_approval_and_reuse(tmp_path: Path):
    store = ProfileStore(tmp_path / "profiles.json")
    proposal = propose_profile(
        "03_crm_accounts.csv",
        ["Account_ID", "Account_Name", "NPI_vod", "Specialty", "City", "St"],
        [{"Account_ID": "A1", "Account_Name": "Ada Lovelace", "NPI_vod": "1309803819", "Specialty": "Oncology", "City": "Chicago", "St": "IL"}],
    )
    checked = validate_profile(proposal, ["Account_ID", "Account_Name", "NPI_vod", "Specialty", "City", "St"], [])
    assert checked["ok"]
    try:
        store.profile_for_run("crm")
        raised = False
    except PermissionError:
        raised = True
    assert raised
    stored = store.add_proposal(proposal)
    store.decide("crm", stored["version"], "approved", reviewer="Steward", reason="Columns match.")
    first = store.profile_for_run("crm")
    second = store.profile_for_run("crm")
    assert first["version"] == second["version"] == 1
    assert first["status"] == "approved"
