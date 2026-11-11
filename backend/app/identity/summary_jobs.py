"""Refresh a doctor's stored summary when that doctor's evidence changes."""

from __future__ import annotations

import asyncio
import threading
from typing import Iterable, List

from app.identity.briefs import alarms_from_decisions, compose_brief
from app.utils.dates import utc_now_iso


def refresh_profiles(repo: object, doctor_ids: Iterable[str]) -> None:
    ids = [doctor_id for doctor_id in doctor_ids if doctor_id]
    if not ids:
        return

    def mutator(state: dict) -> None:
        alarms = alarms_from_decisions(list(state.get("match_decisions") or []))
        by_doctor: dict = {}
        for alarm in alarms:
            did = alarm.get("doctor_id") or ""
            if did:
                by_doctor.setdefault(did, []).append(alarm)
        now = utc_now_iso()
        for doctor_id in ids:
            doctor = (state.get("doctors") or {}).get(doctor_id)
            if not doctor:
                continue
            doctor_alarms = by_doctor.get(doctor_id) or []
            doctor["alarms"] = doctor_alarms
            doctor["profile_brief"] = compose_brief(doctor, doctor_alarms)
            doctor["updated_at"] = now
            doctor["version"] = int(doctor.get("version") or 1) + 1

    repo.runtime.mutate(mutator)  # type: ignore[attr-defined]
    schedule_summaries(ids, force=True)


def schedule_summaries(doctor_ids: List[str], *, force: bool) -> None:
    from app.core.settings import get_settings

    settings = get_settings()
    if settings.analysis_mode != "azure" or not doctor_ids:
        return
    threading.Thread(
        target=_run_summaries,
        args=(list(doctor_ids), force),
        daemon=True,
        name="profile-summaries",
    ).start()


def _run_summaries(doctor_ids: List[str], force: bool) -> None:
    from app.api.dependencies import get_ai_service

    service = get_ai_service()

    async def _go() -> None:
        for doctor_id in doctor_ids:
            job = service.submit_summary(doctor_id, force_refresh=force)
            if job.get("should_run"):
                await service.execute(job["job_id"])

    asyncio.run(_go())
