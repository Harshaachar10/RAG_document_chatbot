from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_run_service
from app.schemas.run import DemoRun
from app.services.run_service import RunService

router = APIRouter(prefix="/demo-runs", tags=["demo-runs"])


@router.get("", operation_id="listDemoRuns")
def list_runs(service: RunService = Depends(get_run_service)) -> Dict[str, Any]:
    return service.list_runs()


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DemoRun, operation_id="startDemoRun")
def start_run(service: RunService = Depends(get_run_service)) -> DemoRun:
    return DemoRun(**service.start_run())


@router.get("/{run_id}", response_model=DemoRun, operation_id="getDemoRun")
def get_run(run_id: str, service: RunService = Depends(get_run_service)) -> DemoRun:
    return DemoRun(**service.get_run(run_id))
