# 10 --- API Contract

This is a proposed contract for frontend/backend integration. It must be
kept versioned and synchronized with implementation.

## Dataset

### GET /api/v1/datasets

List registered datasets.

### POST /api/v1/datasets/upload

Upload/register a dataset.

### GET /api/v1/datasets/{dataset_id}

Return dataset metadata and validation status.

## Analysis

### POST /api/v1/analysis

Start an analysis run for a dataset.

Request should identify: - dataset_id - analysis configuration

### GET /api/v1/analysis/{run_id}

Return run status and progress.

### GET /api/v1/analysis/{run_id}/summary

Return computed summary statistics.

## Leads

### GET /api/v1/leads

Query/filter investigation leads.

Supported filters should include: - priority - entity type - search
term - cluster - score range

### GET /api/v1/leads/{lead_id}

Return detailed lead evidence.

## Entity

### GET /api/v1/entities/{entity_id}

Return entity summary and evidence.

### GET /api/v1/entities/{entity_id}/timeline

Return entity activity timeline.

## Graph

### GET /api/v1/graph/{entity_id}

Return a focused investigation subgraph.

Optional query parameters: - depth - node_types - edge_types

## Patterns

### GET /api/v1/patterns

List detected candidate transaction patterns.

### GET /api/v1/patterns/{pattern_id}

Return pattern evidence.

## Clusters

### GET /api/v1/clusters

List entity clusters.

### GET /api/v1/clusters/{cluster_id}

Return cluster details.

## Cases

Cases may initially remain frontend/local until backend persistence is
required.

## API rules

-   JSON responses
-   Pydantic schemas
-   stable IDs
-   explicit error responses
-   no hidden mock data once real backend integration begins
