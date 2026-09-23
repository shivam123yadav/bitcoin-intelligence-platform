# 09 --- Investigation Priority & Explainability

## Terminology

Use **Investigation Priority**, not probability of criminality.

## Priority inputs

Potential inputs: - anomaly score - behavioral deviation - graph
connectivity - transaction velocity - IP/network diversity - pattern
evidence - clustering context - temporal irregularity

## Proposed output

Each lead should contain:

``` text
lead_id
entity_id
entity_type
priority_level
priority_score
anomaly_score
cluster_id
signals[]
evidence[]
source_records[]
created_at
analysis_run_id
```

## Explainability

Each lead should explain: 1. What was observed? 2. What model/pattern
detected it? 3. Which source records support it? 4. Why it increased
investigation priority?

## Evidence categories

-   observed data
-   derived feature
-   ML finding
-   graph finding
-   pattern finding

## Avoid unsupported feature attribution

Do not claim a feature caused an Isolation Forest result unless the
implementation provides a valid explanation method.

The UI should prefer statements such as: - "High transaction velocity
was observed." - "The entity received a high anomaly score relative to
the analyzed population." - "A candidate multi-hop pattern was
detected."
