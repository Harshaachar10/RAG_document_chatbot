from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DemoRun(BaseModel):
    run_id: str
    mode: str = "simulation"
    status: str
    current_step: Optional[str] = None
    completed_steps: int = 0
    total_steps: int = 7
    progress_percent: int = 0
    message: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    result_url: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    step_labels: List[str] = Field(default_factory=list)
    result_counts: Optional[dict] = None
