# 04 --- Ingestion Pipeline

## Supported inputs

-   CSV
-   JSON
-   XML

## Pipeline

``` text
file
→ format detection
→ parser
→ raw validation
→ canonical normalization
→ data-quality report
→ analytical storage
```

## Requirements

The ingestion service must: - process bulk data - stream/chunk large
files where practical - avoid loading unnecessarily large datasets
entirely into memory - report progress - produce validation statistics -
preserve source record IDs - produce actionable errors

## Dataset lifecycle

``` text
REGISTERED
→ INGESTING
→ VALIDATING
→ NORMALIZED
→ READY
```

Failed states should include an error message and stage.

## Security

Treat uploaded datasets as untrusted input: - validate file type -
enforce configurable size limits - prevent path traversal - never
execute uploaded content - sanitize filenames
