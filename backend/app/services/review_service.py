from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.providers.mock_recommendations import MockRecommendationProvider
from app.repositories.csv_repository import CsvDemoRepository
from app.services.filtering import matches_search, paginate, sort_items
from app.utils.dates import utc_now_iso
from app.utils.links import is_linked_status


VALID_ACTIONS = {
    "possible_duplicate": {"link_records", "keep_separate", "defer"},
    "same_name_ambiguity": {"select_candidate", "leave_unresolved", "defer"},
    "identifier_conflict": {"leave_unresolved", "defer"},
    "name_update": {"approve_update", "reject_update", "defer", "resume"},
    "address_update": {"approve_update", "reject_update", "defer", "resume"},
    "affiliation_update": {"approve_update", "reject_update", "defer", "resume"},
    "contact_update": {"approve_update", "reject_update", "defer", "resume"},
    "duplicate_ingestion": {"reject_update", "defer", "resume"},
    "link_correction": {"approve_update", "reject_update", "defer", "resume"},
}

FIELD_UPDATE_NAMES = {
    "preferred_name", "primary_affiliation", "affiliation", "address", "city",
    "professional_email", "email", "professional_phone", "phone",
}


class ReviewService:
    def __init__(self, repo: CsvDemoRepository, recommendations: MockRecommendationProvider) -> None:
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
                if d:
                    cand_names.append(d.get("preferred_name"))
            items.append({
                "review_id": review["review_id"],
                "doctor_id": review.get("doctor_id"),
                "doctor_name": doctor.get("preferred_name") if doctor else None,
                "case_type": review.get("case_type"),
                "title": review.get("title"),
                "severity": review.get("severity"),
                "status": review.get("status"),
                "source_record_id": review.get("source_record_id"),
                "candidate_doctor_id": review.get("candidate_doctor_id"),
                "proposed_field": review.get("proposed_field"),
                "proposed_value": review.get("proposed_value"),
                "created_at": review.get("created_at"),
                "updated_at": review.get("updated_at"),
                "age_days": age_days,
                "candidates_summary": ", ".join([n for n in cand_names if n]) or None,
            })
        allow = {"created_at", "updated_at", "severity", "status", "case_type", "title", "review_id"}
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
                "doctor_name": d.get("preferred_name") if d else None,
                "demo_score": c.get("demo_score"),
                "evidence_summary": c.get("evidence_summary"),
            })
        source_record = records.get(review.get("source_record_id") or "")
        doctor = doctors.get(review.get("doctor_id") or "")
        recommendation = self._recommendation_payload(state, review)

        comparison = {
            "source_profile": source_record,
            "doctor_profile": {
                "doctor_id": review.get("doctor_id"),
                "preferred_name": doctor.get("preferred_name") if doctor else None,
                "specialty": doctor.get("specialty") if doctor else None,
                "city": doctor.get("city") if doctor else None,
                "state": doctor.get("state") if doctor else None,
                "email": doctor.get("professional_email") if doctor else None,
            },
            "agreements": [],
            "conflicts": [],
        }
        if source_record and doctor:
            for field, left, right in [
                ("name", source_record.get("recorded_name"), doctor.get("preferred_name")),
                ("specialty", source_record.get("specialty"), doctor.get("specialty")),
                ("email", source_record.get("email"), doctor.get("professional_email")),
                ("state", source_record.get("state"), doctor.get("state")),
            ]:
                if left and right and str(left).lower() == str(right).lower():
                    comparison["agreements"].append({"field": field, "value": left})
                elif left and right:
                    comparison["conflicts"].append({"field": field, "source": left, "doctor": right})

        evidence_rows = []
        for evid in state["evidence"].values():
            if source_record and evid.get("source_record_id") == source_record.get("source_record_id"):
                evidence_rows.append(evid)
        for ref in recommendation.get("evidence_refs") or []:
            if ref in state["evidence"] and state["evidence"][ref] not in evidence_rows:
                evidence_rows.append(state["evidence"][ref])

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
            "label": "Prepared result",
            "origin": "prepared_demo",
            "summary": (
                "This case was supplied in the prepared demo dataset. "
                "It is not a live model recommendation and it is not an approved fact by itself."
            ),
            "proposed_field": review.get("proposed_field"),
            "proposed_value": review.get("proposed_value"),
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
                "actor_label": "Demo Steward",
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
