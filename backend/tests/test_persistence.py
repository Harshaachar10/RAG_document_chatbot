from __future__ import annotations

import uuid


def test_decision_persists_in_runtime(client):
    listing = client.get("/api/v1/reviews", params={"status": "pending", "page_size": 10}).json()
    assert listing["items"]
    review_id = listing["items"][0]["review_id"]
    detail = client.get(f"/api/v1/reviews/{review_id}").json()
    key = str(uuid.uuid4())
    res = client.post(
        f"/api/v1/reviews/{review_id}/decisions",
        json={
            "decision": "deferred",
            "action": "defer",
            "comment": "Waiting for stronger corroboration.",
            "expected_version": detail["version"],
            "idempotency_key": key,
        },
    )
    assert res.status_code == 200, res.text
    again = client.get(f"/api/v1/reviews/{review_id}").json()
    assert again["status"] == "deferred"

    res2 = client.post(
        f"/api/v1/reviews/{review_id}/decisions",
        json={
            "decision": "resumed",
            "action": "resume",
            "comment": "Returning to queue",
            "expected_version": again["version"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert res2.status_code == 200, res2.text
    assert client.get(f"/api/v1/reviews/{review_id}").json()["status"] == "pending"


def test_pipeline_run_starts(client):
    res = client.post("/api/v1/demo-runs")
    assert res.status_code == 202
    body = res.json()
    assert body["run_id"].startswith("ID-RUN-")
    assert body["status"] in {"running", "completed", "queued"}
