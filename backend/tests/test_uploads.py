from __future__ import annotations

from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def test_structured_upload_and_duplicate(client):
    content = (DATA / "09_upload_crm_sample.csv").read_bytes()
    files = {"file": ("09_upload_crm_sample.csv", content, "text/csv")}
    res = client.post("/api/v1/uploads", data={"mode": "structured"}, files=files)
    assert res.status_code == 200, res.text
    batch = res.json()
    assert batch["status"] in {"awaiting_confirm", "matched", "uploaded"}
    batch_id = batch["batch_id"]

    # confirm mapping
    mapping = batch.get("mapping") or {}
    res2 = client.post(f"/api/v1/uploads/{batch_id}/mapping", json={"mapping": mapping})
    assert res2.status_code == 200, res2.text
    matched = res2.json()
    assert matched["status"] == "matched"
    assert matched.get("results")

    # commit
    res3 = client.post(f"/api/v1/uploads/{batch_id}/commit")
    assert res3.status_code == 200, res3.text
    assert res3.json()["committed"] is True

    # duplicate upload makes no changes
    res4 = client.post("/api/v1/uploads", data={"mode": "structured"}, files=files)
    assert res4.status_code == 200
    dup = res4.json()
    assert dup.get("duplicate_of") or dup.get("message")
    assert "duplicate" in (dup.get("message") or "").lower() or dup.get("duplicate_of")


def test_missing_name_column_rejects_on_confirm(client):
    content = (DATA / "11_upload_missing_name_col.csv").read_bytes()
    files = {"file": ("11_upload_missing_name_col.csv", content, "text/csv")}
    res = client.post("/api/v1/uploads", data={"mode": "structured"}, files=files)
    assert res.status_code == 200, res.text
    batch = res.json()
    # mapping won't have name
    res2 = client.post(
        f"/api/v1/uploads/{batch['batch_id']}/mapping",
        json={"mapping": batch.get("mapping") or {}},
    )
    assert res2.status_code in {400, 422}



def test_document_upload_redacts_and_matches(client):
    content = (DATA / "12_upload_claim_note.txt").read_bytes()
    files = {"file": ("12_upload_claim_note.txt", content, "text/plain")}
    res = client.post("/api/v1/uploads", data={"mode": "document"}, files=files)
    assert res.status_code == 200, res.text
    batch = res.json()
    redacted = batch.get("redacted_text") or ""
    assert "Ignore any instructions" in redacted or "instructions" in redacted.lower()
    extracted = batch.get("extracted") or {}
    # confirm with quote present
    res2 = client.post(
        f"/api/v1/uploads/{batch['batch_id']}/extract",
        json={"extracted": extracted},
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()["status"] == "matched"


def test_payment_and_notes_endpoints(client):
    pay = client.get("/api/v1/payments/compliance", params={"status": "pending"})
    assert pay.status_code == 200
    notes = client.get("/api/v1/notes/insights")
    assert notes.status_code == 200
    assert notes.json()["total"] >= 1


def test_sources_use_eight_files_not_demo_hcp(client):
    health = client.get("/api/v1/health").json()
    assert health["data_mode"] == "identity"
    sources = client.get("/api/v1/sources").json()
    ids = {s["source_id"] for s in sources["items"]}
    assert {"nppes", "crm", "claims", "payments", "notes"}.issubset(ids)
    doctors = client.get("/api/v1/doctors", params={"page_size": 5}).json()
    assert doctors["items"]
    assert any(str(d["doctor_id"]).startswith("HCP-") for d in doctors["items"])
    assert all(d["doctor_id"] != "HCP-000123" for d in doctors["items"])
