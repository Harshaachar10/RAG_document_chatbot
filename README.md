# Doctor Intelligence — Golden Records & Identity History

Interactive mock-data demo for Daiichi Sankyo stakeholders. React frontend + FastAPI backend with CSV-backed synthetic doctor identity data, steward review actions, evidence viewer, and a clearly labeled processing simulation.

## Quick start

### Backend (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Keep the existing .env. It supplies Azure OpenAI settings.
# CSV_DIRECTORY defaults to data/Doctor_Demo_CSV_Only/csv.
python scripts/validate_csv.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend (separate terminal)

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173
```

### URLs

- Application: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/v1/health

### Reset demo state (backend stopped)

```powershell
cd backend
python scripts/reset_demo.py --confirm RESET
```

## Verification

```powershell
# backend
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest

# frontend
cd frontend
npm run typecheck
npm run test -- --run
npm run build
npx playwright install chromium
npm run test:e2e
```

## Boundaries

Prepared CSV profiles, links, and reviews load without a model call and stay labeled as prepared results. Explicit AI actions call Azure OpenAI and return recommendations only. Steward approval is required before a master, link, or history row changes. No NPPES lookup is performed. `scripts/seed_data.py` still writes the legacy `data/csv` folder and does not modify the supplied dataset.
