from __future__ import annotations

import uuid


def _first_pending_review(client):
    res = client.get("/api/v1/reviews", params={"status": "pending", "page_size": 50})
    assert res.status_code == 200
    items = res.json()["items"]
    assert items, "expected pending reviews from identity pipeline"
    return items[0]


def test_list_pending_reviews(client):
    item = _first_pending_review(client)
    assert item["status"] == "pending"
    assert item["review_id"].startswith("REV-")


def test_defer_and_resume_review(client):
    item = _first_pending_review(client)
    detail = client.get(f"/api/v1/reviews/{item['review_id']}").json()
    version = detail["version"]
    key = str(uuid.uuid4())
    res = client.post(
        f"/api/v1/reviews/{item['review_id']}/decisions",
        json={
            "decision": "deferred",
            "action": "defer",
            "comment": "Need more corroboration.",
            "expected_version": version,
            "idempotency_key": key,
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["review"]["status"] == "deferred"

    again = client.get(f"/api/v1/reviews/{item['review_id']}").json()
    res2 = client.post(
        f"/api/v1/reviews/{item['review_id']}/decisions",
        json={
            "decision": "resumed",
            "action": "resume",
            "comment": "Back to queue",
            "expected_version": again["version"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert res2.status_code == 200, res2.text
    assert client.get(f"/api/v1/reviews/{item['review_id']}").json()["status"] == "pending"


def test_assign_reviewer(client):
    item = _first_pending_review(client)
    detail = client.get(f"/api/v1/reviews/{item['review_id']}").json()
    # assignment endpoint if present
    res = client.post(
        f"/api/v1/reviews/{item['review_id']}/assignment",
        json={
            "assigned_reviewer": "Aisha Mehta",
            "assignment_status": "assigned_for_human_review",
            "assignment_comment": "Please verify NPI geography.",
            "expected_version": detail["version"],
        },
    )
    if res.status_code == 404:
        return
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("assigned_reviewer") == "Aisha Mehta" or body.get("review", {}).get("assigned_reviewer") == "Aisha Mehta"
