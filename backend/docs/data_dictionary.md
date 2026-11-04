# Data Dictionary

Authoritative mock business data lives in `backend/data/csv/`.

| File | Purpose |
| --- | --- |
| sources.csv | Source system snapshots |
| doctors.csv | Golden doctor profiles (`official_npi` null in seed) |
| source_records.csv | Identity entries, supporting transactions, notes |
| source_links.csv | Record-to-doctor links |
| aliases.csv | Preferred / previous / abbreviation / spelling variants |
| affiliations.csv | Current, historical, proposed affiliations |
| observations.csv | Field observations |
| field_provenance.csv | Selected field provenance |
| events.csv | Timeline events |
| reviews.csv | Steward review cases |
| review_candidates.csv | Multi-candidate ambiguity cases |
| evidence.csv | Citations to documents or CSV fields |
| documents.csv | Document metadata |
| audit_events.csv | Seeded and live audit trail |

Nested fixtures:

- `data/documents/*.json` — safe typed document pages/blocks
- `data/mock/recommendations.json` — precomputed simulated recommendations
- `data/mock/processing_baseline.json` — seeded completed demo run
- `data/manifest.json` — seed version and showcase IDs
