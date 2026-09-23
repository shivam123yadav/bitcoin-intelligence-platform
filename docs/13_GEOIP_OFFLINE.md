# 13 --- Offline GeoIP Enrichment

## Requirement

The SIH problem statement calls for integration of an open-source
downloadable GeoIP database.

## Design

``` text
IP address
   ↓
local GeoIP database
   ↓
country / available geographic metadata
   ↓
normalized observation
```

ASN enrichment should use the locally available database/source when
supplied.

## Rules

-   no live external lookup during analysis
-   database path/configuration must be explicit
-   missing IP results must not fail the entire pipeline
-   record enrichment status
-   record database/version metadata for reproducibility

## Privacy

All enrichment should remain local/offline during normal analysis.
