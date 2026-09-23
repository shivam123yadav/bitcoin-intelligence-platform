# SIH Prototype — Phase 5C Integrated Frontend

This package connects the existing React dashboard to the validated Phase 5C FastAPI investigative-lead pipeline.

## Backend

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

## Frontend

```powershell
cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

The frontend defaults to `/api/v1` and the Vite proxy forwards `/api` to `http://127.0.0.1:8000`.

## Phase 5C integration

The dashboard now consumes:

- `GET /api/v1/leads/phase5c/final`
- `GET /api/v1/leads/phase5c/final/{entity_id}`

Integrated surfaces:

- Overview → Phase 5C top investigative leads
- Investigative Leads → final Phase 5C queue
- Entity Investigation → final score, signal breakdown, validated patterns, evidence quality and review warnings

The backend's existing Phase 2A–5C systems remain non-destructive.
