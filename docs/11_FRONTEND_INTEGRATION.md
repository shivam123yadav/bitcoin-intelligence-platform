# 11 --- Frontend Integration

## Existing frontend

The frontend already contains ten screens and a working navigation
shell.

## Integration principle

Do not rewrite pages unnecessarily.

Replace mock service implementations with API-backed services behind the
existing service abstraction.

## Service layers

Proposed:

``` text
src/services/
  apiClient.ts
  datasets.ts
  analysis.ts
  leads.ts
  entities.ts
  graph.ts
  patterns.ts
  clusters.ts
  cases.ts
```

## API client

The client should: - use a configurable API base URL - handle JSON -
handle non-2xx errors - support request cancellation where useful -
expose typed responses

## Loading/error states

Every API-backed screen should support: - loading - success - empty -
error

Do not silently fall back to fake data after an API error.

## Mapping

Overview: - dataset summary - analysis summary - priority distribution -
recent activity

Dataset: - dataset metadata - validation - data-quality statistics

Analysis: - analysis-run status - stage progress - stage metrics

Investigative Leads: - ranked lead list

Entity Investigation: - entity details - evidence - timeline

Graph Investigation: - focused graph

Transaction Flow: - candidate patterns

Clusters: - cluster statistics/details

Cases & Reports: - backend persistence can be introduced later

Settings: - backend configuration only when explicitly implemented
