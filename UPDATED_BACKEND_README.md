# Bitcoin Intelligence — Updated Offline Backend

This update completes the backend analysis path through anomaly detection, clustering, candidate pattern detection, investigation-priority leads, dashboard APIs, and the existing React service integration.

## Runtime

### Backend

```powershell
cd D:\A_SIH\prototype\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd D:\A_SIH\prototype\frontend
npm install
npm run dev
```

The frontend is configured to use the live backend by default. To explicitly configure it:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_USE_MOCK=false
```

## Analysis flow

1. Frozen v1.0.0 dataset is loaded from normalized DuckDB storage.
2. Wallet/IP behavioral features are generated.
3. Stage-3 graph structural features are incorporated for wallets.
4. Isolation Forest produces reproducible relative anomaly scores.
5. DBSCAN creates behavioral entity clusters.
6. Candidate peeling-chain and mixing-like structures are detected from observed transaction flow.
7. Investigation-priority leads are generated with evidence and source-record references.
8. Results are cached under `backend/data/runs/`.

## Main endpoints

- `GET /api/health`
- `GET /api/v1/dataset/meta`
- `GET /api/v1/dataset/stats`
- `GET /api/v1/dataset/quality`
- `GET /api/v1/dataset/preview`
- `GET /api/v1/analysis/stages`
- `POST /api/v1/analysis/run`
- `GET /api/v1/analysis/result`
- `GET /api/v1/leads`
- `GET /api/v1/clusters`
- `GET /api/v1/patterns`
- `GET /api/v1/graph`
- `GET /api/v1/graph/entity/{entity_id}`
- `GET /api/v1/transactions`
- `GET /api/v1/transactions/{txid}`
- `GET /api/v1/transactions/flow-patterns`
- `GET /api/v1/dashboard/*`

## Notes

- The canonical dataset is not regenerated or modified.
- Ground-truth label files are not used as ML features.
- Candidate patterns are not claims of criminality or attribution.
- Cases remain local/empty at this stage because the project documentation allows frontend/local case handling initially.
