from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import NotFoundError, ValidationAppError
from app.repositories.csv_repository import CsvDemoRepository
from app.services.filtering import matches_search, paginate, sort_items
from app.utils.links import display_npi_status, is_linked_status


class DoctorService:
    def __init__(self, repo: CsvDemoRepository, resolution: Any = None) -> None:
        self.repo = repo
        self.resolution = resolution

    def _links_by_doctor(self) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        for link in self.repo.list_links():
            did = link.get("doctor_id")
            if not did:
                continue
            out.setdefault(did, []).append(link)
        return out

    def _doctor_ids_for_source(self, source_id: str) -> Set[str]:
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        ids: Set[str] = set()
        for link in self.repo.list_links():
            if not link.get("doctor_id"):
                continue
            rec = records.get(link.get("source_record_id"))
            if rec and rec.get("source_id") == source_id:
                ids.add(link["doctor_id"])
        return ids

    def _pending_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for review in self.repo.list_reviews():
            if review.get("status") != "pending":
                continue
            did = review.get("doctor_id")
            if did:
                counts[did] = counts.get(did, 0) + 1
        return counts

    def list_doctors(
        self,
        *,
        search: Optional[str] = None,
        specialty: Optional[str] = None,
        state: Optional[str] = None,
        affiliation: Optional[str] = None,
        source_id: Optional[str] = None,
        pending_review: Optional[bool] = None,
        missing_core: Optional[bool] = None,
        sort_by: str = "preferred_name",
        sort_direction: str = "asc",
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        if page < 1:
            raise ValidationAppError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValidationAppError("page_size must be between 1 and 100")

        aliases = self.repo.list_aliases()
        alias_map: Dict[str, List[str]] = {}
        for a in aliases:
            alias_map.setdefault(a["doctor_id"], []).append(a.get("name") or "")

        links_by_doctor = self._links_by_doctor()
        pending = self._pending_counts()
        source_doctor_ids = self._doctor_ids_for_source(source_id) if source_id else None
        affiliations = self.repo.list_affiliations()
        aff_by_doctor: Dict[str, List[Dict[str, Any]]] = {}
        for aff in affiliations:
            aff_by_doctor.setdefault(aff["doctor_id"], []).append(aff)

        items: List[Dict[str, Any]] = []
        for doctor in self.repo.list_doctors():
            did = doctor["doctor_id"]
            if specialty and doctor.get("specialty") != specialty:
                continue
            if state and doctor.get("state") != state:
                continue
            if source_doctor_ids is not None and did not in source_doctor_ids:
                continue
            affs = aff_by_doctor.get(did, [])
            if affiliation:
                if not any(affiliation.lower() in (a.get("organization_name") or "").lower() for a in affs):
                    continue
            pend = pending.get(did, 0)
            if pending_review is True and pend == 0:
                continue
            if pending_review is False and pend > 0:
                continue
            if missing_core:
                missing = not doctor.get("specialty") or not doctor.get("city") or not doctor.get("professional_email")
                if not missing:
                    continue

            search_blob = " ".join(
                [
                    doctor.get("preferred_name") or "",
                    doctor.get("doctor_id") or "",
                    " ".join(alias_map.get(did, [])),
                ]
            )
            if search and not matches_search(search_blob, search):
                continue

            primary = next((a for a in affs if a.get("is_primary")), affs[0] if affs else None)
            accepted = [l for l in links_by_doctor.get(did, []) if is_linked_status(l.get("link_status"))]
            items.append({
                "doctor_id": did,
                "preferred_name": doctor.get("preferred_name"),
                "specialty": doctor.get("specialty"),
                "primary_affiliation": primary.get("organization_name") if primary else None,
                "affiliation_count": len([a for a in affs if a.get("relationship_status") in {"current", "proposed", "historical_observation", "previous"}]),
                "city": doctor.get("city"),
                "state": doctor.get("state"),
                "linked_record_count": len(accepted),
                "pending_item_count": pend,
                "identity_status": doctor.get("identity_status"),
                "updated_at": doctor.get("updated_at"),
                "npi_status": display_npi_status(doctor.get("npi_status")),
            })

        allow = {
            "preferred_name", "doctor_id", "specialty", "state", "updated_at",
            "linked_record_count", "pending_item_count", "primary_affiliation",
        }
        items = sort_items(items, sort_by, sort_direction, allow, "doctor_id")
        page_items, total = paginate(items, page, page_size)
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "applied_filters": {
                "search": search,
                "specialty": specialty,
                "state": state,
                "affiliation": affiliation,
                "source_id": source_id,
                "pending_review": pending_review,
                "missing_core": missing_core,
                "sort_by": sort_by,
                "sort_direction": sort_direction,
            },
            "snapshot_version": self.repo.snapshot_version(),
        }

    def get_doctor(self, doctor_id: str) -> Dict[str, Any]:
        doctor = self.repo.get_doctor(doctor_id)
        if not doctor:
            raise NotFoundError(f"Doctor {doctor_id} not found")
        aliases = self.repo.list_aliases(doctor_id)
        affiliations = self.repo.list_affiliations(doctor_id)
        links = [l for l in self.repo.list_links() if l.get("doctor_id") == doctor_id and is_linked_status(l.get("link_status"))]
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        source_ids = {
            records[l["source_record_id"]]["source_id"]
            for l in links
            if l.get("source_record_id") in records
        }
        pending_reviews = [
            r for r in self.repo.list_reviews()
            if r.get("doctor_id") == doctor_id and r.get("status") == "pending"
        ]
        identity_reviews = [r for r in pending_reviews if r.get("case_type") in {
            "possible_duplicate", "same_name_ambiguity", "identifier_conflict"
        }]
        field_updates = [r for r in pending_reviews if r.get("case_type") in {
            "name_update", "address_update", "affiliation_update", "contact_update"
        }]
        primary = next((a for a in affiliations if a.get("is_primary")), None)
        sources = {s["source_id"]: s for s in self.repo.list_sources()}
        coverage = [
            {"source_id": sid, "source_name": sources.get(sid, {}).get("source_name", sid)}
            for sid in sorted(source_ids)
        ]
        pending_updates = []
        for rev in field_updates:
            pending_updates.append({
                "review_id": rev["review_id"],
                "field": rev.get("proposed_field"),
                "proposed_value": rev.get("proposed_value"),
                "before_value": primary.get("organization_name") if rev.get("proposed_field") == "primary_affiliation" and primary else doctor.get("preferred_name"),
                "case_type": rev.get("case_type"),
                "evidence_hint": rev.get("source_record_id"),
            })
        previous_names = [a["name"] for a in aliases if a.get("alias_type") == "previous_name"]
        return {
            "doctor_id": doctor_id,
            "preferred_name": doctor.get("preferred_name"),
            "given_name": doctor.get("given_name"),
            "family_name": doctor.get("family_name"),
            "specialty": doctor.get("specialty"),
            "city": doctor.get("city"),
            "state": doctor.get("state"),
            "professional_email": doctor.get("professional_email"),
            "professional_phone": doctor.get("professional_phone"),
            "official_npi": doctor.get("official_npi"),
            "npi_status": display_npi_status(doctor.get("npi_status")),
            "mock_npi_ref": doctor.get("mock_npi_ref"),
            "data_classification": "synthetic",
            "identity_status": doctor.get("identity_status"),
            "identity_review_status": "pending" if identity_reviews else "clear",
            "pending_field_changes": len(field_updates),
            "linked_record_count": len(links),
            "source_count": len(source_ids),
            "aliases": aliases,
            "primary_affiliation": primary,
            "affiliations": affiliations,
            "previous_names": previous_names,
            "pending_updates": pending_updates,
            "source_coverage": coverage,
            "credential_details": self._credential_for(doctor_id),
            "updated_at": doctor.get("updated_at"),
            "version": int(doctor.get("version") or 1),
        }

    def _credential_for(self, doctor_id: str) -> Optional[str]:
        links = [l for l in self.repo.list_links() if l.get("doctor_id") == doctor_id]
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        for link in links:
            rec = records.get(link.get("source_record_id"))
            if rec and rec.get("credential_reference"):
                return rec["credential_reference"]
        return None

    def list_source_records(self, doctor_id: str) -> Dict[str, Any]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        links = {l["source_record_id"]: l for l in self.repo.list_links() if l.get("doctor_id") == doctor_id}
        sources = {s["source_id"]: s for s in self.repo.list_sources()}
        evidence = self.repo.list_evidence()
        items = []
        for rec in self.repo.list_source_records():
            link = links.get(rec["source_record_id"])
            if not link:
                continue
            evid_ids = [e["evidence_id"] for e in evidence if e.get("source_record_id") == rec["source_record_id"]]
            items.append({
                **rec,
                "source_name": sources.get(rec.get("source_id"), {}).get("source_name"),
                "link_status": link.get("link_status"),
                "doctor_id": doctor_id,
                "evidence_ids": evid_ids,
                "normalized": {
                    "recorded_name": rec.get("recorded_name"),
                    "practice_name": rec.get("practice_name"),
                    "email": rec.get("email"),
                },
                "linkage_explanation": link.get("decision_basis"),
                "submitted_by": rec.get("submitted_by") or "Not recorded",
                "submitted_to": rec.get("submitted_to") or "Not recorded",
            })
        items.sort(key=lambda r: (r.get("record_date") or "", r["source_record_id"]), reverse=True)
        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "page_size": len(items) or 25,
            "applied_filters": {"doctor_id": doctor_id},
            "snapshot_version": self.repo.snapshot_version(),
        }

    def list_aliases(self, doctor_id: str) -> List[Dict[str, Any]]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        return self.repo.list_aliases(doctor_id)

    def list_affiliations(self, doctor_id: str) -> List[Dict[str, Any]]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        return self.repo.list_affiliations(doctor_id)

    def history(
        self,
        doctor_id: str,
        *,
        event_type: Optional[str] = None,
        field: Optional[str] = None,
        sort_direction: str = "desc",
    ) -> Dict[str, Any]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        evidence = {e["evidence_id"]: e for e in self.repo.list_evidence()}
        sources = {s["source_id"]: s for s in self.repo.list_sources()}
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        items = []
        for event in self.repo.list_events(doctor_id):
            if event_type and event_type != "all":
                mapping = {
                    "names": {"name_variation_observed", "name_change_documented", "name_update"},
                    "addresses": {"address_update", "address_observed"},
                    "affiliations": {"affiliation_observed", "affiliation_effective", "affiliation_update"},
                    "record_entries": {"record_entry"},
                    "review_decisions": {"review_decision", "preferred_name_approved"},
                }
                allowed = mapping.get(event_type)
                if allowed and event.get("event_type") not in allowed:
                    continue
            if field:
                blob = " ".join([
                    event.get("title") or "",
                    event.get("description") or "",
                    event.get("previous_value") or "",
                    event.get("new_value") or "",
                    event.get("event_type") or "",
                ]).lower()
                if field.lower() not in blob and field.lower() not in (event.get("event_type") or "").lower():
                    # also match affiliation/name fields loosely
                    if field == "preferred_name" and "name" not in (event.get("event_type") or ""):
                        continue
                    if field == "primary_affiliation" and "affiliation" not in (event.get("event_type") or ""):
                        continue
            evid = evidence.get(event.get("evidence_id") or "")
            source_type = None
            if evid and evid.get("source_record_id"):
                rec = records.get(evid["source_record_id"])
                if rec:
                    source_type = sources.get(rec.get("source_id"), {}).get("source_type")
            date_label = event.get("effective_date") or event.get("document_date") or event.get("recorded_at")
            if event.get("effective_date"):
                date_meaning = "effective_date"
            elif event.get("document_date"):
                date_meaning = "document_date"
            else:
                date_meaning = "recorded_at"
            items.append({
                **event,
                "date_label": date_label,
                "date_meaning": date_meaning,
                "source_type": source_type,
                "actor": None,
                "reason": event.get("description"),
                "evidence_quotation": evid.get("quoted_text") if evid else None,
            })
        reverse = (sort_direction or "desc").lower() != "asc"
        items.sort(key=lambda e: (e.get("date_label") or "", e["event_id"]), reverse=reverse)
        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "page_size": len(items) or 25,
            "applied_filters": {"doctor_id": doctor_id, "event_type": event_type, "field": field},
            "snapshot_version": self.repo.snapshot_version(),
        }

    def provenance(self, doctor_id: str) -> Dict[str, Any]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        observations = {o["observation_id"]: o for o in self.repo.list_observations(doctor_id)}
        items = []
        for row in self.repo.list_provenance(doctor_id):
            obs = observations.get(row.get("observation_id") or "")
            evid_ids = list(row.get("evidence_ids") or [])
            if obs and obs.get("evidence_id") and obs["evidence_id"] not in evid_ids:
                evid_ids.append(obs["evidence_id"])
            items.append({**row, "evidence_ids": evid_ids})
        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "page_size": len(items) or 25,
            "applied_filters": {"doctor_id": doctor_id},
            "snapshot_version": self.repo.snapshot_version(),
        }

    def match_explanation(self, doctor_id: str) -> Dict[str, Any]:
        """Prepared linkage narrative. This does not call a model and is not an identity validation."""
        doctor = self.repo.get_doctor(doctor_id)
        if not doctor:
            raise NotFoundError(f"Doctor {doctor_id} not found")
        records = {r["source_record_id"]: r for r in self.repo.list_source_records()}
        links = [
            link for link in self.repo.list_links()
            if link.get("doctor_id") == doctor_id and is_linked_status(link.get("link_status"))
        ]
        side_by_side = []
        for link in sorted(links, key=lambda item: item.get("source_record_id") or "")[:6]:
            rec = records.get(link.get("source_record_id") or "")
            if not rec:
                continue
            side_by_side.append({
                "source_record_id": rec.get("source_record_id"),
                "recorded_name": rec.get("recorded_name"),
                "credential_reference": rec.get("credential_reference"),
                "email": rec.get("email"),
                "city": rec.get("city"),
                "state": rec.get("state"),
                "practice_name": rec.get("practice_name"),
            })
        constraints = []
        for constraint in self.repo.list_constraints():
            if doctor_id in {constraint.get("left_doctor_id"), constraint.get("right_doctor_id")}:
                constraints.append(constraint.get("basis") or constraint.get("constraint_id"))
        pending = [
            r.get("title") for r in self.repo.list_reviews()
            if r.get("doctor_id") == doctor_id and r.get("status") == "pending"
        ]
        summary = (
            f"Prepared demo linkage for {doctor.get('preferred_name')}. "
            f"{len(links)} source records are already associated with {doctor_id} in the supplied dataset. "
            "This view is not an independent AI identity validation."
        )
        return {
            "doctor_id": doctor_id,
            "label": "Prepared result",
            "summary": summary,
            "simulated_recommendation": "Prepared result. These links were supplied with the dataset and were not generated by the live model.",
            "demo_match_score": None,
            "decision_method": "prepared_demo",
            "review_status": "pending" if pending else "clear",
            "ambiguities": pending,
            "constraints": constraints,
            "side_by_side": side_by_side,
            "evidence_rows": [],
        }

    def review_history(self, doctor_id: str) -> Dict[str, Any]:
        if not self.repo.get_doctor(doctor_id):
            raise NotFoundError(f"Doctor {doctor_id} not found")
        items = []
        for audit in self.repo.list_audit():
            if audit.get("doctor_id") != doctor_id:
                continue
            items.append({
                **audit,
                "changed_fields": [],
                "reason": audit.get("summary"),
                "before_after": {},
                "evidence_refs": [],
            })
        items.sort(key=lambda a: a.get("occurred_at") or "", reverse=True)
        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "page_size": len(items) or 25,
            "applied_filters": {"doctor_id": doctor_id},
            "snapshot_version": self.repo.snapshot_version(),
        }
