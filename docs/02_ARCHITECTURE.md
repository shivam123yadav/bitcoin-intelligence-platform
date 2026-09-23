# 02 --- Architecture

## Logical architecture

``` text
                 React Frontend
                       |
                    REST/JSON
                       |
                  FastAPI API
                       |
        +--------------+--------------+
        |              |              |
    Data Layer     Analysis Layer   Case Layer
        |              |              |
   DuckDB/Parquet   ML/Graph       SQLite/metadata
        |              |
        +--------------+
               |
        Offline GeoIP DB
```

## Backend modules

Proposed modules:

``` text
backend/
  app/
    main.py
    config.py
    api/
    schemas/
    services/
    ingestion/
    normalization/
    enrichment/
    correlation/
    graph/
    features/
    ml/
    patterns/
    prioritization/
    explainability/
    storage/
    reports/
    tests/
```

## Processing stages

1.  Dataset registration
2.  Ingestion
3.  Validation
4.  Normalization
5.  GeoIP enrichment
6.  Correlation
7.  Graph construction
8.  Feature engineering
9.  Anomaly detection
10. Entity clustering
11. Pattern analysis
12. Investigation prioritization
13. Explainability/evidence generation

## Job model

Analysis should be represented as an analysis run with: - run ID -
dataset ID - start/end time - stage status - progress - record counts -
errors/warnings - model/configuration version - output artifact
references

The frontend must not assume an analysis succeeded merely because a page
contains mock values.
