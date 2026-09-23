# 12 --- Storage

## Analytical data

Prefer DuckDB + Parquet for analytical datasets and derived tables.

Reasons: - offline - local - efficient analytical queries - easy Python
integration - avoids unnecessary database infrastructure

## Application metadata

SQLite may be used for: - dataset registry - analysis-run metadata -
case metadata - report metadata - configuration

Do not introduce PostgreSQL or MongoDB unless a concrete requirement
appears.

## Suggested storage layout

``` text
data/
  raw/
  normalized/
  derived/
  graph/
  runs/
  reports/
  app.sqlite
```

## Reproducibility

Each analysis run should reference: - dataset ID - dataset
fingerprint/hash - code version - model version - configuration -
timestamps
