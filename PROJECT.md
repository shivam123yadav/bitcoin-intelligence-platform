# Bitcoin Intelligence --- Project Specification

## 1. Purpose

Bitcoin Intelligence is an offline transaction-monitoring and
investigation prototype for SIH 2026 Problem Statement 26146,
"AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic."

The system is intended to ingest synthetic Bitcoin transaction/network
metadata, correlate network-layer observations with blockchain-layer
transaction and wallet information, construct an entity/transaction
graph, apply AI/ML and pattern analysis, and produce prioritized,
explainable investigative leads.

## 2. Current project status

### Frontend

Implemented in React + TypeScript + Vite + Tailwind CSS.

Implemented screens: - Overview - Dataset - Analysis - Investigative
Leads - Entity Investigation - Graph Investigation - Transaction Flow -
Clusters - Cases & Reports - Settings

The current frontend is mock/offline and is the UI foundation only.

### Backend

Not implemented yet.

### ML

Not implemented yet.

### Data

The exact production ingestion schema must be confirmed against the
actual SIH dataset before backend implementation. Do not invent
dataset-specific formats.

## 3. Source requirements

The SIH problem statement requires: - bulk CSV/JSON/XML ingestion -
transaction/network metadata parsing - correlation of IP/port/timing
observations with wallet/TXID/amount information - an entity/transaction
graph linking IPs, wallets and transactions - a working AI/ML detection
use case - ranked, explainable investigative leads with
confidence/priority information - dashboard/link-analysis
visualization - offline Linux operation - offline GeoIP enrichment using
an open-source downloadable database

## 4. Engineering principles

1.  Offline-first.
2.  Reproducible analysis.
3.  Explainable outputs.
4.  Preserve provenance from source record to investigation lead.
5.  Separate observed facts from model findings and analyst
    interpretation.
6.  Do not label an entity criminal or claim illicit activity is proven.
7.  Prefer deterministic pipelines and versioned analysis runs.
8.  Do not fabricate backend results to satisfy the frontend.
9.  Keep frontend/backend contracts explicit.
10. Do not introduce external cloud AI APIs.

## 5. Proposed technology stack

Frontend: - React - TypeScript - Vite - Tailwind CSS - local interactive
graph implementation initially; Cytoscape.js may be introduced later if
justified

Backend: - Python - FastAPI - Pydantic - Pandas - DuckDB/Parquet for
analytical storage - NetworkX for graph analytics - scikit-learn for
classical ML - offline GeoIP database

Storage: - raw dataset files - normalized analytical data - analysis-run
metadata - derived features - graph artifacts - investigation leads -
cases/reports

## 6. Primary processing pipeline

CSV/JSON/XML → ingestion → validation → normalization → GeoIP enrichment
→ IP/TXID/wallet correlation → graph construction → feature engineering
→ anomaly detection → entity clustering → transaction-pattern analysis →
investigation priority → evidence/explainability → API → frontend

## 7. Implementation rule

The `/docs` directory is the authoritative engineering specification.

Agents must: - read PROJECT.md and all relevant docs before
implementation - preserve existing working frontend behavior - not
silently change architecture - not invent unavailable data - report
assumptions and blockers - validate changes with tests/builds
