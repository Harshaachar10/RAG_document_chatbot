from __future__ import annotations


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["data_mode"] == "csv_demo"
    assert body["analysis_mode"] == "mock"
    assert body["data_classification"] == "synthetic"
    assert body["ai_ready"] is True
    assert body["ready"] is True


def test_reference_data(client):
    res = client.get("/api/v1/reference-data")
    assert res.status_code == 200
    body = res.json()
    assert "Medical oncology" in body["specialties"]
    assert len(body["sources"]) == 6


def test_doctors_list_and_sarah_search(client):
    res = client.get("/api/v1/doctors", params={"search": "Sarah Lee", "page_size": 50})
    assert res.status_code == 200
    body = res.json()
    ids = [i["doctor_id"] for i in body["items"]]
    assert "HCP-000123" in ids
    assert body["total"] >= 1


def test_doctor_detail(client):
    res = client.get("/api/v1/doctors/HCP-000123")
    assert res.status_code == 200
    body = res.json()
    assert body["preferred_name"] == "Sarah Lee-Kim"
    assert body["npi_status"] == "Not verified"
    assert body["pending_field_changes"] >= 1


def test_dashboard_kpis(client):
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    body = res.json()
    keys = {k["key"] for k in body["kpis"]}
    assert keys == {
        "source_doctor_entries",
        "golden_profiles",
        "linked_records",
        "consolidated_duplicates",
        "pending_reviews",
        "profiles_with_proposals",
    }
    golden = next(k for k in body["kpis"] if k["key"] == "golden_profiles")
    assert golden["value"] == 120


def test_evidence_and_document(client):
    records = client.get("/api/v1/doctors/HCP-000123/source-records")
    assert records.status_code == 200
    evidence_ids = [eid for row in records.json()["items"] for eid in row["evidence_ids"]]
    assert evidence_ids
    cited = None
    for evidence_id in evidence_ids:
        evid = client.get(f"/api/v1/evidence/{evidence_id}").json()
        if evid.get("document_id") and evid.get("quoted_text"):
            cited = evid
            break
    assert cited is not None
    doc = client.get(
        f"/api/v1/documents/{cited['document_id']}",
        params={"version": cited["document_version"]},
    )
    assert doc.status_code == 200
    pages = doc.json()["pages"]
    assert any(cited["quoted_text"] in block["text"] for page in pages for block in page["blocks"])
    assert "<script" not in doc.text.lower()


def test_exports(client):
    res = client.get("/api/v1/exports/doctors")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "HCP-000123" in res.text
