from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


def paginate(items: Sequence[Any], page: int, page_size: int) -> Tuple[List[Any], int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return list(items[start:end]), total


def sort_items(
    items: List[Dict[str, Any]],
    sort_by: Optional[str],
    sort_direction: str,
    allowlist: Iterable[str],
    tie_breaker: str,
) -> List[Dict[str, Any]]:
    direction = (sort_direction or "asc").lower()
    if direction not in {"asc", "desc"}:
        raise ValueError("sort_direction must be asc or desc")
    key = sort_by if sort_by in set(allowlist) else tie_breaker
    reverse = direction == "desc"

    def sort_key(row: Dict[str, Any]) -> Tuple[Any, Any]:
        val = row.get(key)
        # None sorts last for asc
        none_rank = 1 if val is None or val == "" else 0
        return (none_rank, "" if val is None else val, row.get(tie_breaker) or "")

    return sorted(items, key=sort_key, reverse=reverse)


def matches_search(text: Optional[str], query: Optional[str]) -> bool:
    if not query:
        return True
    if text is None:
        return False
    return query.lower() in text.lower()


def doctor_in_scope(
    doctor: Dict[str, Any],
    *,
    specialty: Optional[str] = None,
    state: Optional[str] = None,
    source_id: Optional[str] = None,
    doctor_ids_for_source: Optional[set] = None,
) -> bool:
    if specialty and doctor.get("specialty") != specialty:
        return False
    if state and doctor.get("state") != state:
        return False
    if source_id and doctor_ids_for_source is not None:
        if doctor.get("doctor_id") not in doctor_ids_for_source:
            return False
    return True
