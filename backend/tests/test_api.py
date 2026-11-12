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
    assert any(i.get("official_npi") == "1848459463" for i in body["items"])


def test_doctor_detail_chicago_lee(client):
    listing = client.get("/api/v1/doctors", params={"search": "Lee-Kim", "page_size": 50}).json()
    doctor = next(i for i in listing["items"] if i.get("official_npi") == "1848459463")
    res = client.get(f"/api/v1/doctors/{doctor['doctor_id']}")
    assert res.status_code == 200
    body = res.json()
    assert "lee" in (body["preferred_name"] or "").lower()
    assert body["official_npi"] == "1848459463"
    assert body["linked_record_count"] >= 1


def test_dashboard_kpis(client):
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    body = res.json()
    keys = {k["key"] for k in body["kpis"]}
    assert "records_resolved" in keys
    assert "decisions_waiting" in keys
    processed = next(k for k in body["kpis"] if k["key"] == "records_resolved")
    assert processed["value"] >= 10
    wrong = next(k for k in body["kpis"] if k["key"] == "wrong_npis_caught")
    assert wrong["display"] == str(wrong["value"])
    assert "G0" not in wrong["display"]
    assert wrong["detail"]
    assert isinstance(wrong.get("parts"), list)
    assert {p["label"] for p in wrong["parts"]} >= {"Invalid format", "Group / org NPI"}


def test_sources_list(client):
    res = client.get("/api/v1/sources")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 8
    keys = {s["source_id"] for s in body["items"]}
    assert {"nppes", "crm", "claims", "payments"}.issubset(keys)


def test_story_and_ask_and_preview(client):
    summary = client.get("/api/v1/dashboard/summary").json()
    story = summary["story"]
    assert story["needs_run"] is False
    verified = next(row for row in story["headlines"] if row["key"] == "verified_vs_provisional")
    assert verified["value"] == 23
    assert verified["secondary"] == 1
    doctors = next(row for row in story["headlines"] if row["key"] == "records_to_doctors")
    assert doctors["secondary"] == 24
    wrong_payments = next(row for row in story["would_have_gone_wrong"] if row["key"] == "payments")
    assert wrong_payments["count"] == len(wrong_payments["items"]) or wrong_payments["count"] >= len(wrong_payments["items"])

    answer = client.post("/api/v1/ask", json={"question": "Why are the two Sarah Lees separate?"}).json()
    assert answer["wrote"] is False
    assert answer["citations"]
    assert answer["tools"]

    refused = client.post("/api/v1/ask", json={"question": "What is the weather on Mars?"}).json()
    assert "do not answer" in refused["answer"].lower()

    before = client.get("/api/v1/dashboard/summary").json()["snapshot_version"]
    preview = client.post("/api/v1/match/preview", json={"text": "Dr. S Lee, LCI, Chicago"}).json()
    after = client.get("/api/v1/dashboard/summary").json()["snapshot_version"]
    assert preview["committed"] is False
    assert after == before

    health = client.get("/api/v1/health").json()
    assert health["search_mode"] in {"local", "azure"}


def test_reset_keeps_profiles(client):
    profiles = client.get("/api/v1/source-profiles").json()["items"]
    assert profiles
    reset = client.post("/api/v1/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["profiles_kept"] == len(profiles)
    cleared = client.get("/api/v1/dashboard/summary").json()["story"]
    assert cleared["needs_run"] is True
    assert client.get("/api/v1/doctors").json()["total"] == 0
    assert client.get("/api/v1/source-profiles").json()["items"]


def test_exports(client):
    res = client.get("/api/v1/exports/doctors")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "HCP-" in res.text
