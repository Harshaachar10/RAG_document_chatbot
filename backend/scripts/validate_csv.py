"""Validate the historical identity CSV set under backend/data."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.identity.config import DEFAULT_SOURCE_PROFILES  # noqa: E402
from app.identity.ingest import ingest_all  # noqa: E402
from app.identity.npi import build_nppes_index, luhn_valid_npi  # noqa: E402
from app.identity.pipeline import run_identity_pipeline  # noqa: E402


def main() -> int:
    data_dir = BACKEND_ROOT / "data"
    missing = [p.filename for p in DEFAULT_SOURCE_PROFILES.values() if not (data_dir / p.filename).exists()]
    if missing:
        print("Missing files:", ", ".join(missing))
        return 1
    ingested = ingest_all(data_dir)
    index = build_nppes_index(ingested["nppes_rows"])
    bad = [n for n in index if not luhn_valid_npi(n)]
    if bad:
        print("Invalid NPPES NPIs:", bad)
        return 1
    result = run_identity_pipeline(data_dir)
    print("OK ingest", ingested["counts"])
    print("OK pipeline", result["counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
