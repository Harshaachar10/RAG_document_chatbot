from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple


def _blocking_keys(record: Dict[str, Any]) -> Set[str]:
    std = record.get("standardized") or {}
    name = std.get("name") or {}
    keys: Set[str] = set()

    # NPI exact
    for nf in record.get("npi_fields") or []:
        if nf.get("valid") and nf.get("digits"):
            keys.add(f"npi:{nf['digits']}")

    last = name.get("last_norm") or ""
    first = name.get("first_norm") or ""
    zip3 = std.get("zip3") or ""
    state = std.get("state") or ""
    soundex = std.get("soundex_last") or ""
    phone = std.get("phone") or ""
    email = std.get("email") or ""
    license_no = (std.get("license_no") or "").lower()

    if last and first:
        keys.add(f"name:{last}|{first[:1]}")
        if zip3:
            keys.add(f"namezip:{last}|{first[:1]}|{zip3}")
        if state:
            keys.add(f"namestate:{last}|{first[:1]}|{state}")
    if soundex and first:
        keys.add(f"sx:{soundex}|{first[:1]}")
    if phone and len(phone) == 10:
        keys.add(f"phone:{phone}")
    if email:
        keys.add(f"email:{email}")
    if license_no and state:
        keys.add(f"lic:{state}|{license_no}")

    # hyphenated last-name parts
    for part in name.get("last_parts") or []:
        if part and first:
            keys.add(f"name:{part}|{first[:1]}")

    other = std.get("other_last") or ""
    if other and first:
        keys.add(f"name:{other}|{first[:1]}")

    return keys


def build_candidate_pairs(
    records: List[Dict[str, Any]],
    nppes_index: Dict[str, Dict[str, Any]],
) -> List[Tuple[str, str, List[str]]]:
    """
    Return list of (uid_a, uid_b_or_npi:NPI, block_reasons).
    NPPES reference candidates use target id 'npi:<digits>'.
    """
    matchable = [
        r
        for r in records
        if not r.get("exclude_from_matching") and not r.get("answer_key") and not r.get("is_reference")
    ]

    buckets: Dict[str, List[str]] = defaultdict(list)
    uid_to_keys: Dict[str, Set[str]] = {}
    for rec in matchable:
        keys = _blocking_keys(rec)
        uid_to_keys[rec["uid"]] = keys
        for k in keys:
            buckets[k].append(rec["uid"])

    pair_reasons: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    # record-record pairs from shared blocks
    for block_key, uids in buckets.items():
        uniq = sorted(set(uids))
        if len(uniq) < 2:
            continue
        # cap fan-out for large blocks
        if len(uniq) > 40:
            uniq = uniq[:40]
        for i, a in enumerate(uniq):
            for b in uniq[i + 1 :]:
                pair = (a, b) if a < b else (b, a)
                pair_reasons[pair].add(block_key.split(":")[0])

    # record → NPPES via valid NPI
    for rec in matchable:
        for nf in rec.get("npi_fields") or []:
            if nf.get("valid") and nf.get("digits") and nf["digits"] in nppes_index:
                pair_reasons[(rec["uid"], f"npi:{nf['digits']}")].add("npi")

        # also soft block into NPPES by name+state/zip when no NPI
        std = rec.get("standardized") or {}
        name = std.get("name") or {}
        last = name.get("last_norm") or ""
        first = name.get("first_norm") or ""
        if last and first:
            for npi, ref in nppes_index.items():
                rname = ref.get("name") or {}
                if rname.get("last_norm") != last:
                    # hyphen / other last
                    if last not in (rname.get("last_parts") or []) and last != (ref.get("other_last") or ""):
                        if (ref.get("other_last") or "") != last:
                            continue
                if (rname.get("first_norm") or "")[:1] != first[:1]:
                    continue
                same_geo = False
                if std.get("state") and ref.get("state") and std["state"] == ref["state"]:
                    same_geo = True
                if std.get("zip3") and ref.get("postal") and std["zip3"] == ref["postal"][:3]:
                    same_geo = True
                if same_geo or not std.get("state"):
                    pair_reasons[(rec["uid"], f"npi:{npi}")].add("name_geo")

    return [(a, b, sorted(reasons)) for (a, b), reasons in pair_reasons.items()]
