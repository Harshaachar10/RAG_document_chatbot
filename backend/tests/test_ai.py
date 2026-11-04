from __future__ import annotations

from app.api.dependencies import get_ai_service, get_repository, get_runtime_store


def _wait(client, job):
    assert job["status"]
    if job["status"] in {"completed", "failed", "interrupted"}:
        return job
    current = client.get(job["status_url"].replace("/api/v1", "/api/v1") if False else f"/api/v1/ai/jobs/{job['job_id']}")
    assert current.status_code == 200
    return current.json()


def test_identity_analysis_excludes_answer_keys_and_does_not_merge(client):
    before = client.get("/api/v1/doctors/HCP-000123").json()
    res = client.post(
        "/api/v1/ai/identity-analyses",
        json={"source_record_ids": ["REC-00001", "REC-00005"], "force_refresh": False},
    )
    assert res.status_code == 202, res.text
    job = _wait(client, res.json())
    assert job["status"] == "completed", job
    analysis = job["analysis"]
    assert analysis["label"] == "AI-generated from supplied evidence"
    assert analysis["outcome"] == "model_result"
    assert analysis["response"]["recommendation"] in {
        "same_doctor", "different_doctors", "insufficient_evidence", "conflicting_identifier",
    }
    user = get_ai_service().client.last_user
    for banned in ("expected_resolution", "true_doctor_id", "expected_action", "SC-01", "decision_basis", "evaluation_only"):
        assert banned not in user
    after = client.get("/api/v1/doctors/HCP-000123").json()
    assert after["version"] == before["version"]
    assert after["preferred_name"] == before["preferred_name"]


def test_cached_analysis_is_not_called_twice(client):
    body = {"source_record_ids": ["REC-00001", "REC-00002"], "force_refresh": False}
    first = client.post("/api/v1/ai/identity-analyses", json=body)
    assert first.status_code == 202
    first_job = _wait(client, first.json())
    calls = get_ai_service().client.calls
    second = client.post("/api/v1/ai/identity-analyses", json=body)
    assert second.status_code == 202
    second_job = second.json()
    assert second_job["cached"] is True
    assert second_job["analysis_id"] == first_job["analysis_id"]
    assert get_ai_service().client.calls == calls


def test_unknown_evidence_id_is_rejected(client):
    service = get_ai_service()
    service.client.scripted["scripted_json"] = {
        "recommendation": "same_doctor",
        "summary": "Invented.",
        "supporting_evidence_ids": ["EVD-NOT-REAL"],
        "conflicting_evidence_ids": [],
        "missing_information": [],
        "proposed_changes": [],
        "requires_human_review": True,
    }
    res = client.post(
        "/api/v1/ai/identity-analyses",
        json={"source_record_ids": ["REC-00010", "REC-00015"], "force_refresh": True},
    )
    assert res.status_code == 202
    job = _wait(client, res.json())
    assert job["status"] == "failed"
    assert job["error"]["code"] == "AI_VALIDATION_FAILED"
    service.client.scripted.pop("scripted_json", None)


def test_prompt_digest_changes_fingerprint():
    from app.ai.context import _fingerprint

    left = _fingerprint("identity_analysis", {"records": ["REC-00001"]}, "digest-a", "deployment", None)
    right = _fingerprint("identity_analysis", {"records": ["REC-00001"]}, "digest-b", "deployment", None)
    assert left != right


def test_source_change_invalidates_cache(client):
    body = {"source_record_ids": ["REC-00621"], "force_refresh": False}
    first = client.post("/api/v1/ai/change-extractions", json=body)
    assert first.status_code == 202
    _wait(client, first.json())
    repo = get_repository()

    def mutate(state):
        state["source_records"]["REC-00621"]["note_text"] = (
            (state["source_records"]["REC-00621"].get("note_text") or "") + " added observation"
        )

    repo.runtime.mutate(mutate)
    second = client.post("/api/v1/ai/change-extractions", json=body)
    assert second.status_code == 202
    assert second.json().get("cached") is not True


def test_missing_record_and_bad_request(client):
    missing = client.post(
        "/api/v1/ai/identity-analyses",
        json={"source_record_ids": ["REC-00001", "REC-DOES-NOT-EXIST"]},
    )
    assert missing.status_code == 404
    bad = client.post("/api/v1/ai/identity-analyses", json={"source_record_ids": ["REC-00001"]})
    assert bad.status_code == 422


def test_profile_summary_does_not_run_on_read(client):
    calls = get_ai_service().client.calls
    res = client.get("/api/v1/doctors/HCP-000123/ai-summary")
    assert res.status_code == 200
    assert res.json()["available"] is False
    assert get_ai_service().client.calls == calls
    created = client.post("/api/v1/doctors/HCP-000123/ai-summary", json={"force_refresh": False})
    assert created.status_code == 202
    job = _wait(client, created.json())
    assert job["status"] == "completed"
    assert job["analysis"]["operation"] == "profile_summary"


def test_interrupted_job_is_marked_on_restart(client):
    store = get_runtime_store()

    def mutate(state):
        state.setdefault("ai_jobs", {})["JOB-OPEN"] = {
            "job_id": "JOB-OPEN",
            "status": "calling_model",
            "operation": "identity_analysis",
            "requested_at": "2026-11-04T00:00:00Z",
        }

    store.mutate(mutate)
    fingerprint = store.get()["dataset_fingerprint"]
    store._state = None
    store.ensure_initialized(lambda: {}, dataset_fingerprint=fingerprint)
    job = client.get("/api/v1/ai/jobs/JOB-OPEN")
    assert job.status_code == 200
    assert job.json()["status"] == "interrupted"
