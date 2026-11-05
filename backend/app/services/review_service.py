from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.providers.mock_recommendations import MockRecommendationProvider
from app.identity.labels import case_label, risk_rank, source_label
from app.services.filtering import matches_search, paginate, sort_items
from app.utils.dates import utc_now_iso
from app.utils.links import is_linked_status


VALID_ACTIONS = {
    "possible_duplicate": {"link_records", "keep_separate", "defer"},
    "same_name_ambiguity": {"select_candidate", "leave_unresolved", "defer"},
    "identifier_conflict": {"leave_unresolved", "select_candidate", "defer"},
    "name_update": {"approve_update", "reject_update", "defer", "resume"},
    "address_update": {"approve_update", "reject_update", "defer", "resume"},
    "affiliation_update": {"approve_update", "reject_update", "defer", "resume"},
    "contact_update": {"approve_update", "reject_update", "defer", "resume"},
    "duplicate_ingestion": {"reject_update", "defer", "resume"},
    "link_correction": {"approve_update", "reject_update", "defer", "resume"},
    # Identity pipeline queues — business actions
    "probable_match": {"approve", "reject", "needs_more_information", "defer", "resume", "select_candidate", "leave_unresolved"},
    "compliance_review": {"approve", "reject", "needs_more_information", "defer", "resume", "select_candidate", "leave_unresolved"},
    "npi_assignment": {"approve", "reject", "needs_more_information", "defer", "resume", "leave_unresolved"},
    "unmatched": {"approve", "reject", "needs_more_information", "defer", "resume", "select_candidate", "leave_unresolved"},
    "not_a_person": {"approve", "reject", "defer", "resume", "leave_unresolved"},
    "auto_link": {"approve", "reject", "defer", "resume"},
}

FIELD_UPDATE_NAMES = {
    "preferred_name", "primary_affiliation", "affiliation", "address", "city",
    "professional_email", "email", "professional_phone", "phone",
}

# No invented reviewer names — unassigned unless a real logged-in user is provided later.
ASSIGNMENT_STATUSES = (
    "unassigned",
    "assigned_for_human_review",
)

VALID_DECISION_ACTIONS = {
    "approve",
    "reject",
    "needs_more_information",
    "defer",
    "resume",
    # legacy aliases still accepted
    "select_candidate",
    "leave_unresolved",
    "link_records",
    "keep_separate",
    "approve_update",
    "reject_update",
}


