"""Build model inputs from selected source evidence.

evaluation_only/, prepared link assignments, and review recommendations are not included
in fresh duplicate-resolution or change-extraction requests.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


RECORD_FIELDS = (
    "source_record_id", "source_id", "record_kind", "recorded_name", "specialty",
    "practice_name", "address_line", "city", "state", "postal_code", "email", "phone",
    "credential_reference", "provider_identifier", "identifier_kind", "record_date",
    "submitted_at", "note_text",
)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class EvidencePack:
    operation: str
    user_text: str
    allowed_evidence_ids: List[str]
    known_dates: List[str]
    text_blob: str
    fingerprint: str
    source_record_ids: List[str]
    evidence_display: List[Dict[str, Any]] = field(default_factory=list)
    narrowing: Optional[Dict[str, Any]] = None
    doctor_revision: Optional[str] = None
    allowed_names: List[str] = field(default_factory=list)
    pending_proposals: List[str] = field(default_factory=list)


def build_identity_pack(
    repo: Any,
    record_ids: Sequence[str],
    *,
    prompt_digest: str,
    deployment: str,
    max_records: int,
    max_evidence: int,
) -> EvidencePack:
    records = [_require_records(repo, record_ids)]
    flat = records[0]
    if len(flat) > max_records:
        return _narrowing(
            "identity_analysis",
            flat,
            reason=(
                f"{len(flat)} records were selected. Fresh analysis accepts at most {max_records} "
                "records so contradictory evidence is not dropped."
            ),
            groups=_block_groups(flat),
            prompt_digest=prompt_digest,
            deployment=deployment,
        )
    evidence = _evidence_for(repo, [r["source_record_id"] for r in flat])
    if len(evidence) > max_evidence:
        return _narrowing(
            "identity_analysis",
            flat,
            reason=(
                f"The selection has {len(evidence)} evidence rows, above the limit of {max_evidence}. "
                "Narrow the selection. Evidence was not truncated."
            ),
            groups=_block_groups(flat),
            prompt_digest=prompt_digest,
            deployment=deployment,
        )
    constraints = _constraints_for_records(repo, {r["source_record_id"] for r in flat})
    passages = _passages(repo, evidence)
    payload = {
        "task": "Compare these source records. Decide whether they support one doctor.",
        "records": [_public_record(r) for r in flat],
        "evidence": [_public_evidence(e) for e in evidence],
        "document_passages": passages,
        "verified_constraints": constraints,
    }
    return _pack("identity_analysis", payload, evidence, flat, prompt_digest, deployment)


def build_change_pack(
    repo: Any,
    record_ids: Sequence[str],
    *,
    prompt_digest: str,
    deployment: str,
    max_records: int,
    max_evidence: int,
) -> EvidencePack:
    flat = _require_records(repo, record_ids)
    evidence = _evidence_for(repo, [r["source_record_id"] for r in flat])
    if len(flat) > max_records or len(evidence) > max_evidence:
        return _narrowing(
            "change_extraction",
            flat,
            reason=(
                "The selection is larger than the evidence limit. "
                "Narrow it before extracting changes. No evidence was truncated."
            ),
            groups=_block_groups(flat),
            prompt_digest=prompt_digest,
            deployment=deployment,
        )
    payload = {
        "task": "Extract proposed changes from these source records and their evidence.",
        "records": [_public_record(r) for r in flat],
        "evidence": [_public_evidence(e) for e in evidence],
        "document_passages": _passages(repo, evidence),
    }
    return _pack("change_extraction", payload, evidence, flat, prompt_digest, deployment)


def build_summary_pack(
    repo: Any,
    doctor_id: str,
    *,
    prompt_digest: str,
    deployment: str,
) -> EvidencePack:
    doctor = repo.get_doctor(doctor_id)
    if not doctor:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Doctor {doctor_id} not found")
    aliases = repo.list_aliases(doctor_id)
    affiliations = repo.list_affiliations(doctor_id)
    provenance = repo.list_provenance(doctor_id)
    pending = [
        {
            "review_id": review.get("review_id"),
            "case_type": review.get("case_type"),
            "proposed_field": review.get("proposed_field"),
            "proposed_value": review.get("proposed_value"),
            "status": "pending",
            "note": "Pending proposal. Not an accepted fact.",
        }
        for review in repo.list_reviews()
        if review.get("doctor_id") == doctor_id and review.get("status") == "pending"
    ]
    observations = {o["observation_id"]: o for o in repo.list_observations(doctor_id)}
    evidence_rows = []
    evidence_ids: List[str] = []
    for row in provenance:
        obs = observations.get(row.get("observation_id") or "")
        if obs and obs.get("evidence_id"):
            evid = repo.get_evidence(obs["evidence_id"])
            if evid:
                evidence_rows.append(evid)
                evidence_ids.append(evid["evidence_id"])
    for alias in aliases:
        if alias.get("evidence_id"):
            evid = repo.get_evidence(alias["evidence_id"])
            if evid and evid["evidence_id"] not in evidence_ids:
                evidence_rows.append(evid)
                evidence_ids.append(evid["evidence_id"])
    accepted = {
        "doctor_id": doctor.get("doctor_id"),
        "preferred_name": doctor.get("preferred_name"),
        "specialty": doctor.get("specialty"),
        "city": doctor.get("city"),
        "state": doctor.get("state"),
        "professional_email": doctor.get("professional_email"),
        "professional_phone": doctor.get("professional_phone"),
        "official_npi": doctor.get("official_npi"),
        "npi_status": doctor.get("npi_status"),
        "mock_npi_ref": doctor.get("mock_npi_ref"),
        "mock_npi_note": "Fictional source label, not an official NPI, and not registry-checked.",
        "version": doctor.get("version"),
        "aliases": [
            {"name": a.get("name"), "alias_type": a.get("alias_type"), "evidence_id": a.get("evidence_id")}
            for a in aliases
        ],
        "affiliations": [
            {
                "organization_name": a.get("organization_name"),
                "relationship_status": a.get("relationship_status"),
                "is_primary": a.get("is_primary"),
                "effective_from": a.get("effective_from"),
                "effective_to": a.get("effective_to"),
                "evidence_id": a.get("evidence_id"),
            }
            for a in affiliations
        ],
        "provenance": [
            {
                "field_name": row.get("field_name"),
                "selected_value": row.get("selected_value"),
                "selection_reason": row.get("selection_reason"),
            }
            for row in provenance
        ],
    }
    omitted = 0
    if len(evidence_rows) > 40:
        omitted = len(evidence_rows) - 40
        evidence_rows = evidence_rows[:40]
    payload = {
        "task": "Summarize this accepted doctor profile. Do not treat pending proposals as approved facts.",
        "accepted_profile": accepted,
        "pending_proposals": pending,
        "evidence": [_public_evidence(e) for e in evidence_rows],
        "omitted_evidence_count": omitted,
        "omission_note": (
            None if omitted == 0 else
            "Additional accepted evidence rows exist and were not included. Do not invent them."
        ),
    }
    pack = _pack(
        "profile_summary",
        payload,
        evidence_rows,
        [],
        prompt_digest,
        deployment,
        doctor_revision=f"{doctor_id}:{doctor.get('version')}:{len(pending)}",
    )
    pack.source_record_ids = sorted({
        str(obs.get("source_record_id"))
        for obs in observations.values()
        if obs.get("source_record_id")
    })
    pack.allowed_names = [a.get("name") for a in aliases if a.get("name")]
    pack.pending_proposals = [
        f"{item.get('proposed_field')}: {item.get('proposed_value')}"
        for item in pending
        if item.get("proposed_value")
    ]
    pack.fingerprint = _fingerprint(pack.operation, payload, prompt_digest, deployment, pack.doctor_revision)
    return pack


def build_review_pack(
    repo: Any,
    review_id: str,
    *,
    prompt_digest: str,
    deployment: str,
    max_evidence: int,
) -> EvidencePack:
    review = repo.get_review(review_id)
    if not review:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Review {review_id} not found")
    record_ids = [review["source_record_id"]] if review.get("source_record_id") else []
    records = _require_records(repo, record_ids) if record_ids else []
    evidence = _evidence_for(repo, record_ids)
    if len(evidence) > max_evidence:
        return _narrowing(
            "review_explanation",
            records,
            reason="This review cites more evidence than the analysis limit. Narrow the cited records.",
            groups=[],
            prompt_digest=prompt_digest,
            deployment=deployment,
        )
    candidates = []
    for candidate in repo.list_candidates(review_id):
        doctor = repo.get_doctor(candidate.get("candidate_doctor_id") or "")
        if not doctor:
            continue
        candidates.append({
            "doctor_id": doctor.get("doctor_id"),
            "preferred_name": doctor.get("preferred_name"),
            "specialty": doctor.get("specialty"),
            "city": doctor.get("city"),
            "state": doctor.get("state"),
        })
    if review.get("doctor_id"):
        doctor = repo.get_doctor(review["doctor_id"])
        if doctor and all(c["doctor_id"] != doctor["doctor_id"] for c in candidates):
            candidates.append({
                "doctor_id": doctor.get("doctor_id"),
                "preferred_name": doctor.get("preferred_name"),
                "specialty": doctor.get("specialty"),
                "city": doctor.get("city"),
                "state": doctor.get("state"),
            })
    constraints = _constraints_for_records(repo, set(record_ids))
    payload = {
        "task": "Explain why this review case needs a human decision.",
        "case_type": review.get("case_type"),
        "records": [_public_record(r) for r in records],
        "candidate_profiles_on_file": candidates,
        "evidence": [_public_evidence(e) for e in evidence],
        "document_passages": _passages(repo, evidence),
        "verified_constraints": constraints,
    }
    pack = _pack("review_explanation", payload, evidence, records, prompt_digest, deployment)
    pack.source_record_ids = record_ids
    return pack


def _require_records(repo: Any, record_ids: Sequence[str]) -> List[Dict[str, Any]]:
    from app.core.exceptions import NotFoundError, ValidationAppError

    if not record_ids:
        raise ValidationAppError("Select at least one source record.")
    found = []
    for record_id in record_ids:
        row = repo.get_source_record(record_id)
        if not row:
            raise NotFoundError(f"Source record {record_id} not found")
        found.append(row)
    return found


def _public_record(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: row.get(key) for key in RECORD_FIELDS}


def _public_evidence(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_id": row.get("evidence_id"),
        "source_record_id": row.get("source_record_id"),
        "document_id": row.get("document_id"),
        "document_version": row.get("document_version"),
        "page_number": row.get("page_number"),
        "block_id": row.get("block_id"),
        "quoted_text": row.get("quoted_text"),
        "source_field": row.get("source_field"),
        "citation_label": row.get("citation_label"),
    }


def _evidence_for(repo: Any, record_ids: Iterable[str]) -> List[Dict[str, Any]]:
    wanted = set(record_ids)
    rows = [row for row in repo.list_evidence() if row.get("source_record_id") in wanted]
    rows.sort(key=lambda row: row.get("evidence_id") or "")
    return rows


def _passages(repo: Any, evidence: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    passages = []
    seen = set()
    for evid in evidence:
        doc_id = evid.get("document_id")
        if not doc_id:
            continue
        version = str(evid.get("document_version") or "")
        page = evid.get("page_number")
        key = (doc_id, version, page)
        if key in seen:
            continue
        seen.add(key)
        pages = repo.document_pages(str(doc_id), version)
        blocks = []
        for doc_page in pages:
            if page is not None and int(doc_page.get("page_number") or 0) != int(page):
                continue
            for block in doc_page.get("blocks") or []:
                blocks.append({"block_id": block.get("block_id"), "text": block.get("text")})
        passages.append({
            "document_id": doc_id,
            "document_version": version,
            "page_number": page,
            "blocks": blocks,
        })
    return passages


def _constraints_for_records(repo: Any, record_ids: set) -> List[Dict[str, Any]]:
    rows = []
    for constraint in repo.list_constraints():
        if constraint.get("left_record_id") in record_ids or constraint.get("right_record_id") in record_ids:
            rows.append({
                "constraint_id": constraint.get("constraint_id"),
                "constraint_type": constraint.get("constraint_type"),
                "basis": constraint.get("basis"),
                "left_record_id": constraint.get("left_record_id"),
                "right_record_id": constraint.get("right_record_id"),
            })
    return rows


def _pack(
    operation: str,
    payload: Dict[str, Any],
    evidence: Sequence[Dict[str, Any]],
    records: Sequence[Dict[str, Any]],
    prompt_digest: str,
    deployment: str,
    doctor_revision: Optional[str] = None,
) -> EvidencePack:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return EvidencePack(
        operation=operation,
        user_text=blob,
        allowed_evidence_ids=sorted({e["evidence_id"] for e in evidence if e.get("evidence_id")}),
        known_dates=sorted(set(DATE_RE.findall(blob))),
        text_blob=blob.casefold(),
        fingerprint=_fingerprint(operation, payload, prompt_digest, deployment, doctor_revision),
        source_record_ids=sorted({r.get("source_record_id") for r in records if r.get("source_record_id")}),
        evidence_display=[
            {
                "evidence_id": e.get("evidence_id"),
                "citation_label": e.get("citation_label") or e.get("evidence_id"),
                "quoted_text": e.get("quoted_text"),
                "document_id": e.get("document_id"),
                "page_number": e.get("page_number"),
                "block_id": e.get("block_id"),
            }
            for e in evidence
        ],
        doctor_revision=doctor_revision,
    )


def _fingerprint(
    operation: str,
    payload: Dict[str, Any],
    prompt_digest: str,
    deployment: str,
    doctor_revision: Optional[str],
) -> str:
    material = {
        "operation": operation,
        "payload": payload,
        "prompt_digest": prompt_digest,
        "deployment": deployment,
        "doctor_revision": doctor_revision,
    }
    encoded = json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _narrowing(
    operation: str,
    records: Sequence[Dict[str, Any]],
    *,
    reason: str,
    groups: List[Dict[str, Any]],
    prompt_digest: str,
    deployment: str,
) -> EvidencePack:
    payload = {"outcome": "narrowing_required", "reason": reason, "groups": groups}
    return EvidencePack(
        operation=operation,
        user_text="",
        allowed_evidence_ids=[],
        known_dates=[],
        text_blob="",
        fingerprint=_fingerprint(operation, {"records": [r.get("source_record_id") for r in records], **payload}, prompt_digest, deployment, None),
        source_record_ids=[r.get("source_record_id") for r in records if r.get("source_record_id")],
        narrowing=payload,
    )


def _block_groups(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    parent = {r["source_record_id"]: r["source_record_id"] for r in records}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    buckets: Dict[str, List[str]] = {}
    for record in records:
        keys = []
        email = _norm(record.get("email"))
        phone = re.sub(r"\D", "", record.get("phone") or "")
        credential = _norm(record.get("credential_reference"))
        name = _norm(record.get("recorded_name"))
        if email:
            keys.append(f"email:{email}")
        if len(phone) >= 7:
            keys.append(f"phone:{phone}")
        if credential:
            keys.append(f"credential:{credential}")
        if record.get("identifier_kind") == "synthetic_individual" and record.get("provider_identifier"):
            keys.append(f"identifier:{_norm(record.get('provider_identifier'))}")
        if name:
            keys.append(f"name:{name}")
        for key in keys:
            buckets.setdefault(key, []).append(record["source_record_id"])
    for ids in buckets.values():
        for other in ids[1:]:
            union(ids[0], other)
    grouped: Dict[str, List[str]] = {}
    for record in records:
        grouped.setdefault(find(record["source_record_id"]), []).append(record["source_record_id"])
    return [
        {"group_id": index + 1, "source_record_ids": sorted(ids), "size": len(ids)}
        for index, ids in enumerate(grouped.values())
    ]


def _norm(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()
