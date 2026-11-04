#!/usr/bin/env python3
"""Validate the configured CSV directory. Does not read evaluation_only/."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.exceptions import DatasetValidationError  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.repositories.dataset_loader import dataset_error_lines, load_dataset  # noqa: E402


def main() -> int:
    settings = get_settings()
    try:
        loaded = load_dataset(settings.csv_path)
    except DatasetValidationError as exc:
        print("CSV validation failed. No records were dropped.")
        for line in dataset_error_lines(exc.errors):
            print(line)
        return 1
    print(f"Validated {loaded.csv_directory}")
    for name, count in sorted(loaded.row_counts.items()):
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
