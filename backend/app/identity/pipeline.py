from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.identity.config import MatchThresholds
from app.identity.descriptions import content_hash, describe_doctor, describe_record
from app.identity.embeddings import embed_texts
from app.identity.grow import assign_rounds
from app.identity.ingest import ingest_all
from app.identity.npi import build_nppes_index
from app.identity.profiles import load_sample_profiles
from app.identity.resolve import resolve_records
from app.identity.vectorstore import LocalVectorIndex, build_azure_stores


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

    profiles = load_sample_profiles(data_dir)
    descriptions = _build_description_rows(goldens, records, resolved.get("known_values") or {})
    embed = embed_texts([row["text"] for row in descriptions])
    semantic_hits, vector_status = _semantic_hits(descriptions, embed, goldens)
    growth = assign_rounds(
        decisions,
        resolved["catalog"],
        semantic_hits=semantic_hits,
        max_rounds=thresholds.max_rounds,
    )
    resolved["known_values"] = growth["known_values"]
    resolved["rounds"] = growth["rounds"]
    metrics["rounds"] = growth["rounds"]
    metrics["search"] = growth["search"]
    metrics["search"]["semantic_status"] = embed.get("status") or "skipped"
    if embed.get("reason"):
        metrics["search"]["semantic_reason"] = embed["reason"]
    metrics["search"]["doctors_embedded"] = sum(1 for row in descriptions if row["kind"] == "doctor" and row.get("embedded"))
    metrics["search"]["vector_store"] = vector_status
    metrics["suspicious"] = _suspicious(goldens, decisions)

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
        "known_values": resolved.get("known_values") or {},
        "rounds": resolved.get("rounds") or [],
        "profiles": profiles,
        "descriptions": [
            {key: value for key, value in row.items() if key != "vector"}
            for row in descriptions
        ],
        "embedding": {
            "status": embed.get("status"),
            "reason": embed.get("reason") or "",
            "model": embed.get("model") or "",
            "deployment": embed.get("deployment") or "",
            "embedded": embed.get("embedded") or 0,
            "cached": embed.get("cached") or 0,
        },
    }


def _build_description_rows(goldens, records, known_values) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for golden in goldens:
        text = describe_doctor(golden, {"aliases": golden.get("aliases") or [], "organizations": []})
        rows.append(
            {
                "id": golden.get("golden_id"),
                "kind": "doctor",
                "label": golden.get("display_name") or "",
                "text": text,
                "hash": content_hash(text),
                "state": golden.get("state") or "",
                "specialty": golden.get("specialty") or "",
                "embedded": False,
            }
        )
    for record in records:
        if record.get("is_reference"):
            continue
        text = describe_record(record)
        if not text:
            continue
        rows.append(
            {
                "id": record.get("uid"),
                "kind": "record",
                "label": record.get("record_id") or "",
                "text": text,
                "hash": content_hash(text),
                "state": (record.get("standardized") or {}).get("state") or "",
                "specialty": (record.get("standardized") or {}).get("specialty") or "",
                "embedded": False,
            }
        )
    return rows


def _semantic_hits(descriptions, embed, goldens) -> tuple[Dict[str, List[str]], str]:
    vectors = embed.get("vectors") or []
    if embed.get("status") == "skipped" or not any(vectors):
        return {}, "local-skipped"
    local = LocalVectorIndex()
    rows = []
    for row, vector in zip(descriptions, vectors):
        if not vector:
            continue
        row["embedded"] = True
        rows.append({**row, "vector": vector})
    local.upsert(rows)
    status = "local"
    azure_error = ""
    dimension = embed.get("dimension") or 0
    try:
        stores = build_azure_stores(dimension)
        if stores and rows:
            for store in stores:
                subset = [row for row in rows if (row.get("kind") == "doctor") == (store.index_name == "golden-doctors")]
                if not subset:
                    continue
                store.ensure()
                store.upsert(subset)
            status = "azure-search"
    except Exception:
        azure_error = "Azure AI Search was not updated. Local search is in use."
        status = "local"
    doctor_ids = {g.get("golden_id") for g in goldens}
    hits: Dict[str, List[str]] = {}
    by_id = {row["id"]: row for row in rows}
    for row in rows:
        if row["kind"] != "record":
            continue
        neighbors = local.search(row["vector"], k=20, state=row.get("state") or "", kind="doctor")
        matched = [item["id"] for item in neighbors if item.get("id") in doctor_ids and item.get("similarity", 0) >= 0.55]
        if matched:
            hits[row["id"]] = matched
        by_id[row["id"]]["neighbors"] = len(matched)
    if azure_error:
        status = f"{status}; {azure_error}"
    return hits, status


def _suspicious(goldens, decisions) -> List[Dict[str, Any]]:
    flags = []
    by_target: Dict[str, List[Dict[str, Any]]] = {}
    for decision in decisions:
        if decision.get("action") not in {"AUTO_LINK", "PROVISIONAL"}:
            continue
        by_target.setdefault(decision.get("target_id") or "", []).append(decision)
    for golden in goldens:
        rows = by_target.get(golden.get("golden_id") or "", [])
        states = {(row.get("standardized") or {}).get("state") for row in rows if (row.get("standardized") or {}).get("state")}
        specialties = {(row.get("standardized") or {}).get("specialty") for row in rows if (row.get("standardized") or {}).get("specialty")}
        licenses = {(row.get("standardized") or {}).get("license_no") for row in rows if (row.get("standardized") or {}).get("license_no")}
        if len(states) >= 3:
            flags.append({"doctor_id": golden.get("golden_id"), "code": "distant_locations", "detail": "Linked records name several states."})
        if len(specialties) >= 3:
            flags.append({"doctor_id": golden.get("golden_id"), "code": "unrelated_specialties", "detail": "Linked records name specialties that do not belong together."})
        if len(licenses) >= 3:
            flags.append({"doctor_id": golden.get("golden_id"), "code": "conflicting_licenses", "detail": "Linked records carry several license numbers."})
    return flags


