# API Contracts

Base path: `/api/v1`

List responses:

```json
{
  "items": [],
  "total": 120,
  "page": 1,
  "page_size": 25,
  "applied_filters": {},
  "snapshot_version": 1
}
```

Error responses:

```json
{
  "error": {
    "code": "REVIEW_ALREADY_DECIDED",
    "message": "This case has already been reviewed.",
    "details": {}
  },
  "request_id": "..."
}
```

Key routes are documented in OpenAPI at `/docs` with operation IDs. Decision requests require `comment` (except resume), `expected_version`, and `idempotency_key`.
