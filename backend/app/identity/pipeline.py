from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.identity.config import MatchThresholds
from app.identity.ingest import ingest_all
from app.identity.npi import build_nppes_index
from app.identity.resolve import resolve_records


def _synthetic_nppes_record(ref: Dict[str, Any]) -> Dict[str, Any]:
    return ref


def run_identity_pipeline(
    data_dir: Path,
    *,
    thresholds: Optional[MatchThresholds] = None,
) -> Dict[str, Any]:
    thresholds = thresholds or MatchThresholds()
    started = datetime.now(timezone.utc).isoformat()

    ingested = ingest_all(data_dir)
    records: List[Dict[str, Any]] = ingested["records"]
    nppes_index = build_nppes_index(ingested["nppes_rows"])
    resolved = resolve_records(records, nppes_index)
    decisions = resolved["decisions"]
    goldens = resolved["golden_records"]
    metrics = resolved["metrics"]
    note_links = []
    for decision in decisions:
        if decision.get("source_key") != "notes":
            continue
        note_links.append(
            {
                "uid": decision["uid"],
                "record_id": decision["record_id"],
                "note_date": (decision.get("standardized") or {}).get("record_date"),
                "redacted_note": decision.get("redacted_note") or "",
                "redaction_counts": {},
                "raw_note_type": None,
                "author_role": None,
                "action": decision.get("action"),
                "target_id": decision.get("target_id"),
                "target_label": decision.get("target_label"),
                "safety": decision.get("safety"),
                "proposed_changes": decision.get("proposed_changes") or [],
            }
        )
    by_uid = {d["uid"]: d for d in decisions}
    for rec in records:
        decision = by_uid.get(rec["uid"])
        if not decision:
            continue
        rec["decision"] = decision
        rec["npi_lookups"] = decision.get("npi_lookups") or []
        rec["redacted_note"] = decision.get("redacted_note") or rec.get("redacted_note")

    action_counts: Dict[str, int] = {}
    for decision in decisions:
        action_counts[decision["action"]] = action_counts.get(decision["action"], 0) + 1

    finished = datetime.now(timezone.utc).isoformat()
    return {
        "run": {
            "started_at": started,
            "finished_at": finished,
            "data_dir": str(data_dir),
            "thresholds": {
                "auto_link": thresholds.auto_link,
                "review_low": thresholds.review_low,
                "clear_winner_margin": thresholds.clear_winner_margin,
            },
        },
        "sources": ingested["sources"],
        "counts": {
            **ingested["counts"],
            "nppes_index": len(nppes_index),
            "candidate_pairs": 0,
            "decisions": len(decisions),
            "golden_records": len(goldens),
            "notes": len(note_links),
            "actions": action_counts,
            "open_reviews": sum(1 for d in decisions if d["status"] == "open"),
            "metrics": metrics,
        },
        "records": records,
        "decisions": decisions,
        "golden_records": goldens,
        "notes": note_links,
        "lineage": resolved["lineage"],
        "nppes_index_keys": sorted(nppes_index.keys()),
        "metrics": metrics,
    }


