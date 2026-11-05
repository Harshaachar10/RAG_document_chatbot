from __future__ import annotations

from pathlib import Path

from app.identity.config import DEFAULT_SOURCE_PROFILES
from app.identity.ingest import ingest_all
from app.identity.npi import build_nppes_index, luhn_valid_npi

DATA = Path(__file__).resolve().parents[1] / "data"


def test_all_source_csvs_present():
    for profile in DEFAULT_SOURCE_PROFILES.values():
        path = DATA / profile.filename
        assert path.exists(), f"missing {profile.filename}"


def test_ingest_row_counts_and_nppes_index():
    ingested = ingest_all(DATA)
    assert ingested["counts"]["sources"] == 8
    assert ingested["counts"]["nppes"] == 30
    assert ingested["counts"]["records"] >= 180
    index = build_nppes_index(ingested["nppes_rows"])
    assert len(index) == 30
    assert "1309803819" in index
    assert "1848459461" in index
    for npi in index:
        assert luhn_valid_npi(npi)


def test_utf8_sig_and_all_string_values():
    ingested = ingest_all(DATA)
    for rec in ingested["records"][:20]:
        for k, v in (rec.get("raw") or {}).items():
            assert isinstance(v, str)
