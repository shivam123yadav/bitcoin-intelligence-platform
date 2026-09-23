# Dataset system update

This update adds persistent dataset catalog and upload storage for the SIH prototype.

## Persistent storage

- Uploaded originals: `backend/data/runtime/datasets/<dataset-id>/original.<ext>`
- Dataset registry: `backend/data/runtime/datasets.json`
- Existing analytical artifacts remain under `backend/data/artifacts`, `backend/data/runs`, and `backend/data/normalized`.
- `backend/data/runtime/` is mutable application data and must not be overwritten by future application-code updates.

## API

- `GET /api/v1/dataset/catalog` — list stored datasets and active dataset.
- `POST /api/v1/dataset/upload?filename=<name>` — stream-upload a CSV/JSON/XML file (max 500 MB), validate its structure, store it, and register it.
- `POST /api/v1/dataset/select/{dataset_id}` — select an analyzed dataset as the active investigation dataset. Newly uploaded datasets remain stored but `not_run` until the analysis lifecycle is connected to them.

The current bundled synthetic dataset remains the active analyzed dataset. Uploading a new dataset does not silently switch the investigation to an unanalyzed dataset.
