from __future__ import annotations

import uuid


def test_approve_lakeshore_affiliation(client):
    detail = client.get("/api/v1/reviews/REV-021").json()
    assert detail["status"] == "pending"
    assert detail["recommendation"]["label"] == "Prepared result"
    version = detail["version"]
    before = client.get("/api/v1/doctors/HCP-000123").json()
    key = str(uuid.uuid4())
    res = client.post(
        "/api/v1/reviews/REV-021/decisions",
        json={
            "decision": "approved",
            "action": "approve_update",
            "selected_doctor_id": "HCP-000123",
            "comment": "Supported by the practice-change evidence.",
            "expected_version": version,
            "idempotency_key": key,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["review"]["status"] == "approved"
    assert "HCP-000123" in body["changed_doctor_ids"]

    doctor = client.get("/api/v1/doctors/HCP-000123").json()
    primary = doctor["primary_affiliation"]
    assert primary["organization_name"] == "Lakeshore Cancer Institute"
    assert primary["is_primary"] is True
    oak = next(a for a in doctor["affiliations"] if a["organization_name"] == "Oakridge Oncology")
    assert oak["relationship_status"] == "historical_observation"
    assert oak.get("effective_to") in (None, "")
    assert doctor["version"] == before["version"] + 1
    history = client.get("/api/v1/doctors/HCP-000123/history").json()
    assert any(item["event_type"] == "review_decision" for item in history["items"])
    audit = client.get("/api/v1/doctors/HCP-000123/review-history").json()
    assert any(item["audit_id"] == body["audit_id"] for item in audit["items"])

    res2 = client.post(
        "/api/v1/reviews/REV-021/decisions",
        json={
            "decision": "approved",
            "action": "approve_update",
            "selected_doctor_id": "HCP-000123",
            "comment": "Supported by the practice-change evidence.",
            "expected_version": version,
            "idempotency_key": key,
        },
    )
    assert res2.status_code == 200
    assert res2.json()["audit_id"] == body["audit_id"]

    res3 = client.post(
        "/api/v1/reviews/REV-021/decisions",
        json={
            "decision": "approved",
            "action": "approve_update",
            "comment": "again",
            "expected_version": body["review"]["version"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert res3.status_code == 409
    assert res3.json()["error"]["code"] == "REVIEW_ALREADY_DECIDED"


def test_hard_conflict_cannot_link(client):
    detail = client.get("/api/v1/reviews/REV-010").json()
    res = client.post(
        "/api/v1/reviews/REV-010/decisions",
        json={
            "decision": "linked",
            "action": "link_records",
            "selected_doctor_id": "HCP-000123",
            "comment": "attempt override",
            "expected_version": detail["version"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "IDENTITY_CONFLICT"


def test_stale_version_conflict(client):
    detail = client.get("/api/v1/reviews/REV-019").json()
    res = client.post(
        "/api/v1/reviews/REV-019/decisions",
        json={
            "decision": "deferred",
            "action": "defer",
            "comment": "Need more evidence",
            "expected_version": detail["version"] + 5,
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REVIEW_VERSION_CONFLICT"


def test_missing_review(client):
    res = client.get("/api/v1/reviews/REV-DOES-NOT-EXIST")
    assert res.status_code == 404
