# SIH 26146 Synthetic Dataset Generator

Offline, deterministic generator for the synthetic Bitcoin transaction/network
corpus defined by `docs/17_SYNTHETIC_DATASET.md`.

## Run

From `D:\A_SIH\prototype`:

```powershell
python -m tools.dataset_generator.cli generate --scale dev
```

The development scale emits about 5,000 records. After reviewing validation and
anti-triviality results, the recommended demo scale is:

```powershell
python -m tools.dataset_generator.cli generate --scale demo
```

All output is written under `datasets/`. No network access is used and no real
Bitcoin data is consumed.

## Outputs

- `datasets/generated/synthetic_traffic_v1.0.0.csv`
- `datasets/generated/synthetic_traffic_v1.0.0.ndjson`
- `datasets/generated/sample_records_v1.0.0.json`
- `datasets/metadata/scenario_labels.csv`
- `datasets/metadata/entity_labels.csv`
- `datasets/metadata/instance_catalog.csv`
- `datasets/metadata/ip_geo_mapping.csv`
- `datasets/metadata/generator_config.json`
- `datasets/metadata/dataset_manifest.json`
- `datasets/metadata/dataset_fingerprint.txt`
- `datasets/metadata/anti_triviality_audit.json`
- validation reports under `datasets/validation/`

Ground truth is metadata-only and is never part of canonical records.
