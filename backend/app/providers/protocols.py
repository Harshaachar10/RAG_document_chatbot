from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class ResolutionProvider(Protocol):
    def explain_match(self, doctor_id: str) -> Optional[Dict[str, Any]]: ...


class RecommendationProvider(Protocol):
    def get_recommendation(self, recommendation_id: str) -> Optional[Dict[str, Any]]: ...
