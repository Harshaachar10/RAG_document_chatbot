from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple  # noqa: F401 — Dict used

from app.identity.config import DEFAULT_SOURCE_PROFILES, SourceProfile
from app.identity.npi import classify_npi
from app.identity.standardize import standardize_record


def _read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = list(reader.fieldnames or [])
        rows: List[Dict[str, str]] = []
        for row in reader:
            rows.append({k: ("" if v is None else str(v)) for k, v in row.items()})
        return headers, rows


def _stable_id(source_key: str, record_id: str, raw: Dict[str, str]) -> str:
    payload = "|".join([source_key, record_id, *[f"{k}={raw.get(k, '')}" for k in sorted(raw.keys())]])
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"{source_key}:{record_id or digest}"


def _extract_record_id(raw: Dict[str, str], profile: SourceProfile) -> str:
    for field in profile.id_fields:
        val = (raw.get(field) or "").strip()
        if val:
            return val
    # fallback composite
    bits = [raw.get(k, "") for k in sorted(raw.keys())[:4]]
    return hashlib.sha1("|".join(bits).encode("utf-8")).hexdigest()[:10]


def _extract_npi_fields(raw: Dict[str, str], profile: SourceProfile) -> List[Dict[str, Any]]:
    out = []
    for field in profile.npi_fields:
        info = classify_npi(raw.get(field))
        if info["raw"] or info["digits"]:
            out.append({"field": field, **info})
    return out


def discover_sources(data_dir: Path, profiles: Optional[Dict[str, SourceProfile]] = None) -> List[SourceProfile]:
    profiles = profiles or DEFAULT_SOURCE_PROFILES
    found: List[SourceProfile] = []
    for key, profile in profiles.items():
        path = data_dir / profile.filename
        if path.exists():
            found.append(profile)
    return found


def ingest_all(data_dir: Path, profiles: Optional[Dict[str, SourceProfile]] = None) -> Dict[str, Any]:
    profiles = profiles or DEFAULT_SOURCE_PROFILES
    sources_meta: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    nppes_rows: List[Dict[str, str]] = []

    for key, profile in profiles.items():
        path = data_dir / profile.filename
        if not path.exists():
            continue
        headers, rows = _read_csv(path)
        sources_meta.append(
            {
                "key": profile.key,
                "label": profile.label,
                "filename": profile.filename,
                "path": str(path),
                "row_count": len(rows),
                "headers": headers,
                "trust": profile.trust,
                "flags": {
                    "answer_key": profile.answer_key,
                    "exclude_from_matching": profile.exclude_from_matching,
                    "payment_source": profile.payment_source,
                    "venue_is_not_practice": profile.venue_is_not_practice,
                    "requires_compliance_review": profile.requires_compliance_review,
                },
            }
        )
        if profile.key == "nppes":
            nppes_rows = rows
            # also keep as reference records for UI/search, but mark not for matching
            for raw in rows:
                rid = _extract_record_id(raw, profile)
                uid = _stable_id(profile.key, rid, raw)
                npi_fields = _extract_npi_fields(raw, profile)
                std = standardize_record(
                    raw,
                    source_key=profile.key,
                    profile_flags={
                        "name_fields": profile.name_fields,
                        "venue_is_not_practice": profile.venue_is_not_practice,
                    },
                )
                records.append(
                    {
                        "uid": uid,
                        "record_id": rid,
                        "source_key": profile.key,
                        "source_label": profile.label,
                        "trust": profile.trust,
                        "raw": raw,
                        "standardized": std,
                        "npi_fields": npi_fields,
                        "exclude_from_matching": True,
                        "is_reference": True,
                        "payment_source": False,
                        "requires_compliance_review": False,
                        "answer_key": False,
                    }
                )
            continue

        seen_ids: Dict[str, int] = {}
        for row_idx, raw in enumerate(rows):
            rid = _extract_record_id(raw, profile)
            seen_ids[rid] = seen_ids.get(rid, 0) + 1
            dup_index = seen_ids[rid]
            # Disambiguate duplicate source IDs (exact re-ingests) while keeping stable primary uid
            uid = _stable_id(profile.key, rid, raw) if dup_index == 1 else f"{_stable_id(profile.key, rid, raw)}#dup{dup_index}"
            npi_fields = _extract_npi_fields(raw, profile)
            std = standardize_record(
                raw,
                source_key=profile.key,
                profile_flags={
                    "name_fields": profile.name_fields,
                    "venue_is_not_practice": profile.venue_is_not_practice,
                },
            )
            if not std["name"]["display"] and profile.name_fields:
                bits = [raw.get(f, "") for f in profile.name_fields]
                from app.identity.standardize import parse_person_name

                std["name"] = parse_person_name(" ".join(bits))

            records.append(
                {
                    "uid": uid,
                    "record_id": rid if dup_index == 1 else f"{rid}#dup{dup_index}",
                    "source_key": profile.key,
                    "source_label": profile.label,
                    "trust": profile.trust,
                    "raw": raw,
                    "standardized": std,
                    "npi_fields": npi_fields,
                    "exclude_from_matching": profile.exclude_from_matching,
                    "is_reference": False,
                    "payment_source": profile.payment_source,
                    "requires_compliance_review": profile.requires_compliance_review,
                    "answer_key": profile.answer_key,
                    "is_source_duplicate": dup_index > 1,
                    "duplicate_of_record_id": rid if dup_index > 1 else None,
                    "row_index": row_idx,
                }
            )

    return {
        "sources": sources_meta,
        "records": records,
        "nppes_rows": nppes_rows,
        "counts": {
            "sources": len(sources_meta),
            "records": len(records),
            "nppes": len(nppes_rows),
            "matchable": sum(1 for r in records if not r["exclude_from_matching"] and not r["answer_key"]),
        },
    }


def matchable_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in records if not r.get("exclude_from_matching") and not r.get("answer_key") and not r.get("is_reference")]
