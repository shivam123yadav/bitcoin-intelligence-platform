# Bitcoin Intelligence Backend

FastAPI foundation for the Bitcoin Intelligence prototype.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The service exposes:

- `GET /api/health`
- `GET /docs`

## Configuration

Copy `.env.example` to `.env` when environment-level configuration is needed. The default CORS origins are the standard Vite development origins:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

`FRONTEND_CORS_ORIGINS` accepts a comma-separated list of explicit origins. Unrestricted wildcard CORS is rejected.

## Stage 2 Dataset APIs

The local frozen dataset is ingested from `datasets/generated/synthetic_traffic_v1.0.0.csv` and validated against its manifest and validation report.

- `GET /api/v1/dataset/metadata`
- `GET /api/v1/dataset/ingestion`

Validated observations are stored locally as DuckDB and Parquet under `backend/data/normalized/`.

## Stage 3 Correlation and Graph APIs

The correlation service reads the normalized DuckDB table and builds an offline NetworkX multigraph with IP, wallet, and transaction nodes. Graph artifacts are cached under `backend/data/graph/`.

- `GET /api/v1/entities/{entity_type}/{entity_id}`
- `GET /api/v1/entities/{entity_type}/{entity_id}/neighbors`
- `GET /api/v1/transactions/{txid}`
- `GET /api/v1/graph/statistics`
- `GET /api/v1/graph/neighborhood/{entity_type}/{entity_id}`

Common-input edges are labeled as observed associations or cluster candidates, not confirmed ownership. ML, clustering, pattern detection, risk scoring, and investigative leads remain outside this stage.



## Phase 2A Graph Risk Propagation

Phase 2A adds a separate graph-derived signal without changing anomaly detection, clustering, pattern detection, or the existing 150 investigation leads. It uses the completed anomaly score as the seed, propagates across common-input associations and input-to-output transaction-linked wallet relationships for up to two logical hops, and bounds the resulting propagated risk to `[0, 1]`. IP-layer edges are excluded from propagation.

- `GET /api/v1/entities/{entity_id}/propagated-risk`
- `python scripts\verify_phase2a.py`

The response separates `baseAnomalyScore`, `graphPropagatedSignal`, and `propagatedRisk`. Relationships are investigative graph evidence and are not proof of ownership or criminal activity.


## Phase 5C — Final Investigative Lead Ranking & Explainability

Phase 5C is a non-destructive layer over the validated Phase 5A candidates and Phase 5B audit.

Endpoints:
- `GET /api/v1/leads/phase5c/final`
- `GET /api/v1/leads/phase5c/final/{entity_id}`

The final queue contains a deterministic 0–100 **investigative priority score**, explicitly not a probability or conclusion of wrongdoing. Each lead includes signal breakdown, validated Phase 4C patterns, supporting wallets/transactions/IP observations, graph context, temporal range, evidence provenance, dependence warnings, review classification, and a human-readable explanation.

Verification:
```bash
python scripts/verify_phase5c.py
```

Phase 5C preserves the existing 150 production leads and all Phase 2A–5B experimental layers.
