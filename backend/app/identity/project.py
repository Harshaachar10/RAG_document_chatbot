from __future__ import annotations

"""Project identity pipeline output into the runtime shapes used by existing API services."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.identity.briefs import attach_briefs
from app.identity.labels import review_question, source_label


ACTION_TO_CASE: Dict[str, str] = {
    "REVIEW": "probable_match",
    "COMPLIANCE_REVIEW": "compliance_review",
    "DEDUPE_REVIEW": "possible_duplicate",
    "ASSIGN_NPI": "npi_assignment",
    "NOT_A_PERSON": "not_a_person",
    "AUTO_LINK": "auto_link",
}

QUEUE_TO_CASE: Dict[str, str] = {
    "hard_stop": "identifier_conflict",
    "ambiguous_top": "same_name_ambiguity",
    "probable_match": "probable_match",
    "no_match": "unmatched",
    "low_score": "unmatched",
    "high_score_no_npi": "probable_match",
    "dedupe": "possible_duplicate",
    "compliance": "compliance_review",
    "data_quality": "not_a_person",
    "npi_assignment": "npi_assignment",
}


def _attr(golden: Dict[str, Any], key: str) -> Optional[str]:
    block = (golden.get("attributes") or {}).get(key) or {}
    val = block.get("value")
    return str(val) if val not in (None, "") else None


def _evidence_summary(golden: Dict[str, Any]) -> str:
    count = int(golden.get("member_count") or 0)
    sources = len(golden.get("sources") or [])
    npi = golden.get("npi") or "no NPI"
    return f"{count} linked records from {sources} sources. NPI {npi}."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_pipeline(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build RuntimeStore seed tables from pipeline result.
    Keys match CsvDemoRepository expectations.
    """
    records: List[Dict[str, Any]] = result.get("records") or []
    decisions: List[Dict[str, Any]] = result.get("decisions") or []
    goldens: List[Dict[str, Any]] = result.get("golden_records") or []
    sources_meta: List[Dict[str, Any]] = result.get("sources") or []
    notes: List[Dict[str, Any]] = result.get("notes") or []
    run_meta = result.get("run") or {}
    started = run_meta.get("started_at") or _now()

    by_uid = {r["uid"]: r for r in records}
    decision_by_uid = {d["uid"]: d for d in decisions}

    # --- sources ---
    sources_rows: List[Dict[str, Any]] = []
    for s in sources_meta:
        sources_rows.append(
            {
                "source_id": s["key"],
                "source_name": s.get("label") or s["key"],
                "source_type": s["key"],
                "description": s.get("filename") or "",
                "snapshot_version": "1",
                "updated_at": started,
                "row_count": s.get("row_count"),
                "filename": s.get("filename"),
                "trust": s.get("trust"),
                "headers": s.get("headers") or [],
                "flags": s.get("flags") or {},
            }
        )

    # --- doctors from golden records + provisional NPPES-only shells for candidates ---
    doctors: Dict[str, Dict[str, Any]] = {}
    affiliations: Dict[str, Dict[str, Any]] = {}
    aliases: Dict[str, Dict[str, Any]] = {}
    observations: Dict[str, Dict[str, Any]] = {}
    provenance: Dict[str, Dict[str, Any]] = {}
    events: Dict[str, Dict[str, Any]] = {}
    source_links: Dict[str, Dict[str, Any]] = {}
    source_records: Dict[str, Dict[str, Any]] = {}
    reviews: Dict[str, Dict[str, Any]] = {}
    review_candidates: List[Dict[str, Any]] = []
    evidence: Dict[str, Dict[str, Any]] = {}
    link_history: Dict[str, Dict[str, Any]] = {}
    constraints: Dict[str, Dict[str, Any]] = {}
    audit_events: Dict[str, Dict[str, Any]] = {}

    npi_to_doctor: Dict[str, str] = {}

    for g in goldens:
        did = g["golden_id"]
        npi = g.get("npi") or ""
        if npi:
            npi_to_doctor[npi] = did
        name = g.get("display_name") or "Unknown"
        parts = name.split()
        given = parts[0] if parts else ""
        family = parts[-1] if len(parts) > 1 else ""
        city = _attr(g, "city")
        state = _attr(g, "state")
        specialty = g.get("specialty") or _attr(g, "specialty")
        org = _attr(g, "organization")
        email = _attr(g, "email")
        phone = _attr(g, "phone")
        doctors[did] = {
            "doctor_id": did,
            "preferred_name": name,
            "given_name": given,
            "family_name": family,
            "specialty": specialty,
            "primary_affiliation_id": f"AFF-{did}" if org else None,
            "city": city,
            "state": state,
            "professional_email": email,
            "professional_phone": phone,
            "official_npi": npi or None,
            "npi_status": g.get("npi_status") or ("verified" if npi else "provisional"),
            "badge": "Deactivated" if g.get("deactivated") else ("Verified" if npi else "Provisional"),
            "master_id": did,
            "credential": ", ".join(g.get("credentials") or []) or None,
            "credentials": g.get("credentials") or [],
            "license_states": g.get("license_states") or [],
            "former_names": g.get("former_names") or [],
            "aliases_list": g.get("aliases") or [],
            "source_counts": g.get("source_counts") or {},
            "attributes": g.get("attributes") or {},
            "provisional": bool(g.get("provisional")),
            "mock_npi_ref": None,
            "identity_status": "resolved",
            "updated_at": g.get("updated_at") or started,
            "version": 1,
            "member_uids": g.get("member_uids") or [],
            "sources": g.get("sources") or [],
            "cluster_id": g.get("cluster_id"),
            "open_issue_count": 0,
            "known_values": (result.get("known_values") or {}).get(did) or [],
            "evidence_summary": _evidence_summary(g),
        }
        if org:
            affiliations[f"AFF-{did}"] = {
                "affiliation_id": f"AFF-{did}",
                "doctor_id": did,
                "organization_name": org,
                "address_line": _attr(g, "address"),
                "city": city,
                "state": state,
                "relationship_status": "active",
                "is_primary": True,
                "effective_from": None,
                "effective_to": None,
                "observed_at": started,
                "evidence_id": None,
            }
        # aliases from member display names
        seen_names = {name.lower()}
        for uid in g.get("member_uids") or []:
            rec = by_uid.get(uid)
            if not rec:
                continue
            disp = ((rec.get("standardized") or {}).get("name") or {}).get("display") or ""
            if disp and disp.lower() not in seen_names:
                seen_names.add(disp.lower())
                aid = f"AL-{did}-{len(aliases)+1}"
                aliases[aid] = {
                    "alias_id": aid,
                    "doctor_id": did,
                    "name": disp,
                    "alias_type": "source_variant",
                    "observation_date": started,
                    "evidence_id": None,
                }

        for idx, field in enumerate(["specialty", "city", "state", "phone", "email", "organization", "address"]):
            val = _attr(g, field if field != "organization" else "organization")
            if not val:
                continue
            oid = f"OBS-{did}-{field}"
            observations[oid] = {
                "observation_id": oid,
                "doctor_id": did,
                "source_record_id": None,
                "field_name": field,
                "observed_value": val,
                "effective_from": None,
                "effective_to": None,
                "recorded_at": started,
                "evidence_id": None,
            }
            pid = f"PROV-{did}-{field}"
            provenance[pid] = {
                "provenance_id": pid,
                "doctor_id": did,
                "field_name": field,
                "selected_value": val,
                "observation_id": oid,
                "selection_reason": "highest_trust_source",
                "review_id": None,
                "version": 1,
            }

        eid = f"EVT-{did}-formed"
        events[eid] = {
            "event_id": eid,
            "doctor_id": did,
            "event_type": "golden_record_formed",
            "title": "Golden record formed",
            "description": f"Clustered {g.get('member_count', 0)} source records"
            + (f" under NPI {npi}" if npi else ""),
            "previous_value": None,
            "new_value": name,
            "document_date": None,
            "submitted_at": None,
            "submitted_to": None,
            "effective_date": started[:10],
            "recorded_at": started,
            "review_status": "n/a",
            "evidence_id": None,
        }

    # Ensure doctor shells exist for NPPES targets referenced by open reviews
    for d in decisions:
        for cand in d.get("candidates") or []:
            tid = str(cand.get("target_id") or "")
            if tid.startswith("npi:"):
                npi = tid.split(":", 1)[1]
                if npi not in npi_to_doctor:
                    did = f"GR-{npi}"
                    npi_to_doctor[npi] = did
                    label = cand.get("target_label") or npi
                    parts = label.split()
                    doctors[did] = {
                        "doctor_id": did,
                        "preferred_name": label,
                        "given_name": parts[0] if parts else "",
                        "family_name": parts[-1] if len(parts) > 1 else "",
                        "specialty": None,
                        "primary_affiliation_id": None,
                        "city": None,
                        "state": None,
                        "professional_email": None,
                        "professional_phone": None,
                        "official_npi": npi,
                        "npi_status": "reference",
                        "mock_npi_ref": None,
                        "identity_status": "reference",
                        "updated_at": started,
                        "version": 1,
                        "member_uids": [],
                        "sources": ["nppes"],
                        "cluster_id": tid,
                    }

    # --- source records from all non-reference ingested rows (+ notes) ---
    for rec in records:
        if rec.get("is_reference"):
            continue
        uid = rec["uid"]
        std = rec.get("standardized") or {}
        name = (std.get("name") or {}).get("display") or ""
        primary_npi = next((nf["digits"] for nf in (rec.get("npi_fields") or []) if nf.get("valid")), None)
        if not primary_npi:
            primary_npi = next((nf.get("digits") for nf in (rec.get("npi_fields") or []) if nf.get("digits")), None)
        decision = decision_by_uid.get(uid) or rec.get("decision") or {}
        action = decision.get("action")
        resolution = {
            "AUTO_LINK": "linked",
            "NOT_A_PERSON": "rejected",
            "COMPLIANCE_REVIEW": "pending_review",
            "REVIEW": "pending_review",
            "DEDUPE_REVIEW": "pending_review",
            "ASSIGN_NPI": "pending_review",
        }.get(action or "", "unresolved" if not rec.get("exclude_from_matching") else "informational")

        kind_map = {
            "notes": "note_observation",
            "payments": "supporting_transaction",
            "claims": "supporting_transaction",
            "events": "supporting_transaction",
            "legacy_master": "identity_entry",
            "crm": "identity_entry",
            "hub": "identity_entry",
        }
        source_records[uid] = {
            "source_record_id": uid,
            "source_id": rec.get("source_key"),
            "record_kind": kind_map.get(rec.get("source_key") or "", rec.get("source_key")),
            "recorded_name": name,
            "specialty": std.get("specialty"),
            "practice_name": std.get("organization"),
            "address_line": std.get("address"),
            "city": std.get("city") or std.get("venue_city"),
            "state": std.get("state") or std.get("venue_state"),
            "postal_code": std.get("postal"),
            "email": std.get("email"),
            "phone": std.get("phone"),
            "credential_reference": ",".join((std.get("name") or {}).get("credentials") or []),
            "provider_identifier": primary_npi,
            "identifier_kind": "npi" if primary_npi else None,
            "document_id": None,
            "record_date": std.get("record_date"),
            "submitted_at": std.get("record_date"),
            "submitted_by": None,
            "submitted_to": None,
            "ingested_at": started,
            "resolution_status": resolution,
            "amount_cents": None,
            "currency": None,
            "prescription_count": None,
            "original_transaction_id": rec.get("record_id"),
            "note_text": rec.get("redacted_note") or std.get("note_text") or "",
            "duplicate_of_record_id": None,
            "raw": rec.get("raw") or {},
            "standardized": std,
            "npi_fields": rec.get("npi_fields") or [],
            "npi_lookups": rec.get("npi_lookups") or [],
            "record_flags": rec.get("record_flags") or [],
            "trust": rec.get("trust"),
            "exclude_from_matching": rec.get("exclude_from_matching"),
        }

        # evidence row per record
        evid = f"EV-{uid}"
        evidence[evid] = {
            "evidence_id": evid,
            "evidence_type": "source_record",
            "title": f"{rec.get('source_label')}: {rec.get('record_id')}",
            "summary": name,
            "source_record_id": uid,
            "document_id": None,
            "doctor_id": None,
            "created_at": started,
        }

    # payment amounts
    for uid, sr in source_records.items():
        raw = sr.get("raw") or {}
        if "amount_usd" in raw:
            try:
                sr["amount_cents"] = int(round(float(raw["amount_usd"]) * 100))
                sr["currency"] = "USD"
            except (TypeError, ValueError):
                pass

    # --- links for AUTO_LINK ---
    link_i = 0
    for d in decisions:
        if d.get("action") not in {"AUTO_LINK", "PROVISIONAL", "DEDUPE"}:
            continue
        target = d.get("target_id") or ""
        doctor_id = None
        if str(target).startswith("npi:"):
            npi = str(target).split(":", 1)[1]
            doctor_id = npi_to_doctor.get(npi) or f"GR-{npi}"
        elif str(target) in doctors:
            doctor_id = str(target)
        else:
            # target may be another source uid already in a golden
            for g in goldens:
                if d["uid"] in (g.get("member_uids") or []):
                    doctor_id = g["golden_id"]
                    break
        if not doctor_id:
            continue
        link_i += 1
        lid = f"LNK-{link_i:04d}"
        source_links[lid] = {
            "link_id": lid,
            "source_record_id": d["uid"],
            "doctor_id": doctor_id,
            "link_status": "provisional" if d.get("action") == "PROVISIONAL" else "auto_linked",
            "decision_basis": d.get("reason") or "AUTO_LINK",
            "demo_score": d.get("score"),
            "review_id": None,
        }
        # attach evidence to doctor
        evid = f"EV-{d['uid']}"
        if evid in evidence:
            evidence[evid]["doctor_id"] = doctor_id

        hid = f"LH-{lid}"
        link_history[hid] = {
            "change_id": hid,
            "doctor_id": doctor_id,
            "source_record_id": d["uid"],
            "change_type": "auto_link",
            "previous_status": "unlinked",
            "new_status": "auto_linked",
            "score": d.get("score"),
            "reason": d.get("reason"),
            "changed_at": started,
            "changed_by": "pipeline",
        }

        if doctor_id in doctors:
            doctors[doctor_id]["identity_status"] = "resolved"

    # --- reviews for open decisions ---
    for d in decisions:
        if d.get("status") != "open" and d.get("action") not in {
            "REVIEW",
            "COMPLIANCE_REVIEW",
            "DEDUPE_REVIEW",
            "ASSIGN_NPI",
        }:
            # still create closed review artifact for NOT_A_PERSON? skip
            if d.get("action") != "NOT_A_PERSON":
                continue
            # closed quality item
            rid = f"REV-{d['uid']}"
            reviews[rid] = {
                "review_id": rid,
                "doctor_id": None,
                "case_type": "not_a_person",
                "title": f"Non-person record: {d.get('display_name') or d.get('record_id')}",
                "severity": "low",
                "status": "resolved",
                "source_record_id": d["uid"],
                "candidate_doctor_id": None,
                "proposed_field": None,
                "proposed_value": None,
                "recommendation_id": None,
                "created_at": started,
                "updated_at": started,
                "version": 1,
                "assigned_reviewer": None,
                "assignment_status": "unassigned",
                "pipeline_action": d.get("action"),
                "pipeline_reason": d.get("reason"),
                "pipeline_score": d.get("score"),
                "queue": d.get("queue"),
                "match_explanation": d.get("candidates") or [],
                "record_flags": d.get("record_flags") or [],
            }
            continue

        rid = f"REV-{d['uid']}"
        case = QUEUE_TO_CASE.get(d.get("queue") or "", ACTION_TO_CASE.get(d.get("action") or "", "probable_match"))
        severity = "high" if d.get("action") in {"COMPLIANCE_REVIEW", "DEDUPE_REVIEW"} or (d.get("queue") == "hard_stop") else "medium"
        if d.get("action") == "ASSIGN_NPI":
            severity = "low"

        # best candidate doctor
        cand_doctor = None
        target = d.get("target_id")
        if target and str(target).startswith("npi:"):
            cand_doctor = npi_to_doctor.get(str(target).split(":", 1)[1])
        elif target and str(target) in doctors:
            cand_doctor = str(target)

        title_name = d.get("display_name") or d.get("record_id")
        cand_name = None
        if cand_doctor and cand_doctor in doctors:
            cand_name = doctors[cand_doctor].get("preferred_name")
        elif d.get("candidates"):
            cand_name = (d["candidates"][0] or {}).get("target_label")
        question = review_question(
            source_key=d.get("source_key"),
            display_name=title_name,
            candidate_name=cand_name,
            action=d.get("action"),
            case_type=case,
        )
        reviews[rid] = {
            "review_id": rid,
            "doctor_id": cand_doctor,
            "case_type": case,
            "title": question,
            "severity": severity,
            "status": "pending",
            "source_record_id": d["uid"],
            "record_id": d.get("record_id"),
            "candidate_doctor_id": cand_doctor,
            "proposed_field": "npi_link" if cand_doctor else None,
            "proposed_value": target,
            "recommendation_id": None,
            "created_at": started,
            "updated_at": started,
            "version": 1,
            "assigned_reviewer": None,
            "assignment_status": "unassigned",
            "pipeline_action": d.get("action"),
            "pipeline_reason": d.get("reason"),
            "pipeline_score": d.get("score"),
            "queue": d.get("queue"),
            "match_explanation": d.get("candidates") or [],
            "record_flags": d.get("record_flags") or [],
            "npi_lookups": d.get("npi_lookups") or [],
            "recommended_action": d.get("action"),
            "match_score": d.get("score"),
            "source_key": d.get("source_key"),
            "source_label": source_label(d.get("source_key")),
            "risk_tier": 0 if d.get("action") == "COMPLIANCE_REVIEW" else (1 if severity == "high" else 2),
        }

        for i, cand in enumerate(d.get("candidates") or []):
            tid = str(cand.get("target_id") or "")
            cdoc = None
            if tid.startswith("npi:"):
                cdoc = npi_to_doctor.get(tid.split(":", 1)[1])
            elif tid in doctors:
                cdoc = tid
            review_candidates.append(
                {
                    "review_id": rid,
                    "candidate_doctor_id": cdoc or tid,
                    "rank": i + 1,
                    "score": cand.get("score"),
                    "rationale": ", ".join(cand.get("name_reasons") or []) or cand.get("target_label"),
                    "hard_stops": cand.get("hard_stops") or [],
                    "contributions": cand.get("contributions") or [],
                    "target_id": tid,
                    "target_label": cand.get("target_label"),
                    "target_source": cand.get("target_source"),
                }
            )

        # hard-stop constraints
        for hs in (d.get("candidates") or [{}])[0].get("hard_stops") or []:
            cid = f"CON-{d['uid']}-{hs.get('code')}"
            constraints[cid] = {
                "constraint_id": cid,
                "doctor_id": cand_doctor,
                "source_record_id": d["uid"],
                "constraint_type": hs.get("code"),
                "message": hs.get("message"),
                "status": "active",
                "created_at": started,
            }

    # notes as evidence-only records already in source_records
    for note in notes:
        uid = note["uid"]
        if uid in source_records:
            source_records[uid]["note_text"] = note.get("redacted_note") or source_records[uid].get("note_text") or ""

    # Open issue counts on golden doctors
    for review in reviews.values():
        if review.get("status") != "pending":
            continue
        did = review.get("doctor_id") or review.get("candidate_doctor_id")
        if did and did in doctors:
            doctors[did]["open_issue_count"] = int(doctors[did].get("open_issue_count") or 0) + 1

    # License states from golden attributes / members
    for did, doc in doctors.items():
        states_set = set()
        if doc.get("state"):
            states_set.add(doc["state"])
        for uid in doc.get("member_uids") or []:
            rec = by_uid.get(uid)
            if not rec:
                continue
            st = (rec.get("standardized") or {}).get("license_state") or (rec.get("standardized") or {}).get("state")
            if st:
                states_set.add(st)
            creds = ((rec.get("standardized") or {}).get("name") or {}).get("credentials") or []
            if creds and not doc.get("credential"):
                doc["credential"] = ",".join(creds)
        doc["license_states"] = sorted(states_set)

    safety_alarms = attach_briefs(doctors, decisions)

    audit_events["AUD-pipeline"] = {
        "audit_id": "AUD-pipeline",
        "actor": "identity_pipeline",
        "action": "pipeline_run",
        "entity_type": "run",
        "entity_id": started,
        "detail": f"decisions={len(decisions)} goldens={len(goldens)}",
        "created_at": started,
    }

    return {
        "snapshot_version": 1,
        "dataset_directory": run_meta.get("data_dir"),
        "pipeline_run": run_meta,
        "pipeline_counts": result.get("counts") or {},
        "pipeline_metrics": result.get("metrics") or {},
        "lineage_events": result.get("lineage") or [],
        "match_decisions": [
            {
                "record_id": d.get("record_id"),
                "uid": d.get("uid"),
                "source_key": d.get("source_key"),
                "stated_npi": d.get("stated_npi") or "",
                "display_name": d.get("display_name"),
                "action": d.get("action"),
                "outcome": d.get("outcome"),
                "npi_status": d.get("npi_status"),
                "target_id": d.get("target_id"),
                "target_npi": d.get("target_npi"),
                "target_label": d.get("target_label"),
                "score": d.get("score"),
                "margin": d.get("margin"),
                "reason": d.get("reason"),
                "hard_stops": d.get("hard_stops") or [],
                "contributions": d.get("contributions") or [],
                "proposed_changes": d.get("proposed_changes") or [],
                "safety": d.get("safety") or {},
                "round": d.get("round"),
                "found_by": d.get("found_by") or [],
                "route": d.get("route") or "",
                "learned_value": bool(d.get("learned_value")),
                "search_plan": d.get("search_plan"),
                "splink_score": d.get("splink_score"),
                "splink_levels": d.get("splink_levels") or [],
            }
            for d in decisions
        ],
        "known_values": result.get("known_values") or {},
        "cleanup_rounds": result.get("rounds") or [],
        "source_profiles": result.get("profiles") or [],
        "embedding_status": result.get("embedding") or {},
        "search_quality": (result.get("metrics") or {}).get("search") or {},
        "safety_alarms": safety_alarms,
        "doctors": doctors,
        "affiliations": affiliations,
        "aliases": aliases,
        "source_records": source_records,
        "source_links": source_links,
        "reviews": reviews,
        "review_candidates": review_candidates,
        "events": events,
        "observations": observations,
        "field_provenance": provenance,
        "audit_events": audit_events,
        "evidence": evidence,
        "link_history": link_history,
        "identity_constraints": constraints,
        "sources_meta": sources_rows,
        "notes": notes,
        "idempotency": {},
        "demo_runs": [],
        "upload_batches": [],
        "upload_rollbacks": {},
        "decision_log": [],
        "ai_jobs": {},
        "ai_analyses": {},
        "ai_cache": {},
        "documents": [],
        "document_content": [],
    }
