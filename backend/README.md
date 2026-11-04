# Doctor Intelligence Backend

FastAPI service serving typed `/api/v1` endpoints from CSV seed data and mutable `data/runtime/state.json`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/seed_data.py
python scripts/validate_csv.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Scripts

- `scripts/seed_data.py` — generate coherent CSV + document fixtures
- `scripts/validate_csv.py` — schema, referential, and citation integrity checks
- `scripts/reset_demo.py --confirm RESET` — delete runtime state only

## Data

The API reads `CSV_DIRECTORY`, which defaults to `data/Doctor_Demo_CSV_Only/csv`. Source files stay immutable. Approvals and AI results are stored in `data/runtime/state.json`. A dataset fingerprint change archives the previous runtime file and reseeds. Run one API process; the runtime lock is process-local.

`python scripts/validate_csv.py` checks the configured directory. `scripts/seed_data.py` still writes the legacy `data/csv` folder and does not modify the supplied dataset.

## Docs

See `docs/` for API contracts, data dictionary, workflow states, future integration notes, and the client demo script.
