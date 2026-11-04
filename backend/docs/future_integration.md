# Future Integration Paths

## Path 1 — Replace processed CSVs

Keep the same schema and API response models. Swap `data/csv/` content, validate, reset runtime, restart.

## Path 2 — Real resolution pipeline

Ingest raw source extracts through a future resolution/extraction pipeline that writes master/link/history/evidence outputs compatible with this schema. Then point repositories/providers at those outputs.

Interfaces already reserved:

- `DoctorRepository` / `ReviewRepository` / `EvidenceRepository`
- `ResolutionProvider` / `RecommendationProvider`

Current implementations: `CsvDemoRepository`, `MockResolutionProvider`, `MockRecommendationProvider`.

Dropping arbitrary raw CSV into the folder does not automatically create a golden dataset in this mock phase.