class ReviewService:
    def __init__(self, repo: Any, recommendations: MockRecommendationProvider) -> None:
        self.repo = repo
        self.recommendations = recommendations

    def list_reviews(
        self,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        case_type: Optional[str] = None,
        severity: Optional[str] = None,
        source_id: Optional[str] = None,
        sort_by: str = "created_at",
        sort_direction: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        doctors = {d["doctor_id"]: d for d in self.repo.list_doctors()}
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        now = datetime.now(timezone.utc)
        items = []
        for review in self.repo.list_reviews():
            if status and review.get("status") != status:
                continue
            if case_type and review.get("case_type") != case_type:
                continue
            if severity and review.get("severity") != severity:
                continue
            if source_id:
                rec = records.get(review.get("source_record_id") or "")
                if not rec or rec.get("source_id") != source_id:
                    continue
            doctor = doctors.get(review.get("doctor_id") or "")
            blob = " ".join([
                review.get("title") or "",
                review.get("review_id") or "",
                doctor.get("preferred_name") if doctor else "",
                review.get("doctor_id") or "",
            ])
            if search and not matches_search(blob, search):
                continue
            created = review.get("created_at")
            age_days = None
            if created:
                try:
                    text = created.replace("Z", "+00:00")
                    age_days = max(0, (now - datetime.fromisoformat(text)).days)
                except ValueError:
                    age_days = None
            candidates = self.repo.list_candidates(review["review_id"])
            cand_names = []
            for c in candidates:
                d = doctors.get(c.get("candidate_doctor_id") or "")
                label = (d.get("preferred_name") if d else None) or c.get("target_label") or c.get("doctor_name")
                if label:
                    cand_names.append(label)
            rec = records.get(review.get("source_record_id") or "")
            doctor_name = (doctor.get("preferred_name") if doctor else None) or (
                cand_names[0] if cand_names else None
            ) or (rec.get("recorded_name") if rec else None)
            items.append({
                "review_id": review["review_id"],
                "doctor_id": review.get("doctor_id"),
                "doctor_name": doctor_name,
                "case_type": review.get("case_type"),
                "issue_type": case_label(review.get("case_type")),
                "title": review.get("title"),
                "question": review.get("title"),
                "severity": review.get("severity"),
                "risk": review.get("severity"),
                "status": review.get("status"),
                "source_record_id": review.get("source_record_id"),
                "source_id": review.get("source_key") or (rec.get("source_id") if rec else None),
                "source_label": review.get("source_label") or source_label((rec or {}).get("source_id")),
                "candidate_doctor_id": review.get("candidate_doctor_id"),
                "proposed_field": review.get("proposed_field"),
                "proposed_value": review.get("proposed_value"),
                "match_score": review.get("match_score") or review.get("pipeline_score"),
                "recommended_action": review.get("recommended_action") or review.get("pipeline_action"),
                "created_at": review.get("created_at"),
                "updated_at": review.get("updated_at"),
                "age_days": age_days,
                "candidates_summary": ", ".join([n for n in cand_names if n]) or "No candidates",
                "assigned_reviewer": review.get("assigned_reviewer") or "Unassigned",
                "assignment_status": review.get("assignment_status") or "unassigned",
                "assignment_comment": review.get("assignment_comment"),
                "assigned_at": review.get("assigned_at"),
                "_risk_key": risk_rank(
                    review.get("case_type"), review.get("severity"), review.get("pipeline_action")
                ),
            })
            if sort_by == "risk" or sort_by == "created_at":
                pass
        if sort_by == "risk":
            items.sort(key=lambda r: (*r.get("_risk_key", (9, 9)), r.get("created_at") or ""))
            if sort_direction == "desc":
                items.reverse()
            for row in items:
                row.pop("_risk_key", None)
        else:
            for row in items:
                row.pop("_risk_key", None)
            allow = {"created_at", "updated_at", "severity", "status", "case_type", "title", "review_id", "match_score"}
            items = sort_items(items, sort_by, sort_direction, allow, "review_id")
        page_items, total = paginate(items, page, page_size)
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "applied_filters": {
                "search": search, "status": status, "case_type": case_type,
                "severity": severity, "source_id": source_id,
                "sort_by": sort_by, "sort_direction": sort_direction,
            },
            "snapshot_version": self.repo.snapshot_version(),
        }

    def get_review(self, review_id: str) -> Dict[str, Any]:
        review = self.repo.get_review(review_id)
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        return self._detail_from_state(self.repo.state(), review_id)

    def _detail_from_state(self, state: Dict[str, Any], review_id: str) -> Dict[str, Any]:
        review = state["reviews"].get(review_id)
        if not review:
            raise NotFoundError(f"Review {review_id} not found")
        doctors = state["doctors"]
        records = state["source_records"]
        candidates_raw = [c for c in state.get("review_candidates") or [] if c.get("review_id") == review_id]
        candidates = []
        for c in candidates_raw:
            d = doctors.get(c.get("candidate_doctor_id") or "")
            candidates.append({
                "candidate_doctor_id": c.get("candidate_doctor_id"),
                "doctor_name": d.get("preferred_name") if d else (c.get("target_label")),
                "demo_score": c.get("score") if c.get("score") is not None else c.get("demo_score"),
                "evidence_summary": c.get("rationale") or c.get("evidence_summary"),
                "target_id": c.get("target_id"),
                "target_source": c.get("target_source"),
                "hard_stops": c.get("hard_stops") or [],
                "contributions": c.get("contributions") or [],
                "rank": c.get("rank"),
            })
        source_record = records.get(review.get("source_record_id") or "")
        doctor = doctors.get(review.get("doctor_id") or "")
        candidate_doctor = doctors.get(review.get("candidate_doctor_id") or "")
        recommendation = self._recommendation_payload(state, review)

        evidence_rows = []
        for evid in state["evidence"].values():
            if source_record and evid.get("source_record_id") == source_record.get("source_record_id"):
                evidence_rows.append(evid)
        for ref in recommendation.get("evidence_refs") or []:
            if ref in state["evidence"] and state["evidence"][ref] not in evidence_rows:
                evidence_rows.append(state["evidence"][ref])

        comparison = self._build_comparison(
            review=review,
            source_record=source_record,
            doctor=doctor,
            candidate_doctor=candidate_doctor,
            evidence_rows=evidence_rows,
        )

        case_type = review.get("case_type")
        status = review.get("status")
        valid = set(VALID_ACTIONS.get(case_type, set()))
        if status == "deferred":
            valid = {"resume"} | ({a for a in valid if a != "defer"})
        elif status in {"completed", "approved", "rejected"}:
            valid = set()
        elif status == "pending" and "resume" in valid:
            valid.discard("resume")

        impact = {
            "proposed_field": review.get("proposed_field"),
            "proposed_value": review.get("proposed_value"),
            "action_effects": self._describe_impact(case_type),
        }
        current_state = {
            "status": status,
            "doctor_id": review.get("doctor_id"),
            "version": int(review.get("version") or 1),
        }
        return {
            "review_id": review_id,
            "doctor_id": review.get("doctor_id"),
            "case_type": case_type,
            "title": review.get("title"),
            "severity": review.get("severity"),
            "status": status,
            "source_record_id": review.get("source_record_id"),
            "candidate_doctor_id": review.get("candidate_doctor_id"),
            "proposed_field": review.get("proposed_field"),
            "proposed_value": review.get("proposed_value"),
            "recommendation_id": review.get("recommendation_id"),
            "created_at": review.get("created_at"),
            "updated_at": review.get("updated_at"),
            "version": int(review.get("version") or 1),
            "valid_actions": sorted(valid),
            "comparison": comparison,
            "recommendation": recommendation,
            "evidence": evidence_rows,
            "impact": impact,
            "candidates": candidates,
            "current_state": current_state,
            "assigned_reviewer": review.get("assigned_reviewer"),
            "assignment_status": review.get("assignment_status") or "unassigned",
            "assignment_comment": review.get("assignment_comment"),
            "assigned_at": review.get("assigned_at"),
            "available_reviewers": [],
            "pipeline_action": review.get("pipeline_action"),
            "pipeline_reason": review.get("pipeline_reason"),
            "pipeline_score": review.get("pipeline_score"),
            "queue": review.get("queue"),
            "record_flags": review.get("record_flags") or [],
            "npi_lookups": review.get("npi_lookups") or [],
            "match_explanation": review.get("match_explanation") or candidates,
            "recommended_action": review.get("recommended_action") or review.get("pipeline_action"),
            "match_score": review.get("match_score") or review.get("pipeline_score"),
            "source_label": review.get("source_label") or source_label(
                (source_record or {}).get("source_id") if source_record else None
            ),
            "issue_type": case_label(case_type),
            "raw_record": (source_record or {}).get("raw") or {},
            "standardized_record": (source_record or {}).get("standardized") or {},
        }

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _present(value: Any) -> bool:
        text = str(value or "").strip()
        return bool(text) and text.lower() not in {"missing", "none", "n/a", "na", "unknown"}

    def _doctor_npi(self, doctor: Optional[Dict[str, Any]]) -> Optional[str]:
        if not doctor:
            return None
        return doctor.get("official_npi") or doctor.get("mock_npi_ref") or None

    def _build_comparison(
        self,
        *,
        review: Dict[str, Any],
        source_record: Optional[Dict[str, Any]],
        doctor: Optional[Dict[str, Any]],
        candidate_doctor: Optional[Dict[str, Any]],
        evidence_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        doctor_npi = self._doctor_npi(doctor)
        source_npi = (source_record or {}).get("provider_identifier")
        identifier_kind = (source_record or {}).get("identifier_kind")
        source_profile = {
            **(source_record or {}),
            "npi_display": source_npi if self._present(source_npi) else None,
            "identifier_kind": identifier_kind,
        }
        doctor_profile = {
            "doctor_id": (doctor or {}).get("doctor_id") or review.get("doctor_id"),
            "preferred_name": (doctor or {}).get("preferred_name"),
            "specialty": (doctor or {}).get("specialty"),
            "city": (doctor or {}).get("city"),
            "state": (doctor or {}).get("state"),
            "email": (doctor or {}).get("professional_email"),
            "phone": (doctor or {}).get("professional_phone"),
            "npi_display": doctor_npi if self._present(doctor_npi) else None,
            "npi_status": (doctor or {}).get("npi_status"),
        }
        candidate_profile = None
        if candidate_doctor and candidate_doctor.get("doctor_id") != doctor_profile.get("doctor_id"):
            candidate_profile = {
                "doctor_id": candidate_doctor.get("doctor_id"),
                "preferred_name": candidate_doctor.get("preferred_name"),
                "specialty": candidate_doctor.get("specialty"),
                "npi_display": self._doctor_npi(candidate_doctor),
                "email": candidate_doctor.get("professional_email"),
            }

        field_pairs = [
            ("name", "Name", (source_record or {}).get("recorded_name"), doctor_profile.get("preferred_name")),
            ("npi", "NPI / provider identifier", source_npi, doctor_npi),
            ("credential", "Credential", (source_record or {}).get("credential_reference"), None),
            ("specialty", "Specialty", (source_record or {}).get("specialty"), doctor_profile.get("specialty")),
            ("practice", "Practice / affiliation", (source_record or {}).get("practice_name"), None),
            ("address", "Address", (source_record or {}).get("address_line"), None),
            ("city", "City", (source_record or {}).get("city"), doctor_profile.get("city")),
            ("state", "State", (source_record or {}).get("state"), doctor_profile.get("state")),
            ("email", "Email", (source_record or {}).get("email"), doctor_profile.get("email")),
            ("phone", "Phone", (source_record or {}).get("phone"), doctor_profile.get("phone")),
        ]

        field_assessments: List[Dict[str, Any]] = []
        agreements: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        missing: List[Dict[str, Any]] = []
        uncertain: List[Dict[str, Any]] = []

        for key, label, left, right in field_pairs:
            left_present = self._present(left)
            right_present = self._present(right)
            status = "uncertain"
            explanation = ""
            if key == "npi":
                kind = self._norm(identifier_kind)
                if kind == "malformed" or (left_present and not str(left).replace("-", "").isalnum()):
                    status = "conflict"
                    explanation = (
                        f"Submitted identifier “{left}” is malformed or incomplete "
                        f"compared with the golden reference “{right or 'not recorded'}”."
                    )
                elif kind in {"missing", "absent"} or not left_present:
                    status = "missing"
                    explanation = (
                        "This submission did not include an NPI / provider identifier. "
                        f"Golden profile reference: {right or 'not recorded'}."
                    )
                elif left_present and right_present and self._norm(left) != self._norm(right):
                    status = "conflict"
                    explanation = (
                        f"Submitted identifier “{left}” does not match the golden reference “{right}”."
                    )
                elif left_present and right_present:
                    status = "match"
                    explanation = "Submitted identifier matches the golden reference."
                elif left_present and not right_present:
                    status = "uncertain"
                    explanation = "Identifier appears on the submission, but the golden profile has no verified NPI."
            elif left_present and right_present and self._norm(left) == self._norm(right):
                status = "match"
                explanation = "Values match."
            elif left_present and right_present:
                status = "conflict"
                explanation = f"Submission has “{left}” while the golden profile has “{right}”."
            elif not left_present and right_present:
                status = "missing"
                explanation = f"Not provided on this submission. Golden profile has “{right}”."
            elif left_present and not right_present:
                status = "uncertain"
                explanation = f"Provided on the submission (“{left}”), not confirmed on the golden profile."
            else:
                status = "uncertain"
                explanation = "Neither side has a usable value."

            # Only invent assessments from actual field values — skip pure-empty noise except NPI for identifier cases.
            if key != "npi" and not left_present and not right_present:
                continue

            row = {
                "field": key,
                "label": label,
                "status": status,
                "source_value": left if left_present else None,
                "doctor_value": right if right_present else None,
                "explanation": explanation,
            }
            field_assessments.append(row)
            if status == "match":
                agreements.append({"field": key, "label": label, "value": left})
            elif status == "conflict":
                conflicts.append({"field": key, "label": label, "source": left, "doctor": right, "explanation": explanation})
            elif status == "missing":
                missing.append({"field": key, "label": label, "doctor": right, "explanation": explanation})
            else:
                uncertain.append({"field": key, "label": label, "source": left, "doctor": right, "explanation": explanation})

        conflict_focus = None
        title = (review.get("title") or "").lower()
        case_type = review.get("case_type") or ""
        if case_type == "identifier_conflict" or "npi" in title:
            npi_row = next((r for r in field_assessments if r["field"] == "npi"), None)
            conflict_focus = {
                "kind": "identifier",
                "label": review.get("title") or "Identifier conflict",
                "supplied_identifier": source_npi if self._present(source_npi) else None,
                "identifier_kind": identifier_kind,
                "golden_identifier": doctor_npi if self._present(doctor_npi) else None,
                "candidate_identifier": self._doctor_npi(candidate_doctor) if candidate_doctor else None,
                "candidate_doctor_id": (candidate_doctor or {}).get("doctor_id"),
                "candidate_name": (candidate_doctor or {}).get("preferred_name"),
                "explanation": (npi_row or {}).get("explanation")
                or "Inspect the submitted identifier against the golden reference and cited evidence.",
                "evidence_ids": [e.get("evidence_id") for e in evidence_rows if e.get("evidence_id")],
            }

        return {
            "source_profile": source_profile,
            "doctor_profile": doctor_profile,
            "candidate_profile": candidate_profile,
            "field_assessments": field_assessments,
            "agreements": agreements,
            "conflicts": conflicts,
            "missing": missing,
            "uncertain": uncertain,
            "conflict_focus": conflict_focus,
            "submission_summary": {
                "provided": [r["label"] for r in field_assessments if self._present(r.get("source_value"))],
                "missing": [r["label"] for r in missing],
                "conflicts": [r["label"] for r in conflicts],
                "uncertain": [r["label"] for r in uncertain],
            },
        }

    def list_reviewers(self) -> Dict[str, Any]:
        return {"items": [], "note": "No named reviewers configured. Cases remain Unassigned."}

    def assign_for_human_review(self, review_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        assign = bool(payload.get("assign", True))
        reviewer = (payload.get("assigned_reviewer") or "").strip()
        comment = (payload.get("assignment_comment") or "").strip()
        expected_version = payload.get("expected_version")

        if assign and not reviewer:
            raise ValidationAppError("assigned_reviewer is required when assigning")
        if not assign:
            reviewer = ""

        def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
            review = state["reviews"].get(review_id)
            if not review:
                raise NotFoundError(f"Review {review_id} not found")
            current_version = int(review.get("version") or 1)
            if expected_version is not None and int(expected_version) != current_version:
                raise ConflictError(
                    "REVIEW_VERSION_CONFLICT",
                    "This case has changed since it was loaded.",
                    details={"expected_version": expected_version, "current_version": current_version},
                )
            # Assignment never auto-approves or notifies.
            review["assigned_reviewer"] = reviewer or None
            review["assignment_status"] = "assigned_for_human_review" if assign and reviewer else "unassigned"
            review["assignment_comment"] = comment or None
            review["assigned_at"] = utc_now_iso() if assign and reviewer else None
            review["updated_at"] = utc_now_iso()
            review["version"] = current_version + 1
            state["reviews"][review_id] = review
            audit_id = f"AUD-ASSIGN-{review_id}-{int(datetime.now(timezone.utc).timestamp())}"
            state.setdefault("audit_events", {})[audit_id] = {
                "audit_id": audit_id,
                "doctor_id": review.get("doctor_id"),
                "review_id": review_id,
                "action": "human_evaluation_assignment",
                "actor_label": "Demo Steward",
                "summary": (
                    f"Assigned to {reviewer} for human review"
                    if assign and reviewer
                    else "Cleared human evaluation assignment"
                ),
                "occurred_at": utc_now_iso(),
                "is_seeded": False,
            }
            return {"audit_id": audit_id}

        result = self.repo.runtime.mutate(mutator)
        detail = self.get_review(review_id)
        return {
            "review": detail,
            "changed_doctor_ids": [detail["doctor_id"]] if detail.get("doctor_id") else [],
            "snapshot_version": self.repo.snapshot_version(),
            "audit_id": result["audit_id"],
        }

    def _describe_impact(self, case_type: str) -> List[str]:
        return {
            "possible_duplicate": [
                "Link records attaches an eligible unassigned source record to an existing master.",
                "Keep separate leaves the source record unassigned.",
            ],
            "same_name_ambiguity": [
                "Select supported candidate assigns the source record to that master.",
                "Leave unresolved keeps the record unassigned.",
            ],
            "identifier_conflict": [
                "Hard identity conflicts cannot be overridden with a generic link.",
                "Leave unresolved or defer are the only allowed final paths.",
            ],
            "affiliation_update": [
                "Approve sets the proposed affiliation as primary and retains prior current affiliation as historical observation without inventing an end date.",
            ],
            "name_update": ["Approve updates the preferred name and keeps the previous name as an alias."],
            "address_update": ["Approve updates city/state/address fields on the golden profile."],
            "contact_update": ["Approve updates the professional contact field. It does not assign an NPI."],
            "duplicate_ingestion": ["Reject leaves the repeated ingestion out of the master. It does not delete history."],
            "link_correction": ["Approve moves the source link to the selected doctor and records link history."],
        }.get(case_type, [])

    def _recommendation_payload(self, state: Dict[str, Any], review: Dict[str, Any]) -> Dict[str, Any]:
        analysis_id = review.get("analysis_id")
        if review.get("origin") == "ai_generated" and analysis_id:
            analysis = (state.get("ai_analyses") or {}).get(analysis_id) or {}
            return {
                "label": "AI-generated from supplied evidence",
                "origin": "ai_generated",
                "generated_at": analysis.get("completed_at"),
                "cached": bool(analysis.get("served_from_cache")),
                "analysis_id": analysis_id,
                "summary": (analysis.get("response") or {}).get("summary"),
                "response": analysis.get("response") or {},
                "evidence_display": analysis.get("evidence_display") or [],
            }
        return {
            "label": "Identity pipeline result",
            "origin": "identity_pipeline",
            "summary": review.get("pipeline_reason")
            or "Routed by the historical identity resolution pipeline. Confirm or override before changing golden records.",
            "proposed_field": review.get("proposed_field"),
            "proposed_value": review.get("proposed_value"),
            "pipeline_action": review.get("pipeline_action"),
            "pipeline_score": review.get("pipeline_score"),
            "queue": review.get("queue"),
        }

    def decide(self, review_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        comment = (payload.get("comment") or "").strip()
        action = payload.get("action")
        decision = payload.get("decision")
        idempotency_key = payload.get("idempotency_key")
        expected_version = payload.get("expected_version")
        selected_doctor_id = payload.get("selected_doctor_id")

        if not idempotency_key:
            raise ValidationAppError("idempotency_key is required")
        if not action:
            raise ValidationAppError("action is required")
        if not comment and action not in {"resume"}:
            raise ValidationAppError("comment/reason is required for final decisions")

        existing = self.repo.runtime.get_idempotent(idempotency_key)
        if existing:
            if existing.get("request") != self._canonical_request(payload):
                raise ConflictError(
                    "IDEMPOTENCY_KEY_REUSED",
                    "Idempotency key was reused with a different payload.",
                )
            return existing["response"]

        def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
            review = state["reviews"].get(review_id)
            if not review:
                raise NotFoundError(f"Review {review_id} not found")
            current_version = int(review.get("version") or 1)
            if expected_version is not None and int(expected_version) != current_version:
                raise ConflictError(
                    "REVIEW_VERSION_CONFLICT",
                    "This case has changed since it was loaded.",
                    details={"expected_version": expected_version, "current_version": current_version},
                )
            status = review.get("status")
            if status in {"completed", "approved", "rejected"} and action != "resume":
                raise ConflictError("REVIEW_ALREADY_DECIDED", "This case has already been reviewed.")

            case_type = review.get("case_type")
            allowed = set(VALID_ACTIONS.get(case_type, set()))
            if status == "deferred":
                allowed = {"resume"} | allowed
            if case_type == "identifier_conflict" and action not in {"leave_unresolved", "defer", "resume"}:
                raise ConflictError(
                    "IDENTITY_CONFLICT",
                    "Hard identity conflicts cannot be overridden with a link or a field approval.",
                    details={"review_id": review_id, "action": action},
                )
            if action not in allowed and not (status == "deferred" and action == "resume"):
                raise ValidationAppError(
                    f"Action {action} is not valid for case type {case_type} in status {status}",
                    details={"valid_actions": sorted(allowed)},
                )

            candidate_ids = self._candidate_ids(state, review_id, review)
            if selected_doctor_id and selected_doctor_id not in candidate_ids and selected_doctor_id != review.get("doctor_id"):
                raise ValidationAppError(
                    "selected_doctor_id must belong to the reviewed case",
                    details={"selected_doctor_id": selected_doctor_id},
                )

            changed_doctor_ids: Set[str] = set()
            now = utc_now_iso()
            audit_id = f"AUD-LIVE-{len(state['audit_events']) + 1:05d}"

            if action == "defer":
                review["status"] = "deferred"
                decision_label = "deferred"
            elif action == "resume":
                review["status"] = "pending"
                decision_label = "resumed"
            elif action == "link_records":
                target = selected_doctor_id or review.get("doctor_id") or review.get("candidate_doctor_id")
                if not target:
                    raise ValidationAppError("selected_doctor_id is required to link records")
                self._link_unassigned(state, review, target, now)
                changed_doctor_ids.add(target)
                review["status"] = "completed"
                decision_label = "linked"
            elif action == "keep_separate":
                self._mark_source_status(state, review.get("source_record_id"), "unresolved", None)
                review["status"] = "completed"
                decision_label = "kept_separate"
            elif action == "select_candidate":
                if not selected_doctor_id:
                    raise ValidationAppError("selected_doctor_id is required")
                self._link_unassigned(state, review, selected_doctor_id, now)
                changed_doctor_ids.add(selected_doctor_id)
                review["status"] = "completed"
                decision_label = "candidate_selected"
            elif action == "leave_unresolved":
                self._mark_source_status(state, review.get("source_record_id"), "unresolved", None)
                review["status"] = "completed"
                decision_label = "left_unresolved"
            elif action == "approve_update":
                did = review.get("doctor_id")
                if not did:
                    raise ValidationAppError("Review has no doctor_id")
                self._apply_field_update(state, review, approve=True, now=now, comment=comment)
                changed_doctor_ids.add(did)
                review["status"] = "approved"
                decision_label = "approved"
            elif action == "reject_update":
                did = review.get("doctor_id")
                if did:
                    changed_doctor_ids.add(did)
                review["status"] = "rejected"
                decision_label = "rejected"
            elif action == "approve":
                target = selected_doctor_id or review.get("doctor_id") or review.get("candidate_doctor_id")
                if target:
                    self._link_unassigned(state, review, target, now)
                    changed_doctor_ids.add(target)
                elif review.get("case_type") == "compliance_review":
                    # Compliance approve = acknowledge proposed correction without changing filed payment values
                    self._mark_source_status(state, review.get("source_record_id"), "linked", review.get("doctor_id"))
                else:
                    raise ValidationAppError("selected_doctor_id is required to approve a match")
                review["status"] = "approved"
                decision_label = "approved"
            elif action == "reject":
                self._mark_source_status(state, review.get("source_record_id"), "unresolved", None)
                review["status"] = "rejected"
                decision_label = "rejected"
            elif action == "needs_more_information":
                review["status"] = "deferred"
                review["needs_more_information"] = True
                decision_label = "needs_more_information"
            else:
                raise ValidationAppError(f"Unsupported action {action}")

            review["updated_at"] = now
            review["version"] = current_version + 1
            if review.get("doctor_id"):
                changed_doctor_ids.add(review["doctor_id"])
            if review.get("analysis_id") and review["analysis_id"] in state.get("ai_analyses", {}):
                state["ai_analyses"][review["analysis_id"]]["human_decision_status"] = decision_label

            # timeline + audit
            event_id = f"EVT-LIVE-{len(state['events']) + 1:06d}"
            doctor_for_event = review.get("doctor_id") or selected_doctor_id
            if doctor_for_event:
                state["events"][event_id] = {
                    "event_id": event_id,
                    "doctor_id": doctor_for_event,
                    "event_type": "review_decision",
                    "title": f"Review decision: {action}",
                    "description": comment or decision_label,
                    "previous_value": None,
                    "new_value": review.get("proposed_value"),
                    "document_date": None,
                    "submitted_at": now,
                    "submitted_to": None,
                    "effective_date": None,
                    "recorded_at": now,
                    "review_status": decision_label,
                    "evidence_id": None,
                }
            state["audit_events"][audit_id] = {
                "audit_id": audit_id,
                "doctor_id": doctor_for_event,
                "review_id": review_id,
                "action": action,
                "actor_label": "Steward",
                "summary": comment or f"{action} on {review_id}",
                "occurred_at": now,
                "is_seeded": False,
            }
            state.setdefault("decision_log", []).append({
                "review_id": review_id,
                "action": action,
                "decision": decision or decision_label,
                "at": now,
            })

            detail = self._detail_from_state(state, review_id)
            response = {
                "review": detail,
                "changed_doctor_ids": sorted(changed_doctor_ids),
                "snapshot_version": int(state.get("snapshot_version") or 1) + 1,
                "audit_id": audit_id,
            }
            state.setdefault("idempotency", {})[idempotency_key] = {
                "request": self._canonical_request(payload),
                "response": response,
            }
            return response

        return self.repo.runtime.mutate(mutator)

    def _canonical_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "decision": payload.get("decision"),
            "action": payload.get("action"),
            "selected_doctor_id": payload.get("selected_doctor_id"),
            "comment": payload.get("comment"),
            "expected_version": payload.get("expected_version"),
        }

    def _candidate_ids(self, state: Dict[str, Any], review_id: str, review: Dict[str, Any]) -> Set[str]:
        ids = {
            c.get("candidate_doctor_id")
            for c in state.get("review_candidates") or []
            if c.get("review_id") == review_id and c.get("candidate_doctor_id")
        }
        if review.get("doctor_id"):
            ids.add(review["doctor_id"])
        if review.get("candidate_doctor_id"):
            ids.add(review["candidate_doctor_id"])
        return {i for i in ids if i}

    def _mark_source_status(
        self,
        state: Dict[str, Any],
        source_record_id: Optional[str],
        resolution_status: str,
        doctor_id: Optional[str],
    ) -> None:
        if not source_record_id:
            return
        rec = state["source_records"].get(source_record_id)
        if rec:
            rec["resolution_status"] = resolution_status
        for link in state["source_links"].values():
            if link.get("source_record_id") == source_record_id:
                if is_linked_status(link.get("link_status")) and doctor_id is None:
                    # do not silently break an existing link unless reassigning
                    continue
                link["link_status"] = "linked" if doctor_id else resolution_status
                link["doctor_id"] = doctor_id

    def _link_unassigned(
        self,
        state: Dict[str, Any],
        review: Dict[str, Any],
        doctor_id: str,
        now: str,
    ) -> None:
        source_record_id = review.get("source_record_id")
        if not source_record_id:
            raise ValidationAppError("Review has no source_record_id to link")
        rec = state["source_records"].get(source_record_id)
        if not rec:
            raise NotFoundError(f"Source record {source_record_id} not found")
        if rec.get("record_kind") != "identity_entry":
            raise ValidationAppError("Only identity_entry records can be linked as doctor entries")
        # Ensure no other accepted link exists for a different doctor
        for link in state["source_links"].values():
            if link.get("source_record_id") != source_record_id:
                continue
            if is_linked_status(link.get("link_status")) and link.get("doctor_id") and link.get("doctor_id") != doctor_id:
                raise ConflictError(
                    "SOURCE_RECORD_ALREADY_LINKED",
                    "Source record already linked to a different doctor.",
                )
        self._reject_hard_identity_conflict(state, source_record_id, doctor_id)
        updated = False
        for link in state["source_links"].values():
            if link.get("source_record_id") == source_record_id:
                link["doctor_id"] = doctor_id
                link["link_status"] = "linked"
                link["decision_basis"] = "steward_link_records"
                updated = True
        if not updated:
            link_id = f"LNK-LIVE-{len(state['source_links']) + 1:06d}"
            state["source_links"][link_id] = {
                "link_id": link_id,
                "source_record_id": source_record_id,
                "doctor_id": doctor_id,
                "link_status": "linked",
                "decision_basis": "steward_link_records",
                "demo_score": None,
                "review_id": review.get("review_id"),
            }
        rec["resolution_status"] = "linked"
        doctor = state["doctors"].get(doctor_id)
        if doctor:
            doctor["updated_at"] = now
            doctor["version"] = int(doctor.get("version") or 1) + 1

    def _reject_hard_identity_conflict(self, state: Dict[str, Any], source_record_id: str, doctor_id: str) -> None:
        for constraint in (state.get("identity_constraints") or {}).values():
            if constraint.get("constraint_type") != "cannot_link":
                continue
            left_record = constraint.get("left_record_id")
            right_record = constraint.get("right_record_id")
            left_doctor = constraint.get("left_doctor_id")
            right_doctor = constraint.get("right_doctor_id")
            blocked = (
                (source_record_id == left_record and doctor_id == right_doctor)
                or (source_record_id == right_record and doctor_id == left_doctor)
            )
            if not blocked:
                continue
            raise ConflictError(
                "IDENTITY_CONFLICT",
                "This link is blocked by a verified cannot-link constraint. "
                f"{constraint.get('basis') or 'The records are different doctors.'}",
                details={"constraint_id": constraint.get("constraint_id")},
            )

    def _apply_field_update(
        self,
        state: Dict[str, Any],
        review: Dict[str, Any],
        *,
        approve: bool,
        now: str,
        comment: str = "",
    ) -> None:
        if not approve:
            return
        doctor_id = review.get("doctor_id")
        doctor = state["doctors"].get(doctor_id or "")
        if not doctor:
            raise NotFoundError(f"Doctor {doctor_id} not found")
        field = review.get("proposed_field")
        value = review.get("proposed_value")
        if field == "preferred_name" and value:
            previous = doctor.get("preferred_name")
            if previous and previous != value:
                alias_id = f"ALS-LIVE-{len(state['aliases']) + 1:05d}"
                state["aliases"][alias_id] = {
                    "alias_id": alias_id,
                    "doctor_id": doctor_id,
                    "name": previous,
                    "alias_type": "previous_name",
                    "observation_date": now[:10],
                    "evidence_id": self._evidence_for_record(state, review.get("source_record_id")),
                }
            doctor["preferred_name"] = value
        elif field in {"primary_affiliation", "affiliation"} and value:
            # Sarah Lakeshore pattern and generic affiliation updates
            current_primary = None
            proposed = None
            for aff in state["affiliations"].values():
                if aff.get("doctor_id") != doctor_id:
                    continue
                if aff.get("is_primary"):
                    current_primary = aff
                if aff.get("relationship_status") == "proposed" and aff.get("organization_name") == value:
                    proposed = aff
                if aff.get("organization_name") == value:
                    proposed = proposed or aff
            if current_primary and (not proposed or current_primary["affiliation_id"] != proposed.get("affiliation_id")):
                current_primary["is_primary"] = False
                if current_primary.get("relationship_status") == "current":
                    current_primary["relationship_status"] = "historical_observation"
                    # do not invent effective_to
            if proposed:
                proposed["is_primary"] = True
                proposed["relationship_status"] = "current"
                doctor["primary_affiliation_id"] = proposed["affiliation_id"]
                if proposed.get("city"):
                    doctor["city"] = proposed["city"]
                if proposed.get("state"):
                    doctor["state"] = proposed["state"]
            else:
                aff_id = f"AFF-LIVE-{len(state['affiliations']) + 1:05d}"
                state["affiliations"][aff_id] = {
                    "affiliation_id": aff_id,
                    "doctor_id": doctor_id,
                    "organization_name": value,
                    "address_line": None,
                    "city": doctor.get("city"),
                    "state": doctor.get("state"),
                    "relationship_status": "current",
                    "is_primary": True,
                    "effective_from": None,
                    "effective_to": None,
                    "observed_at": now[:10],
                    "evidence_id": None,
                }
                doctor["primary_affiliation_id"] = aff_id
        elif field == "address" and value:
            doctor["city"] = value
        elif field in {"professional_email", "email"} and value:
            doctor["professional_email"] = value
        elif field in {"professional_phone", "phone"} and value:
            doctor["professional_phone"] = value
        elif field not in FIELD_UPDATE_NAMES:
            raise ValidationAppError(f"Field {field} cannot be approved from this case.")
        doctor["updated_at"] = now
        doctor["version"] = int(doctor.get("version") or 1) + 1
        evidence_id = self._evidence_for_record(state, review.get("source_record_id"))
        provenance_id = f"PRV-LIVE-{len(state['field_provenance']) + 1:05d}"
        state["field_provenance"][provenance_id] = {
            "provenance_id": provenance_id,
            "doctor_id": doctor_id,
            "field_name": field,
            "selected_value": value,
            "observation_id": None,
            "selection_reason": comment or "Approved by a steward from cited source evidence.",
            "review_id": review.get("review_id"),
            "version": doctor["version"],
            "evidence_ids": [evidence_id] if evidence_id else [],
        }

    def _evidence_for_record(self, state: Dict[str, Any], source_record_id: Optional[str]) -> Optional[str]:
        if not source_record_id:
            return None
        for evid in state["evidence"].values():
            if evid.get("source_record_id") == source_record_id:
                return evid.get("evidence_id")
        return None
