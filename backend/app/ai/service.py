from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence

from app.ai.context import (
    EvidencePack,
    build_change_pack,
    build_identity_pack,
    build_review_pack,
    build_summary_pack,
)
from app.ai.prompts import load_prompt
from app.ai.provider import LlmClient, sanitize_error
from app.ai.validate import parse_model_output
from app.core.exceptions import AppError, NotFoundError, ValidationAppError
from app.core.settings import Settings
from app.repositories.csv_repository import CsvDemoRepository
from app.utils.dates import utc_now_iso
from app.utils.links import is_linked_status

TERMINAL = {"completed", "failed", "interrupted"}
ACTIVE = {"queued", "preparing_evidence", "calling_model", "validating_response"}


class AiService:
    def __init__(self, repo: CsvDemoRepository, settings: Settings, client: LlmClient) -> None:
        self.repo = repo
        self.settings = settings
        self.client = client

    def submit_identity(self, record_ids: Sequence[str], *, force_refresh: bool) -> Dict[str, Any]:
        self._require_ids(record_ids, minimum=2)
        return self._submit("identity_analysis", record_ids=list(record_ids), force_refresh=force_refresh)

    def submit_changes(self, record_ids: Sequence[str], *, force_refresh: bool) -> Dict[str, Any]:
        self._require_ids(record_ids, minimum=1)
        return self._submit("change_extraction", record_ids=list(record_ids), force_refresh=force_refresh)

    def submit_summary(self, doctor_id: str, *, force_refresh: bool) -> Dict[str, Any]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        return self._submit("profile_summary", doctor_id=doctor_id, force_refresh=force_refresh)

    def submit_explanation(self, review_id: str, *, force_refresh: bool) -> Dict[str, Any]:
        if not self.repo.get_review(review_id):
            raise NotFoundError(f"Review {review_id} not found")
        return self._submit("review_explanation", review_id=review_id, force_refresh=force_refresh)

    def latest_summary(self, doctor_id: str) -> Dict[str, Any]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        analyses = [
            row for row in self.repo.state().get("ai_analyses", {}).values()
            if row.get("operation") == "profile_summary"
            and row.get("doctor_id") == doctor_id
            and row.get("response")
        ]
        if not analyses:
            return {"available": False, "doctor_id": doctor_id}
        latest = max(analyses, key=lambda row: row.get("completed_at") or "")
        return {
            "available": True,
            "stale": False,
            "cached": True,
            "analysis": self._public_analysis(latest),
        }

    def get_job(self, job_id: str) -> Dict[str, Any]:
        job = self.repo.state().get("ai_jobs", {}).get(job_id)
        if not job:
            raise NotFoundError(f"AI job {job_id} not found")
        return self._public_job(job)

    def list_jobs(self, limit: int = 20) -> Dict[str, Any]:
        rows = list(self.repo.state().get("ai_jobs", {}).values())
        rows.sort(key=lambda row: row.get("requested_at") or "", reverse=True)
        return {"items": [self._public_job(row) for row in rows[:limit]], "total": len(rows)}

    def get_analysis(self, analysis_id: str) -> Dict[str, Any]:
        row = self.repo.state().get("ai_analyses", {}).get(analysis_id)
        if not row:
            raise NotFoundError(f"AI analysis {analysis_id} not found")
        return self._public_analysis(row)

    def list_analyses(self, *, operation: Optional[str] = None, doctor_id: Optional[str] = None) -> Dict[str, Any]:
        rows = list(self.repo.state().get("ai_analyses", {}).values())
        if operation:
            rows = [row for row in rows if row.get("operation") == operation]
        if doctor_id:
            rows = [row for row in rows if row.get("doctor_id") == doctor_id]
        rows.sort(key=lambda row: row.get("completed_at") or row.get("requested_at") or "", reverse=True)
        return {"items": [self._public_analysis(row) for row in rows], "total": len(rows)}

    async def execute(self, job_id: str) -> None:
        job = self.repo.state().get("ai_jobs", {}).get(job_id)
        if not job or job.get("status") in TERMINAL:
            return
        try:
            self._update_job(job_id, status="preparing_evidence")
            pack = self._pack_for_job(job)
            if pack.narrowing:
                self._finish_narrowing(job_id, pack)
                return
            self._update_job(job_id, status="calling_model", input_fingerprint=pack.fingerprint)
            version, _digest, system = load_prompt(job["operation"])
            completion = await self.client.complete_json(
                system=system,
                user=pack.user_text,
                request_id=job["request_id"],
            )
            self._update_job(job_id, status="validating_response")
            try:
                result = parse_model_output(job["operation"], completion.content, pack)
            except ValueError as exc:
                repair = (
                    pack.user_text
                    + "\n\nThe previous response failed validation: "
                    + str(exc)
                    + "\nReturn only corrected JSON. Do not invent evidence."
                )
                completion = await self.client.complete_json(
                    system=system,
                    user=repair,
                    request_id=job["request_id"] + "-repair",
                )
                self._update_job(job_id, status="validating_response")
                result = parse_model_output(job["operation"], completion.content, pack)
            self._finish_success(
                job_id,
                pack,
                result,
                prompt_version=version,
                completion_usage=completion.usage,
                provider_request_id=completion.request_id,
            )
        except ValueError as exc:
            self._finish_failure(job_id, "AI_VALIDATION_FAILED", str(exc))
        except AppError as exc:
            self._finish_failure(job_id, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001
            secret = getattr(self.settings, "azure_openai_api_key", "")
            self._finish_failure(job_id, "AI_REQUEST_FAILED", sanitize_error(str(exc), secret))

    def _submit(
        self,
        operation: str,
        *,
        record_ids: Optional[List[str]] = None,
        doctor_id: Optional[str] = None,
        review_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        self._ensure_configured()
        pack = self._build(operation, record_ids or [], doctor_id, review_id)
        state = self.repo.state()
        if not force_refresh and not pack.narrowing:
            cached_id = (state.get("ai_cache") or {}).get(pack.fingerprint)
            cached = (state.get("ai_analyses") or {}).get(cached_id or "")
            if cached and cached.get("response"):
                return self._view_cached(cached)
        for job in (state.get("ai_jobs") or {}).values():
            if job.get("input_fingerprint") == pack.fingerprint and job.get("status") in ACTIVE:
                view = self._public_job(job)
                view["should_run"] = False
                return view
        job_id = f"JOB-{uuid.uuid4().hex[:12]}"
        request_id = str(uuid.uuid4())
        now = utc_now_iso()
        version, digest, _system = load_prompt(operation)
        deployment = getattr(self.client, "deployment", self.settings.azure_openai_deployment or "unconfigured")
        record = {
            "job_id": job_id,
            "status": "queued",
            "operation": operation,
            "source_record_ids": pack.source_record_ids,
            "doctor_id": doctor_id,
            "review_id": review_id,
            "input_fingerprint": pack.fingerprint,
            "prompt_version": version,
            "prompt_digest": digest,
            "provider": getattr(self.client, "provider", self.settings.analysis_mode),
            "deployment": deployment,
            "request_id": request_id,
            "requested_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
            "analysis_id": None,
            "error": None,
            "cached": False,
            "should_run": True,
        }

        def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
            state.setdefault("ai_jobs", {})[job_id] = {k: v for k, v in record.items() if k != "should_run"}
            return record

        self.repo.runtime.mutate(mutator)
        return self._public_job(record) | {"should_run": True}

    def _build(
        self,
        operation: str,
        record_ids: Sequence[str],
        doctor_id: Optional[str],
        review_id: Optional[str],
    ) -> EvidencePack:
        _version, digest, _system = load_prompt(operation)
        deployment = getattr(self.client, "deployment", "") or "unconfigured"
        if operation == "identity_analysis":
            return build_identity_pack(
                self.repo, record_ids, prompt_digest=digest, deployment=deployment,
                max_records=self.settings.ai_max_source_records, max_evidence=self.settings.ai_max_evidence,
            )
        if operation == "change_extraction":
            return build_change_pack(
                self.repo, record_ids, prompt_digest=digest, deployment=deployment,
                max_records=self.settings.ai_max_source_records, max_evidence=self.settings.ai_max_evidence,
            )
        if operation == "profile_summary":
            return build_summary_pack(self.repo, doctor_id or "", prompt_digest=digest, deployment=deployment)
        return build_review_pack(
            self.repo, review_id or "", prompt_digest=digest, deployment=deployment,
            max_evidence=self.settings.ai_max_evidence,
        )

    def _pack_for_job(self, job: Dict[str, Any]) -> EvidencePack:
        return self._build(job["operation"], job.get("source_record_ids") or [], job.get("doctor_id"), job.get("review_id"))

    def _ensure_configured(self) -> None:
        if self.settings.analysis_mode == "mock":
            return
        if self.settings.analysis_mode != "azure":
            raise AppError(
                "AI_PROVIDER_UNSUPPORTED",
                "Live analysis uses the configured Azure OpenAI provider.",
                status_code=503,
            )
        missing = self.settings.missing_azure_settings()
        if missing:
            raise AppError(
                "AI_NOT_CONFIGURED",
                "Azure OpenAI is not configured. Set the missing variables and restart the API.",
                status_code=503,
                details={"missing": missing},
            )

    def _finish_success(
        self,
        job_id: str,
        pack: EvidencePack,
        result: Dict[str, Any],
        *,
        prompt_version: str,
        completion_usage: Optional[Dict[str, Any]],
        provider_request_id: str,
    ) -> None:
        analysis_id = f"ANL-{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        job = self.repo.state()["ai_jobs"][job_id]
        analysis = {
            "analysis_id": analysis_id,
            "job_id": job_id,
            "operation": job["operation"],
            "source_record_ids": pack.source_record_ids,
            "doctor_id": job.get("doctor_id"),
            "review_id": job.get("review_id"),
            "input_fingerprint": pack.fingerprint,
            "prompt_version": prompt_version,
            "provider": job.get("provider"),
            "deployment": job.get("deployment"),
            "request_id": provider_request_id,
            "requested_at": job.get("requested_at"),
            "started_at": job.get("started_at") or now,
            "completed_at": now,
            "response": result,
            "evidence_ids": pack.allowed_evidence_ids,
            "evidence_display": pack.evidence_display,
            "token_usage": completion_usage,
            "error": None,
            "human_decision_status": "pending" if result.get("requires_human_review") else "not_required",
            "served_from_cache": False,
            "outcome": "model_result",
            "label": "AI-generated from supplied evidence",
        }

        def mutator(state: Dict[str, Any]) -> None:
            state.setdefault("ai_analyses", {})[analysis_id] = analysis
            state.setdefault("ai_cache", {})[pack.fingerprint] = analysis_id
            current = state["ai_jobs"][job_id]
            current.update({
                "status": "completed",
                "analysis_id": analysis_id,
                "completed_at": now,
                "updated_at": now,
                "input_fingerprint": pack.fingerprint,
                "error": None,
            })
            if job["operation"] in {"identity_analysis", "change_extraction"} and result.get("requires_human_review"):
                self._create_review(state, analysis)

        self.repo.runtime.mutate(mutator)

    def _finish_narrowing(self, job_id: str, pack: EvidencePack) -> None:
        analysis_id = f"ANL-{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        job = self.repo.state()["ai_jobs"][job_id]
        analysis = {
            "analysis_id": analysis_id,
            "job_id": job_id,
            "operation": job["operation"],
            "source_record_ids": pack.source_record_ids,
            "doctor_id": job.get("doctor_id"),
            "review_id": job.get("review_id"),
            "input_fingerprint": pack.fingerprint,
            "prompt_version": job.get("prompt_version"),
            "provider": None,
            "deployment": None,
            "request_id": job.get("request_id"),
            "requested_at": job.get("requested_at"),
            "started_at": now,
            "completed_at": now,
            "response": pack.narrowing,
            "evidence_ids": [],
            "evidence_display": [],
            "token_usage": None,
            "error": None,
            "human_decision_status": "not_required",
            "served_from_cache": False,
            "outcome": "narrowing_required",
            "label": "Narrowing required",
        }

        def mutator(state: Dict[str, Any]) -> None:
            state.setdefault("ai_analyses", {})[analysis_id] = analysis
            current = state["ai_jobs"][job_id]
            current.update({
                "status": "completed",
                "analysis_id": analysis_id,
                "completed_at": now,
                "updated_at": now,
                "error": None,
            })

        self.repo.runtime.mutate(mutator)

    def _finish_failure(self, job_id: str, code: str, message: str) -> None:
        now = utc_now_iso()

        def mutator(state: Dict[str, Any]) -> None:
            job = state["ai_jobs"].get(job_id)
            if not job or job.get("status") in TERMINAL:
                return
            job["status"] = "failed"
            job["error"] = {"code": code, "message": message}
            job["completed_at"] = now
            job["updated_at"] = now

        self.repo.runtime.mutate(mutator)

    def _create_review(self, state: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        response = analysis.get("response") or {}
        changes = response.get("proposed_changes") or []
        first = changes[0] if changes else {}
        recommendation = response.get("recommendation")
        if analysis["operation"] == "identity_analysis":
            case_type = {
                "same_doctor": "possible_duplicate",
                "different_doctors": "possible_duplicate",
                "insufficient_evidence": "same_name_ambiguity",
                "conflicting_identifier": "identifier_conflict",
            }.get(recommendation, "possible_duplicate")
            proposed_field = first.get("field")
            proposed_value = first.get("proposed_value")
        else:
            case_type = _case_type_for_change(first.get("change_type"), first.get("field"))
            proposed_field = first.get("field")
            proposed_value = first.get("proposed_value")
        doctor_id = _single_linked_doctor(state, analysis.get("source_record_ids") or [])
        if case_type == "identifier_conflict":
            doctor_id = doctor_id  # kept for context; approval cannot link
        review_id = f"REV-AI-{len(state['reviews']) + 1:05d}"
        now = utc_now_iso()
        state["reviews"][review_id] = {
            "review_id": review_id,
            "doctor_id": doctor_id,
            "case_type": case_type,
            "title": "AI recommendation",
            "severity": "medium",
            "status": "pending",
            "source_record_id": (analysis.get("source_record_ids") or [None])[0],
            "candidate_doctor_id": doctor_id,
            "proposed_field": proposed_field,
            "proposed_value": proposed_value,
            "recommendation_id": analysis["analysis_id"],
            "analysis_id": analysis["analysis_id"],
            "origin": "ai_generated",
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }
        analysis["review_id"] = review_id
        analysis["human_decision_status"] = "pending"

    def _update_job(self, job_id: str, **fields: Any) -> None:
        now = utc_now_iso()

        def mutator(state: Dict[str, Any]) -> None:
            job = state["ai_jobs"][job_id]
            if fields.get("status") == "calling_model" and not job.get("started_at"):
                job["started_at"] = now
            job.update(fields)
            job["updated_at"] = now

        self.repo.runtime.mutate(mutator)

    def _view_cached(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        job = self.repo.state().get("ai_jobs", {}).get(analysis.get("job_id") or "")
        if not job:
            raise NotFoundError("Cached analysis is missing its job.")
        view = self._public_job(job)
        view["cached"] = True
        view["should_run"] = False
        view["status"] = "completed"
        view["analysis_id"] = analysis["analysis_id"]
        view["completed_at"] = analysis.get("completed_at")
        if view.get("analysis"):
            view["analysis"]["cached"] = True
            view["analysis"]["served_from_cache"] = True
        return view

    def _public_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        analysis = None
        if job.get("analysis_id"):
            analysis = self.repo.state().get("ai_analyses", {}).get(job["analysis_id"])
        return {
            "job_id": job["job_id"],
            "status": job.get("status"),
            "operation": job.get("operation"),
            "source_record_ids": job.get("source_record_ids") or [],
            "doctor_id": job.get("doctor_id"),
            "review_id": job.get("review_id") or (analysis or {}).get("review_id"),
            "analysis_id": job.get("analysis_id"),
            "status_url": f"/api/v1/ai/jobs/{job['job_id']}",
            "requested_at": job.get("requested_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "cached": bool(job.get("cached")),
            "error": job.get("error"),
            "analysis": self._public_analysis(analysis) if analysis else None,
        }

    def _public_analysis(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return {
            "analysis_id": row.get("analysis_id"),
            "operation": row.get("operation"),
            "source_record_ids": row.get("source_record_ids") or [],
            "doctor_id": row.get("doctor_id"),
            "review_id": row.get("review_id"),
            "prompt_version": row.get("prompt_version"),
            "provider": row.get("provider"),
            "deployment": row.get("deployment"),
            "requested_at": row.get("requested_at"),
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at"),
            "response": row.get("response"),
            "evidence_display": row.get("evidence_display") or [],
            "token_usage": row.get("token_usage"),
            "error": row.get("error"),
            "human_decision_status": row.get("human_decision_status"),
            "outcome": row.get("outcome"),
            "label": row.get("label"),
            "cached": bool(row.get("served_from_cache")),
            "served_from_cache": bool(row.get("served_from_cache")),
        }

    def _require_ids(self, record_ids: Sequence[str], *, minimum: int) -> None:
        if len(record_ids) < minimum:
            raise ValidationAppError(
                f"Select at least {minimum} source record{'s' if minimum != 1 else ''}.",
                details={"received": len(record_ids)},
            )
        if len(set(record_ids)) != len(record_ids):
            raise ValidationAppError("Duplicate source record IDs are not allowed in one analysis.")


def _case_type_for_change(change_type: Optional[str], field_name: Optional[str]) -> str:
    mapping = {
        "name_change": "name_update",
        "formatting_variation": "name_update",
        "spelling_variation": "name_update",
        "abbreviation": "name_update",
        "address_change": "address_update",
        "additional_affiliation": "affiliation_update",
        "affiliation_ended": "affiliation_update",
        "contact_change": "contact_update",
        "conflicting_observation": "possible_duplicate",
    }
    if change_type in mapping:
        return mapping[change_type]
    if field_name in {"professional_email", "email", "phone", "professional_phone"}:
        return "contact_update"
    if field_name in {"affiliation", "primary_affiliation"}:
        return "affiliation_update"
    return "possible_duplicate"


def _single_linked_doctor(state: Dict[str, Any], record_ids: Sequence[str]) -> Optional[str]:
    doctors = set()
    for link in state.get("source_links", {}).values():
        if link.get("source_record_id") in set(record_ids) and is_linked_status(link.get("link_status")):
            if link.get("doctor_id"):
                doctors.add(link["doctor_id"])
    if len(doctors) == 1:
        return next(iter(doctors))
    return None
