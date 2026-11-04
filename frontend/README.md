# Doctor Intelligence Frontend

React + TypeScript + Vite application for Golden Records, Review Center, Sources & Processing, Overview, and Quality & Activity.

```powershell
npm ci
Copy-Item .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173
```

Environment:

```
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

The UI never silently falls back to local fixtures when the API is unavailable.
