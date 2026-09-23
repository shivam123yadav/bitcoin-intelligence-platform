# 07 --- ML Specification

## Primary ML use case

Unsupervised anomaly detection is the first working ML use case.

### Proposed model

Isolation Forest.

Reason: - useful when reliable labels are unavailable - suitable for
tabular behavioral features - produces an anomaly score/ranking - works
offline

## Feature categories

### Transaction

-   transaction count
-   total input amount
-   total output amount
-   average amount
-   maximum amount
-   fee statistics

### Temporal

-   transactions per time window
-   average inter-transaction time
-   burst activity
-   active duration

### Network

-   unique IP count
-   unique country count
-   ASN diversity
-   IP change frequency

### Graph

-   degree
-   unique neighbors
-   connected component size
-   centrality where appropriate

### Flow

-   incoming volume
-   outgoing volume
-   incoming/outgoing ratio
-   hop count
-   rapid-hop indicators

## Clustering

Proposed initial approach: - DBSCAN over normalized entity-level
features

Purpose: group entities with similar observed behavioral/structural
characteristics.

Clustering output must not be described as proven common ownership.

## Model artifacts

Store: - model configuration - feature schema/version - training/fit
statistics - random seed where applicable - model version - analysis run
ID

## Validation

The prototype should report: - number of entities scored - number of
anomalies selected - score distribution - cluster counts - cluster size
distribution

Do not fabricate accuracy metrics when ground-truth labels are
unavailable.
