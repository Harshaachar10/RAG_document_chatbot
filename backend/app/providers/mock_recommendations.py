from __future__ import annotations

from typing import Any, Dict, Optional



class MockRecommendationProvider:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def get_recommendation(self, recommendation_id: str) -> Optional[Dict[str, Any]]:
        payload = self.repo.get_recommendation(recommendation_id)
        return dict(payload) if payload else None
