from __future__ import annotations


def test_consolidated_duplicates_exclude_transactions(client):
    summary = client.get("/api/v1/dashboard/summary").json()
    consolidated = next(k for k in summary["kpis"] if k["key"] == "consolidated_duplicates")
    assert consolidated["value"] >= 0
    # Linked records display uses numerator/denominator
    linked = next(k for k in summary["kpis"] if k["key"] == "linked_records")
    assert linked["secondary_value"] >= linked["value"]
    assert "/" in linked["display"]


def test_source_breakdown(client):
    res = client.get("/api/v1/dashboard/source-breakdown")
    assert res.status_code == 200
    body = res.json()
    assert len(body["rows"]) == 6
    assert body["text_summary"]
