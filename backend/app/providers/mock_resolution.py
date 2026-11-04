from __future__ import annotations

from typing import Any, Dict, Optional

from app.repositories.csv_repository import CsvDemoRepository


class MockResolutionProvider:
    def __init__(self, repo: CsvDemoRepository) -> None:
        self.repo = repo

    def explain_match(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        payload = self.repo.get_recommendation(doctor_id)
        if not payload:
            return {
                "recommendation_id": f"REC-{doctor_id}",
                "doctor_id": doctor_id,
                "summary": "Prepared demo explanation is not available for this profile.",
                "simulated_recommendation": "No simulated recommendation seeded for this doctor.",
                "demo_match_score": None,
                "decision_method": "precomputed_demo",
                "review_status": None,
                "ambiguities": [],
                "constraints": [],
                "side_by_side": [],
                "evidence_rows": [],
            }
        return dict(payload)
