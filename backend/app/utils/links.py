from __future__ import annotations

from typing import Optional

LINKED_STATUSES = frozenset({"linked", "accepted"})


def is_linked_status(value: Optional[str]) -> bool:
    return (value or "") in LINKED_STATUSES


def display_npi_status(value: Optional[str]) -> str:
    if not value or value == "not_verified":
        return "Not verified"
    return str(value)
