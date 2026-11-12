"""Known outcomes for the synthetic 01-08 files. IDs belong in this test, not product code."""

from __future__ import annotations

from pathlib import Path

from app.identity.pipeline import run_identity_pipeline

DATA = Path(__file__).resolve().parents[1] / "data"

UNMATCHED = {"CLM-55104", "CLM-55122", "CLM-55127", "E-1142", "HUB-0013"}
COMPLIANCE = {"P-3301", "P-3304", "P-3305", "P-3308", "P-3312", "P-3315", "P-3316"}
AUTO_PAYMENTS = {"P-3302", "P-3303", "P-3306", "P-3309", "P-3310", "P-3311", "P-3313", "P-3314"}


def _run():
    return run_identity_pipeline(DATA)


def test_people_and_master_changes():
    result = _run()
    metrics = result["metrics"]
    assert metrics["doctors"] == 24
    assert metrics["doctors_with_npi"] == 23
    assert metrics["provisional_people"] == 1
    assert metrics["organization_doctors"] == 0
    assert metrics["legacy_rows"] == 24
    assert metrics["merges"] == 3
    assert metrics["splits"] == 1
    assert metrics["new_masters"] == 3
    assert len(metrics["outside_mismatch"]) == 10
    assert len(metrics["group_npi_records"]) == 4
    assert metrics["claim_invalid_or_placeholder"] == 3
    assert metrics["claim_recovered"] == 2
    assert not any(str(g["golden_id"]).replace("HCP-", "") == (g.get("npi") or "") for g in result["golden_records"])


def test_record_actions():
    by_id = {d["record_id"]: d for d in _run()["decisions"]}
    unmatched = {d["record_id"] for d in by_id.values() if d["action"] == "UNMATCHED"}
    assert UNMATCHED <= unmatched

    compliance = {rid for rid, d in by_id.items() if d["action"] == "COMPLIANCE_REVIEW"}
    assert compliance == COMPLIANCE
    for rid in AUTO_PAYMENTS:
        assert by_id[rid]["action"] == "AUTO_LINK"
    assert by_id["P-3307"]["action"] == "PROVISIONAL"
    assert by_id["P-3317"]["action"] == "ORGANIZATION"

    payment = by_id["P-3301"]
    assert payment.get("npi_status") == "MISMATCH"
    assert payment.get("action") == "COMPLIANCE_REVIEW"
    cand_labels = [c.get("target_label") or "" for c in payment.get("candidates") or []]
    assert any("Lee-Kim" in label for label in cand_labels)

    assert by_id["CRM-9401"]["action"] == "REVIEW"
    assert by_id["CRM-9401"]["stated_npi"] == "1576635514"
    assert by_id["CRM-9400"]["action"] == "REVIEW"
    assert by_id["CRM-9400"]["stated_npi"] == "1576635514"
    assert by_id["CLM-55102"]["action"] == "REVIEW"
    assert by_id["CLM-55102"]["stated_npi"] == "1848459461"
    assert by_id["CRM-9602"]["action"] == "REVIEW"
    assert by_id["CRM-9622"]["action"] == "NOT_A_PERSON"
    assert by_id["CRM-9623#dup2"]["action"] == "DEDUPE"

    assert by_id["N-0004"]["safety"]["flagged"] is True
    assert by_id["N-0011"]["target_npi"] == "1370429593"
    assert by_id["N-0012"]["action"] == "AUTO_LINK"
    assert "Tran" in by_id["N-0012"]["target_label"]
    assert by_id["N-0002"]["target_npi"] == "1500605765"
    assert by_id["N-0007"]["action"] == "PROVISIONAL"
    assert by_id["N-0008"]["target_npi"] == "1576634514"
    assert by_id["N-0006"]["action"] == "REVIEW"
    for rid in ("N-0001", "N-0003", "N-0005", "N-0009"):
        quotes = [c.get("quote") or "" for c in by_id[rid].get("proposed_changes") or []]
        assert quotes and all(len(q.split()) >= 4 for q in quotes)


def test_same_name_doctors_stay_separate():
    goldens = _run()["golden_records"]
    def ids_for(fragment: str):
        return {g["golden_id"] for g in goldens if fragment.lower() in (g.get("display_name") or "").lower()}

    assert len(ids_for("park")) >= 2
    assert len(ids_for("john smith")) == 2
    assert len(ids_for("priya sharma")) == 2
    assert len(ids_for("william harris")) == 2
    assert len({g["golden_id"] for g in goldens}) == len(goldens)
