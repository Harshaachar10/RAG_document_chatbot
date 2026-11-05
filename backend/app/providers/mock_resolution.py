from __future__ import annotations

from typing import Any, Dict, List, Optional


class MockResolutionProvider:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def explain_match(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        payload = self.repo.get_recommendation(doctor_id)
        if payload:
            return dict(payload)

        doctor = self.repo.get_doctor(doctor_id) or {}
        links = [l for l in self.repo.list_links() if l.get("doctor_id") == doctor_id]
        constraints = [c for c in self.repo.list_constraints() if c.get("doctor_id") == doctor_id]
        member_uids = doctor.get("member_uids") or [l.get("source_record_id") for l in links]

        side_by_side: List[Dict[str, Any]] = []
        evidence_rows: List[Dict[str, Any]] = []
        scores: List[float] = []
        for uid in member_uids:
            rec = self.repo.get_source_record(uid) if uid else None
            if not rec:
                continue
            side_by_side.append(
                {
                    "source_record_id": uid,
                    "source_id": rec.get("source_id"),
                    "recorded_name": rec.get("recorded_name"),
                    "specialty": rec.get("specialty"),
                    "city": rec.get("city"),
                    "state": rec.get("state"),
                    "npi": rec.get("provider_identifier"),
                    "practice_name": rec.get("practice_name"),
                }
            )
            evidence_rows.append(
                {
                    "evidence_id": f"EV-{uid}",
                    "title": f"{rec.get('source_id')}: {rec.get('original_transaction_id') or uid}",
                    "summary": rec.get("recorded_name"),
                }
            )

        for link in links:
            if link.get("demo_score") is not None:
                try:
                    scores.append(float(link["demo_score"]))
                except (TypeError, ValueError):
                    pass

        avg = round(sum(scores) / len(scores), 4) if scores else None
        npi = doctor.get("official_npi")
        summary = (
            f"Golden record {doctor_id} assembled from {len(member_uids)} source record(s)"
            + (f" under NPI {npi}." if npi else ".")
        )
        return {
            "recommendation_id": f"REC-{doctor_id}",
            "doctor_id": doctor_id,
            "summary": summary,
            "simulated_recommendation": "AUTO_LINK via explainable identity pipeline"
            if links
            else "Reference or provisional identity shell",
            "demo_match_score": avg,
            "decision_method": "identity_pipeline",
            "review_status": doctor.get("identity_status"),
            "ambiguities": [],
            "constraints": constraints,
            "side_by_side": side_by_side,
            "evidence_rows": evidence_rows,
        }
