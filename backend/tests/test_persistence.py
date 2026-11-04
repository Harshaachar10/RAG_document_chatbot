from __future__ import annotations

import uuid


def test_decision_persists_in_runtime(client):
    detail = client.get("/api/v1/reviews/REV-019").json()
    key = str(uuid.uuid4())
    res = client.post(
        "/api/v1/reviews/REV-019/decisions",
        json={
            "decision": "deferred",
            "action": "defer",
            "comment": "Waiting for stronger corroboration.",
            "expected_version": detail["version"],
            "idempotency_key": key,
        },
    )
    assert res.status_code == 200, res.text
    again = client.get("/api/v1/reviews/REV-019").json()
    assert again["status"] == "deferred"

    res2 = client.post(
        "/api/v1/reviews/REV-019/decisions",
        json={
            "decision": "resumed",
            "action": "resume",
            "comment": "Returning to queue",
            "expected_version": again["version"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert res2.status_code == 200, res2.text
    assert client.get("/api/v1/reviews/REV-019").json()["status"] == "pending"


def test_demo_run_starts(client):
    res = client.post("/api/v1/demo-runs")
    assert res.status_code == 202
    body = res.json()
    assert body["mode"] == "simulation"
    assert body["status"] in {"running", "completed"}
    run = client.get(f"/api/v1/demo-runs/{body['run_id']}")
    assert run.status_code == 200
