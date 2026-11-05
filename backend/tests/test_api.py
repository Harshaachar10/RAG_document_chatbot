from __future__ import annotations


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["data_mode"] == "identity"
    assert body["analysis_mode"] == "mock"
    assert body["data_classification"] == "synthetic"
    assert body["ai_ready"] is True
    assert body["ready"] is True


def test_reference_data(client):
    res = client.get("/api/v1/reference-data")
    assert res.status_code == 200
    body = res.json()
    assert "Dermatology" in body["specialties"]
    assert any("Oncology" in s or "Hematology" in s for s in body["specialties"])
    assert len(body["sources"]) == 8
    assert "probable_match" in body["review_case_types"]


def test_doctors_list_and_sarah_search(client):
    res = client.get("/api/v1/doctors", params={"search": "Lee", "page_size": 50})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    ids = [i["doctor_id"] for i in body["items"]]
    assert any(i.startswith("HCP-") for i in ids)
    assert any(i.get("official_npi") == "1309803819" for i in body["items"])


def test_doctor_detail_chicago_lee(client):
    listing = client.get("/api/v1/doctors", params={"search": "Lee-Kim", "page_size": 50}).json()
    doctor = next(i for i in listing["items"] if i.get("official_npi") == "1309803819")
    res = client.get(f"/api/v1/doctors/{doctor['doctor_id']}")
    assert res.status_code == 200
    body = res.json()
    assert "lee" in (body["preferred_name"] or "").lower()
    assert body["official_npi"] == "1309803819"
    assert body["linked_record_count"] >= 1


def test_dashboard_kpis(client):
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    body = res.json()
    keys = {k["key"] for k in body["kpis"]}
    assert "source_records_processed" in keys
    assert "pending_human_review" in keys
    processed = next(k for k in body["kpis"] if k["key"] == "source_records_processed")
    assert processed["value"] >= 10


def test_sources_list(client):
    res = client.get("/api/v1/sources")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 8
    keys = {s["source_id"] for s in body["items"]}
    assert {"nppes", "crm", "claims", "payments"}.issubset(keys)


def test_exports(client):
    res = client.get("/api/v1/exports/doctors")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "HCP-" in res.text
