from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from pydantic import ValidationError

from app.ai.context import EvidencePack
from app.ai.results import RESULT_MODELS


def parse_model_output(operation: str, content: str, pack: EvidencePack) -> Dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model output was not valid JSON ({exc}).") from exc
    model = RESULT_MODELS[operation]
    try:
        parsed = model.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Model output did not match the schema: {exc.errors()[:4]}") from exc
    data = parsed.model_dump()
    unknown = sorted(set(_evidence_ids(data)) - set(pack.allowed_evidence_ids))
    if unknown:
        raise ValueError(f"Model cited evidence IDs that were not supplied: {unknown}")
    for change in data.get("proposed_changes") or []:
        effective = change.get("effective_date")
        if effective and effective not in pack.known_dates:
            raise ValueError(
                f"effective_date {effective} is not present in the supplied evidence. Leave it null when unknown."
            )
        value = (change.get("proposed_value") or "").strip()
        if value and value.casefold() not in pack.text_blob:
            raise ValueError(f"proposed_value {value!r} is not copied from the supplied evidence.")
    if operation == "profile_summary":
        for name in data.get("previous_names") or []:
            if name not in pack.allowed_names:
                raise ValueError(f"previous name {name!r} is not an accepted alias.")
        for proposal in data.get("outstanding_proposals") or []:
            if proposal and not _proposal_supported(proposal, pack.pending_proposals):
                raise ValueError("An outstanding proposal was not in the pending list.")
    return data


def _evidence_ids(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"supporting_evidence_ids", "conflicting_evidence_ids", "evidence_ids"} and isinstance(item, list):
                for evidence_id in item:
                    if evidence_id:
                        yield str(evidence_id)
            else:
                yield from _evidence_ids(item)
    elif isinstance(value, list):
        for item in value:
            yield from _evidence_ids(item)


def _proposal_supported(text: str, pending: List[str]) -> bool:
    folded = text.casefold()
    for proposal in pending:
        piece = proposal.split(": ", 1)[-1].casefold()
        if piece and piece in folded:
            return True
    return False
