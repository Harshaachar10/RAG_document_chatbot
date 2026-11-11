"""Cleanup runs, source profiles, and search quality."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_repository
from app.repositories.identity_repository import IdentityRepository

router = APIRouter(tags=["cleanup"])


@router.post("/demo/reset", operation_id="resetDemo")
def reset_demo(repo: IdentityRepository = Depends(get_repository)) -> Dict[str, Any]:
    return repo.reset_demo()


def _state(repo: IdentityRepository) -> Dict[str, Any]:
    return repo.state()


@router.get("/cleanup/runs", operation_id="listCleanupRuns")
def list_runs(repo: IdentityRepository = Depends(get_repository)) -> Dict[str, Any]:
    state = _state(repo)
    return {
        "rounds": state.get("cleanup_rounds") or [],
        "search": state.get("search_quality") or {},
        "embedding": state.get("embedding_status") or {},
        "run": state.get("pipeline_run") or {},
    }


@router.get("/cleanup/rounds/{round_number}", operation_id="getCleanupRound")
def get_round(round_number: int, repo: IdentityRepository = Depends(get_repository)) -> Dict[str, Any]:
    state = _state(repo)
    decisions = [
        d
        for d in (state.get("match_decisions") or [])
        if d.get("round") == round_number
    ]
    return {"round": round_number, "decisions": decisions, "total": len(decisions)}


@router.get("/source-profiles", operation_id="listSourceProfiles")
def list_profiles(repo: IdentityRepository = Depends(get_repository)) -> Dict[str, Any]:
    state = _state(repo)
    return {"items": state.get("source_profiles") or []}


@router.post("/source-profiles/{source_type}/decision", operation_id="decideSourceProfile")
def decide_profile(
    source_type: str,
    body: Dict[str, Any],
    repo: IdentityRepository = Depends(get_repository),
) -> Dict[str, Any]:
    status = body.get("status")
    if status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be approved or rejected")

    def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
        found = None
        for profile in state.get("source_profiles") or []:
            if profile.get("source_type") != source_type:
                continue
            if body.get("version") and int(profile.get("version") or 0) != int(body["version"]):
                continue
            profile["status"] = status
            profile["reviewer"] = body.get("reviewer") or "Unassigned"
            profile["decision_reason"] = body.get("reason") or ""
            found = profile
        if not found:
            raise HTTPException(status_code=404, detail="Profile was not found.")
        return found

    return repo.runtime.mutate(mutator)
