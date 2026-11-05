from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _pick_best(values: List[tuple[Any, float, str]]) -> Optional[Dict[str, Any]]:
    """values: (value, trust, source_uid)"""
    cleaned = [(v, t, s) for v, t, s in values if v not in (None, "", [], {})]
    if not cleaned:
        return None
    cleaned.sort(key=lambda x: x[1], reverse=True)
    best_v, best_t, best_s = cleaned[0]
    alts = [{"value": v, "trust": t, "source_uid": s} for v, t, s in cleaned[1:4] if v != best_v]
    return {"value": best_v, "trust": best_t, "source_uid": best_s, "alternates": alts}


def build_golden_records(
    records: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
    nppes_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Cluster AUTO_LINK / human-confirmed links by target NPI (or provisional cluster id).
    """
    by_uid = {r["uid"]: r for r in records}
    clusters: Dict[str, List[str]] = defaultdict(list)
    decision_by_uid = {d["uid"]: d for d in decisions}

    for d in decisions:
        action = d.get("action")
        target = d.get("target_id") or d.get("routing", {}).get("target_id")
        if action in {"AUTO_LINK", "LINK", "CONFIRM_LINK"} and target:
            clusters[str(target)].append(d["uid"])
        elif action == "ASSIGN_NPI" and d.get("assigned_npi"):
            clusters[f"npi:{d['assigned_npi']}"].append(d["uid"])

    goldens: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for cluster_id, uids in clusters.items():
        members = [by_uid[u] for u in uids if u in by_uid]
        if not members:
            continue

        npi = cluster_id.replace("npi:", "") if cluster_id.startswith("npi:") else ""
        ref = nppes_index.get(npi) if npi else None

        def collect(getter) -> List[tuple]:
            out = []
            for m in members:
                out.append((getter(m), float(m.get("trust") or 0.5), m["uid"]))
            if ref:
                out.append((getter({"standardized": {
                    "name": ref.get("name"),
                    "organization": ref.get("organization"),
                    "address": ref.get("address"),
                    "city": ref.get("city"),
                    "state": ref.get("state"),
                    "postal": ref.get("postal"),
                    "phone": ref.get("phone"),
                    "specialty": ref.get("specialty"),
                    "license_no": ref.get("license_no"),
                    "license_state": ref.get("license_state"),
                    "email": "",
                }, "trust": 1.0, "uid": f"npi:{npi}"}), 1.0, f"npi:{npi}"))
            return out

        name_display = _pick_best(
            collect(lambda m: ((m.get("standardized") or {}).get("name") or {}).get("display"))
        )
        golden = {
            "golden_id": f"GR-{npi or cluster_id.replace(':', '-')}",
            "npi": npi or None,
            "cluster_id": cluster_id,
            "display_name": (name_display or {}).get("value") or "Unknown",
            "attributes": {
                "name": name_display,
                "organization": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("organization"))),
                "address": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("address"))),
                "city": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("city"))),
                "state": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("state"))),
                "postal": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("postal"))),
                "phone": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("phone"))),
                "email": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("email"))),
                "specialty": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("specialty"))),
                "license_no": _pick_best(collect(lambda m: (m.get("standardized") or {}).get("license_no"))),
            },
            "member_uids": [m["uid"] for m in members],
            "member_count": len(members),
            "sources": sorted({m["source_key"] for m in members}),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        goldens.append(golden)

    goldens.sort(key=lambda g: (-g["member_count"], g["display_name"]))
    return goldens
