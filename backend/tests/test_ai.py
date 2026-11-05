from __future__ import annotations

from app.api.dependencies import get_ai_service


def _wait(client, job):
    assert job["status"]
    if job["status"] in {"completed", "failed", "interrupted"}:
        return job
    current = client.get(f"/api/v1/ai/jobs/{job['job_id']}")
    assert current.status_code == 200
    return current.json()


def _sample_record_ids(client, n: int = 2):
    sources = client.get("/api/v1/sources").json()["items"]
    crm = next(s for s in sources if s["source_id"] == "crm")
    records = client.get(f"/api/v1/sources/{crm['source_id']}/records", params={"page_size": 10}).json()
    ids = [r["source_record_id"] for r in records["items"][:n]]
    assert len(ids) == n
    return ids


def test_identity_analysis_runs_without_mutating_doctors(client):
    doctors = client.get("/api/v1/doctors", params={"page_size": 5}).json()["items"]
    assert doctors
    doctor_id = doctors[0]["doctor_id"]
    before = client.get(f"/api/v1/doctors/{doctor_id}").json()
    ids = _sample_record_ids(client, 2)
    res = client.post(
        "/api/v1/ai/identity-analyses",
        json={"source_record_ids": ids, "force_refresh": False},
    )
    assert res.status_code == 202, res.text
    job = _wait(client, res.json())
    assert job["status"] == "completed", job
    analysis = job["analysis"]
    assert analysis["label"] == "AI-generated from supplied evidence"
    assert analysis["outcome"] == "model_result"
    assert analysis["response"]["recommendation"] in {
        "same_doctor",
        "different_doctors",
        "insufficient_evidence",
        "conflicting_identifier",
    }
    user = get_ai_service().client.last_user
    for banned in ("expected_resolution", "true_doctor_id", "expected_action", "SC-01", "decision_basis", "evaluation_only"):
        assert banned not in user
    after = client.get(f"/api/v1/doctors/{doctor_id}").json()
    assert after["version"] == before["version"]
    assert after["preferred_name"] == before["preferred_name"]


def test_cached_analysis_returns_completed(client):
    ids = _sample_record_ids(client, 2)
    body = {"source_record_ids": ids, "force_refresh": True}
    first = client.post("/api/v1/ai/identity-analyses", json=body)
    assert first.status_code == 202
    job1 = _wait(client, first.json())
    assert job1["status"] == "completed"
    second = client.post("/api/v1/ai/identity-analyses", json={**body, "force_refresh": False})
    assert second.status_code == 202
    job2 = _wait(client, second.json())
    assert job2["status"] == "completed"
    assert job2.get("analysis") or job2.get("cached") is not None
