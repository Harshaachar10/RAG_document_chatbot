from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def empty_to_null(value: Optional[str]) -> Optional[str]:
    """Treat blank cells and the literal pandas token ``nan`` as null.

    Postal codes, mock NPI labels, and other identifiers stay strings.
    Empty input is never coerced to zero.
    """
    if value is None:
        return None
    text = value.strip()
    if text == "" or text.lower() == "nan":
        return None
    return text


def parse_bool(value: Optional[str]) -> Optional[bool]:
    text = empty_to_null(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def escape_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def read_csv_dicts(path: Path) -> List[Dict[str, Optional[str]]]:
    fieldnames, rows = read_csv_rows(path)
    del fieldnames
    return [row for _, row in rows]


def read_csv_rows(path: Path) -> tuple[List[str], List[tuple[int, Dict[str, Optional[str]]]]]:
    """Read a UTF-8 CSV, including a leading BOM, and keep 1-based file line numbers."""
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path.name} has no header row")
        fieldnames = [(name or "").strip() for name in reader.fieldnames]
        if any(name is None or name == "" for name in reader.fieldnames):
            raise ValueError(f"{path.name} has a blank column name")
        rows: List[tuple[int, Dict[str, Optional[str]]]] = []
        for raw in reader:
            if None in raw:
                raise ValueError(
                    f"{path.name} line {reader.line_num} has more values than columns"
                )
            cleaned: Dict[str, Optional[str]] = {}
            for key, val in raw.items():
                cleaned[(key or "").strip()] = empty_to_null(val)
            rows.append((reader.line_num, cleaned))
        return fieldnames, rows


def write_csv_dicts(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: "" if row.get(name) is None else row.get(name) for name in fieldnames})


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def assert_safe_id(value: str, label: str = "id") -> str:
    if not SAFE_ID_RE.match(value):
        raise ValueError(f"Unsafe {label}: {value!r}")
    return value


def resolve_under(root: Path, relative: str) -> Path:
    """Resolve a relative path strictly under root (no traversal)."""
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    if not str(candidate).startswith(str(root_resolved)):
        raise ValueError(f"Path escapes root: {relative}")
    return candidate
