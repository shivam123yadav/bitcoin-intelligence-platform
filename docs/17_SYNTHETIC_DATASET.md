# 17 — Synthetic Dataset Specification

**Status: DESIGN ONLY.** This document specifies the dataset that a future
offline generator must produce (Section 17). It does not create, ship or
download any data.

## 1. Dataset Purpose

### Why the dataset exists

SIH 2026 problem statement 26146 ("AI-Powered Monitoring & Analysis of Bitcoin
Transaction Traffic") states that the dataset is **synthetic** and that the
**Dataset Link is Nil**. No corpus is supplied. `PROJECT.md` therefore records
that "the exact production ingestion schema must be confirmed against the
actual SIH dataset" — and there is no dataset to inspect.

This specification defines a purpose-built synthetic corpus so the ingestion,
correlation, graph, ML, pattern-detection, prioritisation and visualisation
stages documented in `docs/01`–`docs/16` can be built, validated and
demonstrated **fully offline**.

### What this dataset is

- **Synthetic** — every record is produced by a deterministic generator
  (Section 17). No record is copied from a real ledger or real traffic.
- **Modelled on the SIH problem statement** — the field list in Section 2 is
  the field list named by the problem statement (`docs/03`), plus one
  provenance key already present in the canonical normalized record.
- **Designed for the SIH prototype** — sized for a normal student laptop and
  an offline demonstration (Section 8), and shaped so that every documented
  pipeline stage has meaningful work to do.
- **Offline** — generation, ingestion, enrichment and analysis require no
  network access, no live blockchain API and no cloud service
  (`docs/16` Rule 6).
- **Multi-purpose** — it must simultaneously support entity clustering,
  anomaly detection, peeling-chain/mixing detection, risk/priority scoring and
  graph/link analysis. A dataset supporting only one of these is insufficient.
- **Evaluable** — it ships separate ground-truth metadata used **only** for
  post-hoc evaluation, never as a model input (Sections 10 and 11).

### What this dataset is NOT

- It does **not** represent real seized, intercepted, live or historical
  Bitcoin data.
- It does **not** represent any real wallet, person, organisation, IP
  allocation or investigative target.
- It is **not** evidence of illicit activity and must never be described as
  such (`docs/01`, `docs/08`, `docs/15`).
- It does **not** cancel the `docs/03` rule to inspect a source dataset before
  finalising parser logic. If a real corpus is supplied later, that rule and
  Section 18 of this document continue to apply.

## 2. Canonical Schema

One record = **one network observation of one Bitcoin transaction**, which is
the granularity implied by the SIH field list and by the correlation model in
`docs/05`.

| Field | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `timestamp` | string (ISO 8601, UTC, second precision) | Yes | `2024-11-14T09:31:02Z` | Time at which the network observation was recorded. Drives temporal features and temporal correlation. |
| `src_ip` | string (IPv4) | Yes | `203.0.113.42` | Observing source IP. Reserved/documentation ranges only (Section 15). |
| `dst_ip` | string (IPv4) | Yes | `198.51.100.77` | Destination IP of the observation. Must differ from `src_ip`. |
| `src_port` | integer | Yes | `8333` | Source TCP port, range 1024–65535. |
| `dst_port` | integer | Yes | `18333` | Destination TCP port. `8333` is dominant (see PT-01–PT-03). |
| `txid` | string (64 lowercase hex) | Yes | `3f1c…a9d2` (full 64 chars) | Bitcoin transaction identifier. **Not unique per record**: one transaction may be observed by several peers. |
| `input_addresses` | string[] | Yes | `["bc1q…k3fz","bc1q…q7vd"]` | Spending addresses in deterministic spend order (ordering per Section 3; AR-05). |
| `output_addresses` | string[] | Yes | `["bc1q…m2pa","bc1q…t9xw"]` | Receiving addresses in deterministic output-index order. |
| `input_amounts` | number[] (BTC) | Yes | `[2.50000000,1.75000000]` | Value of each input, positionally aligned with `input_addresses`. |
| `output_amounts` | number[] (BTC) | Yes | `[3.90000000,0.34988000]` | Value of each output, positionally aligned with `output_addresses`. |
| `fee` | number (BTC) | Yes | `0.00012000` | `fee = sum(input_amounts) - sum(output_amounts)` within 1e-8 tolerance. |
| `script_type` | enum | Yes | `P2WPKH` | Dominant output script type. Allowed values: `P2PKH`, `P2SH`, `P2WPKH`, `P2WSH`, `P2TR`, `MultiSig`, `OP_RETURN` — identical to the `ScriptType` union in `frontend/src/types/index.ts`. |
| `geo_country` | string (ISO 3166-1 alpha-2, uppercase) | Yes | `SG` | Country associated with the observing IP. Stable per IP (GQ-01). |
| `asn` | string | Yes | `AS14061 DigitalOcean` | Autonomous system associated with the observing IP. Stable per IP (GQ-01). |
| `source_record_id` | string (generator-assigned) | Yes | `R00000001` | Stable provenance key (`docs/03`, `docs/04`, `docs/16` Rule 7). Links a record to ground truth, validation reports and investigation evidence. |

### Schema rules

1. These 15 fields are the **complete** dataset. No extra columns are added.
   Every additional quantity named in `docs/03`, `docs/07` or `docs/09`
   (`input_count`, `output_count`, `total_in`, `total_out`, `net_flow`,
   `velocity`, `degree`, `hop_count`, `anomaly_score`, …) is a **derived
   feature** computed by the pipeline, never shipped as an input column.
2. Address arrays preserve **positional correspondence**:
   `input_amounts[i]` is the value of `input_addresses[i]`, and
   `output_amounts[i]` is the value of `output_addresses[i]`.
3. Amounts and fees are expressed in **BTC with 8-decimal precision**. This
   resolves one open question in `docs/03` **for this synthetic dataset only**
   (Section 18); the real-corpus caution remains in force elsewhere.
4. `source_record_id` is assigned by the generator — monotonic, stable,
   `R` + 8 zero-padded digits — so that ground truth, evidence and validation
   reports can reference a record independently of file row order.
5. Frontend/display identifiers (`Wallet-A7F2`, `TX-120A`, `IP-01`, `C-07`)
   are **derived** identifiers produced by the backend/UI layer from
   `input_addresses`, `output_addresses`, `src_ip` and cluster assignment.
   They are not dataset fields and must not appear in the source file.
6. Empty arrays are **not** permitted in the demo dataset: every record has at
   least one input and at least one output. The invalid-sample fixture
   (Section 16) may contain empty arrays in order to exercise validation.

## 3. CSV Representation

CSV is the primary bulk format (`docs/04`). One row = one observation record.
The header is written exactly once and the column order is fixed:

```text
timestamp,src_ip,dst_ip,src_port,dst_port,txid,input_addresses,output_addresses,input_amounts,output_amounts,fee,script_type,geo_country,asn,source_record_id
```

### Array encoding

Array fields are encoded as **compact JSON arrays inside a single CSV field**,
and that field is always wrapped in double quotes. Address arrays therefore
look like:

```text
input_addresses  -> ["bc1q…k3fz","bc1q…q7vd"]
input_amounts    -> [2.50000000,1.75000000]
```

Rules:

1. No whitespace inside the JSON array (no spaces after commas) so that the
   byte representation is byte-identical for the same logical record.
2. Element order is the spend order for inputs and the output-index order for
   outputs (AR-05). Order is meaningful and must be preserved on round-trip.
3. **Positional correspondence is mandatory**: element `i` of
   `input_amounts` belongs to element `i` of `input_addresses`; element `j` of
   `output_amounts` belongs to element `j` of `output_addresses`.
4. Amounts inside arrays are plain decimal literals with 1–8 decimal places,
   never exponent notation (`0.00000010`, not `1e-7`).
5. A single-element array is still an array: `["bc1q…k3fz"]`, never a bare
   scalar.
6. Empty arrays (`[]`) are reserved for the invalid-sample fixture; they must
   not appear in the demo dataset.

### Escaping and serialization

RFC 4180 conventions, applied deterministically:

- Delimiter: `,`. Line terminator: `LF` only (no `CRLF`).
- Encoding: UTF-8 **without** BOM.
- A field is quoted if it contains `,`, `"`, `LF` or `CR`.
- Address/amount array fields are **always** quoted (they always contain `,`).
- An embedded `"` is escaped by doubling it. Because array fields are JSON,
  the quotes that delimit JSON strings must be doubled:

```csv
timestamp,src_ip,dst_ip,src_port,dst_port,txid,input_addresses,output_addresses,input_amounts,output_amounts,fee,script_type,geo_country,asn,source_record_id
2024-11-14T09:31:02Z,203.0.113.42,198.51.100.77,8333,18333,3f1c8d2e5a4b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f,"[""bc1qk3fz9v2mnt4r7xwq8pd0hay6cj5uslzb1e2g3t4"",""bc1qq7vd5n8s2w1kre6tx9m4pa0lzjc7hf3byug6dq9""]","[""bc1qm2pa4t7k9v2xs1wq8rd0jz6hn5clb3euya7gf2"",""bc1qt9xw6r3n8s5m2vd1kp9j4lz7hc0byu3feqatg6m""]","[2.50000000,1.75000000]","[3.90000000,0.34988000]",0.00012000,P2WPKH,SG,AS14061 DigitalOcean,R00000001
```

- Numeric scalars (`src_port`, `dst_port`, `fee`) are unquoted.
- `asn` contains a space and may contain punctuation; it is quoted only if it
  contains a delimiter or quote character. The `,`-free canonical form
  `AS<number> <Organisation>` is preferred so that quoting stays predictable.
- No field ever contains a line break.
- Trailing delimiter and trailing blank lines are not permitted.

### Row ordering

Rows are emitted in `timestamp` ascending order, breaking ties by
`source_record_id`. Deterministic ordering keeps diffs between regenerated
versions reviewable, and it does not constrain the pipeline — ingestion must
still treat row order as non-semantic.

### Multiple observations of one transaction

The same `txid` may appear in several rows with different `timestamp`,
`src_ip`, `dst_ip`, `src_port`, `dst_port` and `source_record_id`, while the
blockchain-layer fields (`input_addresses`, `output_addresses`,
`input_amounts`, `output_amounts`, `fee`, `script_type`) stay identical.
This is what makes `docs/05` correlation non-trivial and what rule TX-02 in
Section 13 enforces.

## 4. JSON Representation

Two JSON forms are specified. The generator must be able to emit both from the
same in-memory records, and a round-trip through either form must reproduce the
CSV form byte-for-byte.

| Form | File | Purpose |
| --- | --- | --- |
| **NDJSON** (newline-delimited JSON, one object per line) | `synthetic_traffic_v<version>.ndjson` | Bulk format (`docs/04` requires streaming/chunked ingestion). One record per line, no wrapping array. |
| **JSON array / sample file** | `sample_records_v<version>.json` (small, e.g. 200 records) | Human inspection, frontend/back-end contract examples, tests. |

Rules for both forms:

- Field names are identical to the canonical schema (`snake_case`).
- All 15 fields are present in every object; no field is omitted or `null` in
  the demo dataset.
- Arrays stay real JSON arrays with preserved element order.
- Numbers are emitted with the same decimal formatting used in CSV (1–8 decimal
  places, no exponent notation); a JSON consumer must not be required to
  re-round values.
- Utf-8, `LF` line endings, no trailing whitespace.

### Representative record

The example below is a two-input / two-output transaction that also happens to
be the first hop of a peeling-chain instance (Section 7D), so it demonstrates
network metadata, blockchain structure, amounts, fee, script type and
geography in one object.

```json
{
  "timestamp": "2024-11-14T09:31:02Z",
  "src_ip": "203.0.113.42",
  "dst_ip": "198.51.100.77",
  "src_port": 8333,
  "dst_port": 18333,
  "txid": "3f1c8d2e5a4b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f",
  "input_addresses": [
    "bc1qk3fz9v2mnt4r7xwq8pd0hay6cj5uslzb1e2g3t4",
    "bc1qq7vd5n8s2w1kre6tx9m4pa0lzjc7hf3byug6dq9"
  ],
  "output_addresses": [
    "bc1qm2pa4t7k9v2xs1wq8rd0jz6hn5clb3euya7gf2",
    "bc1qt9xw6r3n8s5m2vd1kp9j4lz7hc0byu3feqatg6m"
  ],
  "input_amounts": [2.5, 1.75],
  "output_amounts": [3.9, 0.34988],
  "fee": 0.00012,
  "script_type": "P2WPKH",
  "geo_country": "SG",
  "asn": "AS14061 DigitalOcean",
  "source_record_id": "R00004217"
}
```

### What the record expresses

- **Network layer** — `src_ip`, `dst_ip`, `src_port`, `dst_port`, `timestamp`:
  where and when the transaction was observed (`docs/05` correlation keys).
- **Blockchain layer** — `txid`, `input_addresses`, `output_addresses`,
  `input_amounts`, `output_amounts`, `fee`, `script_type`: what the transaction
  structurally does.
- **Geographic layer** — `geo_country`, `asn`: attributes of the observing IP,
  filled either from the fixed synthetic IP→geo mapping or by later offline
  enrichment (Section 18, conflict C3).
- **Provenance** — `source_record_id`.

### Deliberate JSON design notes

1. The network layer is observation-scoped and the blockchain layer is
   transaction-scoped. `txid` is the join key between them; a second NDJSON
   line with the same `txid` must repeat the blockchain layer verbatim.
2. `fee` is redundant with the input/output sums by design. It is kept because
   the SIH field list names it, and it doubles as a validator of generator
   arithmetic (AM-08).
3. No derived or labelled quantity appears in the record. There is no
   `is_anomaly`, no `scenario`, no `anomaly_score` field — such fields live in
   the ground-truth files (Section 10) and must never be merged into the
   ingestible record.

## 5. Entity Model

The dataset produces four kinds of addressable entity plus one derived grouping.
Terminology follows `docs/01` (output terminology), `docs/05` (correlation) and
`docs/06` (graph node types).

### IP Address

A network endpoint that observed traffic. Identity = the IPv4 literal in
`src_ip` / `dst_ip`. Attributes carried by the dataset: `geo_country`, `asn`.
Attributes derived by the pipeline: observation count, first/last seen, unique
wallet count, unique country count, IP-change frequency (`docs/07` network
features). An IP is **an observing endpoint, not a person**.

### Wallet / Address

A distinct string appearing in `input_addresses` or `output_addresses`. Identity
= the address literal. Attributes derived by the pipeline: transaction count,
incoming/outgoing volume, incoming/outgoing ratio, degree, first/last seen.
A wallet is **an observed address, not a proven owner**.

### Transaction

A distinct `txid`. Identity = `txid`. Intrinsic (blockchain-layer) attributes:
`input_addresses`, `output_addresses`, `input_amounts`, `output_amounts`, `fee`,
`script_type`. Observation-scoped attributes that accumulate per txid: number of
network observations, set of observing IPs, first/last observation timestamp.

### Network Observation

A single dataset record: one IP pair, one port pair, one timestamp and one
`txid`. Identity = `source_record_id`. This is the **source of truth** in the
dataset: every wallet, transaction and IP entity is derived from observations,
and every evidence chain must terminate in one or more `source_record_id`
values (`docs/16` Rule 7). An observation is a row, not an entity to be
investigated.

### Entity / Cluster

A group of wallets that the analysis places together — because of common-input
co-spend evidence, shared network observations, graph community structure or
behavioral similarity (`docs/05`, `docs/07` clustering, `docs/06` `Cluster`
node). Clusters exist **only after analysis**; they are not present in the
source dataset. The dataset's job is to contain structure that makes such
grouping possible. Cluster membership must always be described as an inference,
not as proven common ownership.

### Scenario instance (generator-side term)

A generator-side bookkeeping unit: one concrete realisation of one of the eight
scenarios in Section 7 (e.g. "peeling-chain instance 7, 9 hops, 2024-11-18").
A scenario instance is identified by an ID in the ground-truth metadata only. It
is **not** a dataset field, and it is **not** a cluster: one derived cluster may
contain several scenario instances, and one scenario instance may be split
across several derived clusters. That mismatch is intentional and is a source of
realistic evaluation difficulty.

### Identity summary

| Entity | Identity | Defined by dataset | Defined by analysis |
| --- | --- | --- | --- |
| IP Address | IPv4 literal | `src_ip`, `dst_ip`, `geo_country`, `asn` | counts, diversity, change frequency |
| Wallet | Address literal | membership in input/output arrays, amounts | volume, degree, ratio, hop metrics |
| Transaction | `txid` | txid + blockchain-layer fields | observation count, anomaly score |
| Network Observation | `source_record_id` | timestamp, ports, IP pair, txid | — (quarantine/validation status only) |
| Cluster | derived cluster ID | — | membership inference + behavioral tags |
| Scenario instance | ground-truth ID | — (metadata only) | evaluation grouping only |

## 6. Relationship Model

### Primary chain

```text
IP
 ↓   (observed at timestamp, ports)
Network Observation                ← one dataset record (source_record_id)
 ↓   (carries txid)
Transaction
 ↓   (spends)
Input Wallet
 ↓
Output Wallet
```

Reading the chain for one record: an IP is linked to a transaction because a
record exists that pairs them; the transaction is linked to its input wallets
and its output wallets because those addresses appear in its arrays. Nothing in
the chain is inferred — it is all *observed* in the record.

### IP → Network Observation

Exact, record-level. `src_ip` and `dst_ip` both participate; each occurrence is a
distinct observation with its own `source_record_id`, `timestamp` and ports.

### IP → Wallet

Not stored directly. It is a **derived association**: an IP is associated with a
wallet because the IP observed one or more transactions that reference that
wallet. Strength depends on observation count, time span and wallet diversity:

- few observations, one wallet, tight time window → strong observed association;
- many observations, many wallets, long time span (exchange-like endpoint) →
  weak association.

This association must always be labelled "observed association", never
"ownership".

### Transaction → Wallet

Stored directly, with direction and value:
`TRANSACTION_INPUT_WALLET` for `input_addresses[i]` with amount
`input_amounts[i]`, and `TRANSACTION_OUTPUT_WALLET` for `output_addresses[j]`
with amount `output_amounts[j]`. These are exact, value-carrying edges.

### Wallet → Wallet

Two distinct sub-relationships that must not be conflated:

1. **Transfer relationship** — wallet A transferred value to wallet B because A
   appears in the inputs and B in the outputs of the same transaction. Exact,
   amount-bearing, time-stamped.
2. **Common-input / co-spend association** — wallets A and B both supplied
   inputs to the same transaction. This is a **derived inference** about
   possible common control (`docs/05`) and is the primary input to entity
   clustering (Section 7F). It must be surfaced as an inference with supporting
   `source_record_id` evidence.

### Wallet → Entity/Cluster

Derived only, and only after clustering runs. Carries a cluster ID, the method
and parameters used, and the supporting evidence. Never present in the dataset.

### Mapping to graph nodes and edges

The graph engine in `docs/06` defines exactly four node types and five edge
types. The dataset maps onto them without adding types:

| Relationship | Derived from | Graph realisation | Nature |
| --- | --- | --- | --- |
| IP observing a transaction | `src_ip`/`dst_ip` + `txid` per record | edge `IP OBSERVED_TRANSACTION` | exact observation |
| IP ↔ wallet | IP's observed transactions vs referenced wallets | no dedicated edge type; reported as an observed association in evidence | inferred association |
| Transaction consuming a wallet | `input_addresses[i]`, `input_amounts[i]` | edge `TRANSACTION_INPUT_WALLET` (value = amount) | exact |
| Transaction producing a wallet | `output_addresses[j]`, `output_amounts[j]` | edge `TRANSACTION_OUTPUT_WALLET` (value = amount) | exact |
| Wallet-to-wallet transfer | input wallet and output wallet of the same `txid` | edge `WALLET_CONNECTED_WALLET` | exact source, derived edge |
| Common-input ownership suggestion | co-spend inside one transaction | feeds clustering, reported as evidence; may strengthen `WALLET_CONNECTED_WALLET` | inferred |
| Wallet in cluster | clustering output | edge `WALLET_MEMBER_OF_CLUSTER` | inferred |

**Graph node set** = `IP`, `Transaction`, `Wallet`, `Cluster` (`docs/06`). The
Network Observation is deliberately **not** a node type: it is the row that
*produces* an `IP OBSERVED_TRANSACTION` edge. This avoids an architecture change
and keeps observed facts (edges) distinct from model findings (anomaly scores,
clusters), as `PROJECT.md` principle 5 requires.

### Edge provenance requirements

Every edge must be traceable to at least one `source_record_id`; every derived
relationship must carry the record IDs that generated it, a confidence/strength
value where applicable, and its relationship class (exact / temporal association
/ inferred) — exactly as required by `docs/05` "Correlation output".

## 7. Synthetic Investigation Scenarios

The dataset must contain eight scenario families, A–H. They are the functional
requirements of the corpus: each one exists so that a specific documented
pipeline stage has a fair, non-trivial problem to solve.

### Scenario design constraints (apply to all eight)

1. **No cartoon anomalies.** Percentages, thresholds and shapes must overlap
   with normal behaviour, otherwise the ML task collapses into a trivial
   separator and the demo proves nothing.
2. Normal activity (A and the dense, exchange-like part of H) must sometimes
   contain multiple inputs, multiple outputs, high values, repeated IPs and
   short transaction bursts.
3. Anomalous families must sometimes look ordinary locally (one hop, one IP,
   ordinary amount) and only stand out in aggregate, over time, or structurally.
4. Every family is generated as several **instances** (Section 5), scattered
   across the 30-day window rather than clustered at one point in time.
5. Every family must be evaluable from `source_record_id`-level ground truth
   (Section 10) but must not be detectable from any single field.

---

### A. Normal Bitcoin Activity

**Purpose.** Provide the population baseline that makes "anomaly" meaningful,
and act as a deliberate false-positive reservoir.

**Approximate transactions.** ≈40,900 of 48,000 records (≈85 %) in the SIH demo
dataset.

**Wallets involved.** ≈10,500 distinct addresses; most participate in 1–4
transactions; a small tail (≈600) participates in 20–200 transactions (public
services, exchanges, merchants). These heavy wallets are *normal* — a key
realism element.

**IP behaviour.** ≈3,600 distinct IPs. A typical wallet is observed from 1–3
IPs; ≈12 % of wallets appear from ≥2 IPs; ≈3 % from ≥4 IPs (mobile users,
multi-homed hosts). Public endpoints observe hundreds of unrelated wallets.

**Timing behaviour.** Arrivals follow a Poisson-like process with a diurnal
profile and weekday/weekend variation across the full 30-day window. Short
bursts occur naturally: ≈8 % of wallets show 5–15 transactions inside a 10-minute
window at least once, and ≈3 % produce legitimate 3–4 hop chains (batched
payouts, sweeps).

**Amount behaviour.** Log-normal, median ≈0.05 BTC, 95th percentile ≈2 BTC,
tail to ≈40 BTC. Values are ordinary but not tiny: legitimate 5–20 BTC
transfers occur daily.

**Transaction behaviour.** 1–3 inputs and 1–3 outputs typical; 22 % of records
have ≥2 inputs; 31 % have ≥2 outputs; occasional 8–12 input consolidations.
All seven `script_type` values appear, with `OP_RETURN` rare (≈0.4 %).

**Graph structure.** Low-degree, heavy-tailed degree distribution, many small
components, a partially connected core, plus a few high-degree hubs. Density
varies across the window (busier days look denser).

**Expected anomaly/ML signal.** None by design at the individual level, but
Isolation Forest is *expected* to rank some of these records high — the
heavy-tail wallets should occupy part of the top decile. This is the intended
false-positive source and must be reported honestly in the evaluation
(Section 11).

**Expected pattern-detection signal.** None. Some legitimate payout chains may
sit at the edge of the multi-hop threshold and be reported as low-confidence
candidates; that behaviour is desirable for demo honesty.

**Expected UI evidence.** Low investigation priority; "no candidate pattern";
ordinary timeline; typical IP/ASN diversity; flagged for review only when the
model score is elevated, with wording such as "elevated transaction velocity
relative to the analysed population".

---

### B. High Transaction Velocity

**Purpose.** Exercise temporal features (`docs/07` temporal category) and prove
that velocity alone can raise priority without any structural pattern.

**Approximate transactions.** ≈2,000 records; 14 instances, ≈140 records per
instance.

**Wallets involved.** Per instance: 1–3 core wallets plus 20–40 counterparty
wallets. Core wallets carry 60–200 transactions each.

**IP behaviour.** Deliberately quiet: 1–2 stable IPs per instance, reused from
the normal IP pool, no IP churn and no country hopping. The network feature
category must **not** fire here, otherwise the scenario would be detectable for
the wrong reason.

**Timing behaviour.** 2–6 bursts per active day, each burst 20–80 transactions
inside a 10–60 minute window; bursts recur on 4–10 separate days; inter-burst
gaps of hours. Inter-transaction time inside a burst is seconds to low minutes.

**Amount behaviour.** Ordinary — mostly 0.01–3 BTC, occasionally 10–20 BTC.
Amounts are deliberately unremarkable so velocity is the dominant deviation.

**Transaction behaviour.** 1–2 inputs, 1–3 outputs; typical script types;
normal fees. Structurally indistinguishable from busy legitimate wallets.

**Graph structure.** Hub/star-like around the core wallets, with new
counterparties appearing over time; degree grows steadily; the core wallets sit
in the top decile of degree but so do some normal hubs.

**Expected anomaly/ML signal.** Elevated transactions-per-window, burst count,
short average inter-transaction time and long active duration — all relative to
the analysed population, not absolute.

**Expected pattern-detection signal.** None required. A small number of
instances may brush a fan-out/multi-hop threshold and should be reported as
low-confidence candidates.

**Expected UI evidence.** Per-entity timeline showing dense burst clusters;
evidence entries such as "382 transactions observed in 30 days — 4.2× the
cluster median" and "burst of 41 transactions within 22 minutes"; priority
medium-to-high driven by temporal behaviour, with no pattern finding attached.

---

### C. Rapid Multi-Hop Transfers

**Purpose.** Exercise the flow feature category (`docs/07`: hop count, rapid-hop
indicators, incoming/outgoing ratio) and give `docs/08` a chain candidate that is
*not* a peeling chain, so that the two detections can be separated.

**Approximate transactions.** ≈750 records; 12 instances; per instance 5–7 chains
of 5–9 hops (≈25–60 records per instance).

**Wallets involved.** 6–12 wallets per chain; mostly fresh addresses, with a few
reused across instances. Total ≈140 scenario wallets.

**IP behaviour.** Mostly one IP per hop, drawn from the normal pool, and 2–5 IPs
per chain overall. A subset of instances deliberately shares IPs with family G
(Section 9), which creates cross-scenario contamination rather than a clean
boundary.

**Timing behaviour.** 30 seconds to 10 minutes between hops; a chain completes in
under two hours. Instances are spread over 12 different days, and some run
concurrently with unrelated normal traffic.

**Amount behaviour.** 0.5–12 BTC moving forward with **near-constant value**: a
drop of ≤2 % per hop and ≤5 % across the whole chain, consistent with fees. This
is the deliberate contrast with peeling (D), where the forwarded amount falls
steadily.

**Transaction behaviour.** 78 % of hops are 1-input/1-output. Chain starts may
consume 2 inputs (funding transactions) and 22 % of hops carry a second output
(fee/change), producing near-misses that a naive peeling detector will flag.

**Graph structure.** Directed paths with occasional branching into sub-chains;
low degree per node, high directionality, short temporal span, high path
centrality on the intermediate wallets.

**Expected anomaly/ML signal.** Hop count, average inter-transaction time, rapid
hop indicators, and high chain-internal velocity while volume stays flat.
Intermediate wallets have low transaction counts overall, so they must be judged
*structurally*, not by volume.

**Expected pattern-detection signal.** Candidate multi-hop transfer chain with
hop count, hop timestamps, wallets and amounts. Some instances must legitimately
sit near the peeling threshold and be reported as low-confidence peeling
candidates (intended ambiguity).

**Expected UI evidence.** Transaction Flow listing each step with wallet, amount,
txid, timestamp and fee; evidence such as "6 hops completed in 34 minutes; value
retained 97.6 % across the chain"; anomaly score driven by flow features rather
than by value.

---

### D. Peeling-Chain Pattern

**Purpose.** Provide the primary target of `docs/08` peeling-chain detection:
repeated forward movement, one output continuing, structured amount change,
timing relevance and a chain length above a configurable threshold.

**Approximate transactions.** ≈300 records; 15 instances; 5–12 hops each.

**Wallets involved.** Per instance: 1 funding wallet, one change address per hop
(the peeling spine) and one payment address per hop. Payment addresses are
sometimes reused across instances (merchant-like receivers), which creates
clustering ambiguity on purpose. Total ≈170 scenario wallets.

**IP behaviour.** Deliberately quiet: 1–3 IPs per chain, and several instances
use one IP for every hop. Peeling must therefore be detected **structurally**,
not from network behaviour. This also means the same wallet can appear
network-normal while structurally suspicious.

**Timing behaviour.** Two tempo classes must exist: fast (hops 2–10 minutes
apart, chain finished inside 40 minutes) and slow (hops hours apart, chain spread
over up to two days). Roughly 60 % fast, 40 % slow, so that elapsed time alone
does not identify the pattern.

**Amount behaviour.** Start value 1–20 BTC. Each hop forwards a **decreasing**
amount (3–15 % reduction per hop, multiplicative) while the change output keeps
the remaining value for the next hop. Cumulative reduction reaches 30–75 % over
the chain. The terminal hop moves a small residual (0.001–0.01 BTC). 30 % of
instances instead forward a near-constant amount while accumulating value, so a
single amount signature cannot serve as the detector.

**Transaction behaviour.** ≥85 % of hops are 1-input/2-output (forward + change);
the remainder are 1-in/1-out or 2-in/2-out, providing local counterexamples.

**Graph structure.** A linear spine of change addresses with side branches to
payment addresses; spine wallets have in-degree 1 and out-degree 1–2; the
terminal payment receivers can look like dense hubs.

**Expected anomaly/ML signal.** Elevated amount-reduction structure, repeated
two-output fan-out with a continuing path, and chain-internal timing — expressed
in the flow and transaction feature categories.

**Expected pattern-detection signal.** Peeling-chain candidate with hop count,
transaction IDs, wallets, timestamps, amounts and supporting evidence, exactly as
required by `docs/08`. At least three instances must remain below the length
threshold so that the threshold is visibly configurable rather than absolute.

**Expected UI evidence.** Transaction Flow rendering the peeling sequence (for
example 4.2 → 4.0 → 3.8 → 3.6 BTC with shrinking intervals or wide gaps);
evidence entries such as "4-step peel, 14 % reduction" and "repeated change
address behaviour"; priority raised by pattern evidence with model score as a
secondary signal.

---

### E. Mixing-Like Behaviour

**Purpose.** Exercise `docs/08` mixing-like detection: multiple inputs/outputs,
similar-value transfers, repeated transaction structure and high fan-in/fan-out —
always reported as a **candidate pattern requiring analyst review**.

**Approximate transactions.** ≈420 records; 8 instances; ≈50 records per instance.

**Wallets involved.** 8–25 wallets per instance: an input pool of 5–12 and an
output pool of 8–20. Pool wallets are sometimes reused by other instances, which
weakens the clean separation between instances on purpose.

**IP behaviour.** 1 IP per wallet and 3–10 IPs per instance. In some instances a
single IP is shared by several participating wallets, which adds a network-layer
signal on top of the structural one; in others the IPs are entirely normal.

**Timing behaviour.** Consolidation and distribution happen inside windows of
5–30 minutes, usually 1–3 batches per instance, and the instance spans less than
a day. A detector only ever sees individual records, so batches must not be placed
at regular, easily-recognised intervals.

**Amount behaviour.** Inputs are of varied sizes. Outputs are split into 4–12
**similar-value** chunks (±10 % around a base chunk, often much tighter), plus
one remainder output. Total value is preserved minus the fee. Very tight equal
splits (within ±3 %) should occur in 2 instances only, so that "equal split" is a
useful feature rather than a guaranteed label.

**Transaction behaviour.** Two shapes per instance: a consolidation transaction
(fan-in, 5–12 inputs to 1 output) followed by distribution transactions (fan-out,
1 input to 6–15 outputs). 2–4 such groups per instance; some groups carry a
second output for change.

**Graph structure.** Bipartite fan-in / fan-out around one or two short-lived
central wallets; strong in-degree and out-degree spikes; dense two-hop
neighbourhoods; community structure that DBSCAN should partly recover.

**Expected anomaly/ML signal.** High in-degree and out-degree on wallets that
exist for only hours, many same-size outputs, and high volume concentrated in a
short window.

**Expected pattern-detection signal.** Potential mixing-like structure with
fan-in/fan-out counts, similar-value output evidence, participating wallets and
timestamps — phrased as "candidate pattern / requires analyst review".

**Expected UI evidence.** Transaction Flow showing the fan-in and fan-out
stages; evidence such as "1 input → 12 outputs of 0.750 ± 0.03 BTC within
9 minutes"; cluster context; priority driven mainly by the pattern finding.

**Deliberate ambiguity.** Legitimate batch-payment services produce exactly this
structure. Two of the eight instances must be generated as ordinary batch-payout
context and labelled as such (weak label strength) in ground truth — they are a
designed false positive for pattern review.

---

### F. Common-Input Wallet / Entity Cluster

**Purpose.** Provide the co-spend evidence that makes entity clustering possible
(`docs/05` common-input ownership, `docs/07` DBSCAN clustering) and that gives the
Clusters page and the `WALLET_MEMBER_OF_CLUSTER` edge something real to show.

**Approximate transactions.** ≈1,300 records; 20 instances; 6–15 co-spend
transactions per instance.

**Wallets involved.** 3–9 addresses per entity instance (a multi-address wallet
under common control), ≈190 scenario wallets overall. Each address also transacts
outward with unrelated counterparties, so no address looks inert.

**IP behaviour.** In 75 % of instances the entity's addresses are observed from
the same 1–3 IPs, adding a weak corroborating signal. In the remaining 25 % each
address uses different IPs and different countries, so clustering must succeed
from co-spend structure alone. This split is essential to prove that clustering
is not merely re-reading network data.

**Timing behaviour.** Co-spend events recur at 3–10 day intervals across the
window, with 1–4 co-spend transactions per event — regular enough to be found,
irregular enough not to be a single timestamp burst.

**Amount behaviour.** Ordinary (0.05–5 BTC). The signal is the **input count** and
the identity of the co-spending addresses, not the value.

**Transaction behaviour.** Consolidation transactions with 3–9 inputs and 1–2
outputs. Counterparty transactions keep the usual 1–3 input / 1–3 output shape.

**Graph structure.** Near-clique among the entity's addresses (co-spend edges),
each address also attached to external neighbours: high internal density, low
external density, small connected component, moderate betweenness.

**Expected anomaly/ML signal.** Entity-level graph features: degree, unique
neighbours, component size, co-spend frequency. Individually these records look
ordinary, so scores should be moderate rather than extreme.

**Expected pattern-detection signal.** None by itself. Consolidation-heavy
instances may brush the mixing-like fan-in threshold, which is intended overlap
with family E rather than a defect.

**Expected UI evidence.** Clusters page listing member wallets and the
co-spend evidence with supporting `source_record_id` values; entity detail
stating "common-input observed association — an inference about possible common
control, not proof of ownership"; timeline showing recurring co-spend events.

**Deliberate ambiguity.** 15 % of instances must be generated from ordinary
multi-address users with no other unusual behaviour, so that correct clustering
still yields a low-priority lead.

---

### G. Network/IP Anomaly

**Purpose.** Exercise the network feature category (`docs/07`: unique IP count,
unique country count, ASN diversity, IP change frequency) and provide leads whose
entity type is `ip`, so the leads list and IP evidence views are not empty.

**Approximate transactions.** ≈430 records; 10 instances; ≈40 records per
instance.

**Wallets involved.** 3–8 wallets per instance; ≈90 wallets overall.

**IP behaviour.** This is the family's core signal, with four sub-shapes:

1. **IP churn** — one wallet observed from 6–20 different IPs inside the window,
   each IP used for only 1–5 observations.
2. **Geographic dispersion** — the same wallet observed from 3–6 countries and
   4–9 ASNs within 10 minutes to 6 hours. Because all IPs are reserved/demo
   ranges with a synthetic IP→geo mapping (Section 15), "implausibility" is a
   property of that documented mapping, and the mapping file must be shipped in
   metadata so the demo can explain the finding rather than assert it.
3. **Shared endpoint** — one IP observing 40–200 unrelated wallets, with elevated
   port variety. Legitimate public hubs produce the same shape (family A), which
   is why this sub-shape must not be treated as decisive.
4. **Port behaviour** — predominantly non-`8333` destinations, unusual
   source/destination port pairs, or a repeated identical ephemeral source port
   across many observations.

**Timing behaviour.** Churn happens in bursts of 1–6 hours per instance, spread
across 10 different days. A subset of instances deliberately shares IPs with
family C hops, and one instance shares an IP with a family F cluster, so the
IP-level view genuinely cuts across other families.

**Amount behaviour.** Entirely ordinary (0.01–5 BTC). The family must be
invisible in amount features; if it were visible in amounts the network feature
category would never be exercised.

**Transaction behaviour.** Ordinary 1–2 input / 1–2 output transactions with
common script types. No structural pattern exists in this family.

**Graph structure.** Bipartite IP–wallet stars in which the IP side is large and
the wallet side small; IP nodes with high degree and many short-lived edges;
wallets that land in several otherwise unrelated components.

**Expected anomaly/ML signal.** Elevated unique-IP count, country count, ASN
diversity and IP-change frequency per wallet, and high observation count with
high wallet diversity per IP. These are the only strongly elevated features.

**Expected pattern-detection signal.** **None.** This family must not produce
peeling or mixing-like candidates; if it does, the pattern detector is
over-firing and the condition is a defect, not a success.

**Expected UI evidence.** Entity Investigation showing "observed from 6 IPs
across 4 countries within 2 hours" with the supporting records; IP entries in the
leads list with observation and wallet counts; wording must remain neutral —
"network-layer observation anomaly", never an attribution of identity or intent.

**Deliberate ambiguity.** Only 2 of 10 instances should be strongly elevated
(many IPs, many countries). The other instances must be explainable as ordinary
mobile or multi-homed use with moderate scores, so that the network features are
genuinely graded rather than binary.

---

### H. Dense Wallet Interaction Cluster

**Purpose.** Exercise graph metrics (`docs/07` graph category), community
detection, centrality, and cluster-level leads — while acting as the dataset's
main source of **high-connectivity false positives**.

**Approximate transactions.** ≈1,900 records; 6 clusters; ≈320 records per
cluster.

**Wallets involved.** 40–120 wallets per cluster; ≈520 wallets overall. Many
members also appear in family A records, so membership is not exclusive.

**IP behaviour.** Normal: each wallet observed from 1–3 IPs with an ordinary
country/ASN spread; one or two clusters share a small set of service IPs. Density
must come from the wallet graph, not from the network layer.

**Timing behaviour.** Sustained activity across the whole 30-day window with a
business-hours bias, plus a few high-volume days per cluster. Two clusters overlap
in time and share counterparties, producing ambiguous community boundaries.

**Amount behaviour.** Ordinary to moderately large, 0.01–50 BTC, including some
genuinely large legitimate transfers. High-value members of dense clusters will
appear near the top of rankings; that is intended and must be reported as an
observed characteristic, not as suspicion.

**Transaction behaviour.** 1–4 inputs and 1–4 outputs, frequent co-spend,
recurring counterparty pairs (edges with multiplicity), occasional 10+ input
consolidations by merchant-like members.

**Graph structure.** Several communities with high clustering coefficient, high
average degree, high betweenness on a few hub wallets, components of 40–120
nodes, and partial overlap between two communities.

**Expected anomaly/ML signal.** Elevated degree, unique neighbours, component
size and centrality. Members of these clusters will score above the population
median on graph features alone — the point of the family.

**Expected pattern-detection signal.** None inherent. One cluster must contain a
small embedded family-C instance, so that a real flow pattern surfaces *inside* a
legitimately dense community (contamination in both directions).

**Expected UI evidence.** Graph Investigation rendering a dense but readable
neighbourhood with node-type shapes and edge kinds; Clusters page with member
counts and behavioral tags; evidence such as "27 directly connected wallets —
top 5 % of entities by degree", phrased strictly as an observed association.

**Deliberate ambiguity.** Priority must stay mostly low-to-medium for these
clusters even though connectivity is high, because connectivity alone is not
evidence of unusual behaviour (`docs/09`).

## 8. Dataset Scale

Three scales are recommended. All three must contain **all eight scenario
families** — a smaller dataset is compressed, never simplified by dropping a
family.

### Minimum development dataset

| Property | Recommended value |
| --- | --- |
| Transactions (observation records) | 5,000 |
| Wallets | ≈1,200 |
| IPs | ≈400 |
| Countries / ASNs | ≈12 / ≈20 |
| Scenario instances | 8 families × 1–2 instances = 12 |
| Expected derived clusters | ≈15–25 |
| Time window | 7 days |
| Approximate file size | 2–4 MB CSV |
| Purpose | fast iteration, unit tests, generator and validator development |

### SIH demo dataset (recommended default)

| Property | Recommended value |
| --- | --- |
| Transactions (observation records) | ≈48,000 (acceptable range 40,000–50,000) |
| Wallets | ≈12,000 |
| IPs | ≈3,800 |
| Countries / ASNs | ≈45 / ≈90 |
| Scenario instances | ≈85 (A background + B 14, C 12, D 15, E 8, F 20, G 10, H 6) |
| Expected derived clusters | ≈150–200 |
| Time window | 30 days: 2024-11-01T00:00:00Z → 2024-11-30T23:59:59Z |
| Approximate file size | 20–30 MB CSV, ≈1.5× as NDJSON |
| Purpose | the offline SIH demonstration (`docs/15`) and end-to-end pipeline runtime |

Record allocation for the demo scale:

| Family | Records | Instances | Scenario wallets | Main elevated feature category |
| --- | --- | --- | --- | --- |
| A Normal | ≈40,900 | background | ≈10,500 | none (baseline) |
| B High velocity | ≈2,000 | 14 | ≈260 | temporal |
| C Rapid multi-hop | ≈750 | 12 | ≈140 | flow |
| D Peeling-chain | ≈300 | 15 | ≈170 | flow (structural) |
| E Mixing-like | ≈420 | 8 | ≈180 | structure |
| F Common-input | ≈1,300 | 20 | ≈190 | graph (co-spend) |
| G Network/IP anomaly | ≈430 | 10 | ≈90 | network |
| H Dense cluster | ≈1,900 | 6 | ≈520 | graph (density) |

Wallet totals overlap across families and with A, so unique wallets are lower
than the sum (≈12,000 unique).

**Why this size is practical.** ≈48,000 records is small enough to ingest, score
and render on a normal student laptop with no GPU, to keep a full analysis run in
the low-minutes range, and to fit comfortably inside the DuckDB/Parquet layout in
`docs/12`. It is also large enough for Isolation Forest and DBSCAN to work on a
non-trivial population. The order of magnitude intentionally matches the
illustrative dataset metadata in `frontend/src/mock-data` (48,521 records) so the
demo screens and the real pipeline describe a comparable corpus.

### Stress-test dataset

| Property | Recommended value |
| --- | --- |
| Transactions (observation records) | 250,000–500,000 |
| Wallets | ≈90,000 |
| IPs | ≈20,000 |
| Countries / ASNs | ≈60 / ≈200 |
| Scenario instances | each family × 8–15 → ≈600+ |
| Expected derived clusters | ≈1,200–2,000 |
| Time window | 90 days |
| Approximate file size | 150–250 MB CSV |
| Purpose | chunked-ingestion and memory tests, progress reporting, graph scale limits, prioritisation throughput |

The stress scale is a **performance exercise**, not a demo scale. It exists to
prove that ingestion streams (`docs/04`), that graph neighbourhood queries stay
responsive (`docs/06`) and that the run model in `docs/02` reports progress and
counts honestly.

## 9. Scenario Mixing

The dataset must never be structured as "100 normal records, then 100 anomalous
records". A block-structured corpus leaks its labels through row order, time
range and file position, and it produces a demonstration that proves nothing.

### Required mixing behaviour

1. **Chronological interleaving.** Records from all families are merged and
   sorted by `timestamp`. Scenario records are scattered between background
   records and never form contiguous blocks.
2. **Temporal overlap.** Instances of different families run concurrently — for
   example a peeling chain on days 3–4 while a velocity burst, a mixing batch and
   a dense cluster are active. Peak days carry several families plus heavy
   background traffic.
3. **No positional signal.** Nothing about `source_record_id` or file position
   may correlate with a family label. `source_record_id` is assigned on the
   merged, sorted output, not per family.
4. **Shared entities.** Roughly 60 % of scenario instances share at least one
   wallet with family A activity, and ≈10–15 % of scenario wallets also carry
   ordinary background transactions during the window.
5. **Cross-family intersections.** Deliberate overlaps, each documented in
   ground truth so it can be investigated honestly:
   - C and G share a subset of IPs (hops observed from churning IPs);
   - H contains one embedded C instance;
   - F consolidation transactions can brush E's mixing-like thresholds;
   - E pool wallets are partly reused by other E instances;
   - D payment receivers are reused across D instances (merchant-like).
6. **Neighbour noise.** Many background wallets sit exactly one hop away from
   scenario wallets. Any graph-based detector will include legitimate neighbours
   in the flagged neighbourhood. This is realistic and must not be "cleaned up".
7. **Continuous traffic inside instances.** During a peeling chain or a mixing
   batch, unrelated background records appear between the scenario records, so a
   naive "inspect consecutive rows" strategy fails and windowed features are
   required.
8. **Benign extremes.** Family A must contain legitimate wallets that are extreme
   on single features (very high amount, very high degree, very high velocity,
   high IP diversity). These are the calibration points for honest precision
   reporting (Section 11).

### Anti-triviality audit

The generator must include a **label-separation audit** over the merged dataset,
using ground truth offline, for dataset tuning only:

- No single raw field should separate scenario records from background at very
  high accuracy. As a rule of thumb, the best single-feature separation must stay
  well below a near-perfect threshold; anything close to perfect means the
  scenario parameters are too extreme and must be softened.
- Simple derived features (input count, output count, fee, port, script type,
  country, single-record amount) must also remain weak individually. Real
  separation should require combinations, aggregates and graph structure.
- If the audit fails, the fix is to change generator parameters — widen amount
  distributions, reduce IP diversity, add counterexamples inside the scenario —
  **never** to hide records or weaken ground truth.

### Why mixing improves realism

Mixed data forces the pipeline to earn its results: features must be computed
over rolling windows, entity aggregation and graph neighbourhoods; thresholds must
be justified against a real distribution; and false positives become visible and
explainable. It also makes the demonstration honest, because an analyst sees
normal-looking neighbours around flagged entities and therefore learns what
"evidence" means in this system.

### Why mixing improves evaluation

Because families overlap and contaminate one another, scenario-level recall and
precision can be measured under realistic ambiguity, and the classic synthetic
dataset failure mode — "the model learns the generator instead of the behaviour" —
is directly discouraged.

## 10. Ground Truth Metadata

### Principle

Ground truth describes **generator intent** — which family produced a record and
what a correct detector ought to notice. It is not truth about human behaviour,
ownership or wrongdoing, and it is stored completely separately from the
ingestible dataset.

### Files

| File | Level | Purpose |
| --- | --- | --- |
| `metadata/scenario_labels.csv` | record (`source_record_id`) | Family, instance and role per record; primary evaluation join key. |
| `metadata/entity_labels.csv` | wallet / address | Expected group, instance membership and role per wallet. |
| `metadata/instance_catalog.csv` | scenario instance | One row per instance: family, time span, hop count, wallet count, record count, IP pool, parameter snapshot, label strength. |
| `metadata/anti_triviality_audit.json` | dataset | Single-feature separation audit results (Section 9) recorded per dataset version. |
| `metadata/dataset_manifest.json` | dataset | Seed, versions, counts, config hash, ground-truth file hashes. |

### Record-level ground truth (proposed columns)

| Column | Example | Meaning |
| --- | --- | --- |
| `source_record_id` | `R00004217` | Join key into the dataset. |
| `txid` | 64-hex | Convenience join key. |
| `scenario_family` | `D` | `A`–`H`, or `A` for background records. |
| `scenario_instance_id` | `D-07` | Empty for background. |
| `ground_truth_role` | `scenario_core` | One of: `background`, `scenario_core`, `scenario_support`, `shared_neighbour`, `benign_extreme`, `intersect_other_family`. |
| `label_strength` | `strong` \| `weak` | `weak` marks intentionally ambiguous instances (e.g. the two benign batch-payout instances in E, the moderate G instances). |
| `expected_signals` | `flow,temporal` | Pipe-separated feature categories that should be elevated. |
| `expected_pattern_kind` | `peeling` | `none`, `peeling`, `mixing_like`, `multi_hop`, `fan_in`, `fan_out`. |
| `contamination_note` | `shares_ip_with_G-03` | Free-text note describing deliberate contamination. |

`txid` may appear in several rows with different roles (for example a
`scenario_core` hop and a `background` observation of the same transaction from a
public endpoint). Evaluation must therefore decide per task whether it joins at
record level or at transaction level, and must document that choice.

### Entity-level ground truth (proposed columns)

`address`, `expected_group` (the instance or entity group a wallet belongs to),
`group_kind` (`common_input_entity`, `scenario_instance`, `dense_community`,
`benign_pair`, `none`), `family`, `role`, `label_strength`, `ip_behaviour_class`
(`stable`, `multi_ip`, `churning`), `expected_elevated_features`.

`expected_group` exists for evaluation of clustering only. It must never be used
as a clustering input, and a derived cluster is allowed to disagree with it — the
disagreement is a finding, not an error to hide.

### Preventing data leakage

These rules are mandatory:

1. **Physical separation.** Ground truth lives under `metadata/` (and evaluation
   artifacts under `validation/`). It is never placed in `raw/` or `generated/`,
   and it is never part of a dataset upload. Ingestion reads only the registered
   dataset file(s).
2. **No label-derived fields in the schema.** The canonical schema (Section 2)
   contains no `is_anomaly`, `scenario`, `label`, `score` or `cluster` field, so
   a leak is impossible through the data contract itself.
3. **Schema mismatch as a guard.** Ground-truth files use different column names
   and sets than the canonical schema, so a mistaken ingestion attempt fails
   validation with "unsupported columns" instead of silently succeeding.
4. **Generation order.** The generator writes and validates the dataset first,
   then derives ground truth from the same in-memory scenario bookkeeping. Labels
   must never influence record values, `source_record_id` assignment, ordering or
   deduplication.
5. **Code separation.** Feature engineering, model fitting and pattern detection
   must not be able to read ground-truth files. Evaluation lives in a separate
   module/step that runs after an analysis run completes, and the run manifest
   records the exact input list and feature-column hash so a reviewer can verify
   that no label column was present.
6. **API separation.** The API in `docs/10` never returns ground-truth fields;
   model findings are served without reference to generator intent. Ground truth
   is for the team's offline evaluation and reports, not for the analyst
   interface.
7. **No post-hoc editing.** Once a dataset version is fingerprinted, its labels
   are frozen with it. Corrections require a new dataset version, so that an
   evaluation result always corresponds to one immutable artifact.

## 11. Unsupervised ML Evaluation

### Primary detector

The first working detector is **unsupervised** (`docs/07`): Isolation Forest over
entity-level and transaction-level feature tables, with DBSCAN used for
clustering. No supervised classifier is trained, because no reliable labels exist
in a real investigation.

### Rule

Scenario labels are used **only after** scoring, in a separate evaluation step,
to interpret what the unsupervised ranking did. They are never used to fit,
select features for, or tune the model that produces the scores. If any
hyperparameter is chosen with reference to labels, the evaluation report must say
so explicitly and mark the resulting metrics as optimistic.

### What to measure

1. **Anomaly ranking.**
   - Top-k analyses for several `k` (for example top 50 / 100 / 500 records, and
     top 1 % / 5 % of entities), reported as counts, not as a single number.
   - Rank position of `scenario_core` records and entities (median and
     90th-percentile percentile rank).
   - **Base rate first.** Scenario records are only a few percent of the corpus,
     so every precision figure must be accompanied by the base rate and by an
     enrichment factor relative to random selection. A top-5 % selection that
     captures 30 % of scenario instances is informative; "40 % precision" over a
     6 % base rate is informative too, but only when stated together.
2. **Scenario-level detection.** An instance counts as detected when at least one
   of its `scenario_core` wallets appears above the reporting threshold. Report
   detected/total per family, because families are far from equally detectable —
   D and E are structural and should be easier than G's moderate instances.
3. **Cluster evaluation.** Cluster count and size distribution (`docs/07`
   validation), purity of derived clusters against `expected_group`
   (`docs/10`), and ARI/NMI only where the ground-truth grouping is meaningful
   (families F and H). Clustering must be reported as grouping of *observed
   behavior*, never as proven common ownership.
4. **Pattern-level evaluation.** For peeling candidates: count of candidates,
   share belonging to D, and share belonging to A/C/E (expected near-misses).
   Report both recall on D instances above the chain-length threshold and the
   behaviour of the below-threshold instances, so the threshold is visibly
   justified.
5. **False positives.** Enumerate the top-ranked background entities and classify
   the cause using ground truth: `benign_extreme`, dense-cluster member,
   `shared_neighbour`, family B/C near-miss, IP-hub wallet. Report counts per
   cause. A detector whose false positives are dominated by a single explainable
   cause is easier to defend than one whose false positives are arbitrary.
6. **False negatives.** List the scenario instances with no entity above the
   threshold, with the reason from the instance catalog (slow tempo, short chain,
   low IP diversity, ordinary amounts, chain length below threshold). Some false
   negatives are expected and must be reported, not tuned away.
7. **Manual evidence inspection.** For every lead chosen for the demo
   (`docs/15`), confirm by hand that the evidence chain resolves to real
   `source_record_id` values in the dataset and that the described signals exist
   in the underlying records. A lead whose evidence cannot be traced is a defect,
   regardless of its score.

### Realistic expectations

- Unsupervised detection on deliberately overlapping data will produce
  substantial false positives. That is the correct outcome for a dataset built
  this way, and it is why prioritisation (`docs/09`) says "investigation
  priority" rather than probability of wrongdoing.
- Entity-level and scenario-level metrics will generally look far better than
  record-level precision. Report both levels and never present only the
  flattering one.
- Absolute thresholds are less meaningful than relative ranking. Prefer
  statements such as "the top 100 ranked entities contained 9 of the 15 peeling
  instances" over generic accuracy claims.
- No accuracy, ROC-AUC or F1 figure may be quoted for a model that was not
  trained on labels. The prototype reports score distributions, ranking
  statistics, cluster statistics and post-hoc association with ground truth, as
  `docs/07` "Validation" requires.
- The output is a **ranked set of leads flagged for review**, with evidence.
  Nothing in the evaluation may be worded as proof of criminality.

### Evaluation artifact

The evaluation step writes `validation/eval_report.json` containing: dataset
version and fingerprint, analysis run ID, model and configuration versions,
random seed, threshold values actually used, the metrics above, and the exact
ground-truth file hashes used. Without these fields an evaluation result is not
reproducible and must not be reported.

## 12. Reproducibility

`PROJECT.md` principle 7 requires deterministic pipelines and versioned analysis
runs. The dataset must therefore be reproducible from a small, explicitly stored
set of inputs.

### Random seed

- One **master integer seed** controls all randomness. Default: `26146` (the SIH
  problem-statement number) so the default dataset is deterministic for everyone.
- The seed is declared in the generator configuration, reported in
  `metadata/dataset_manifest.json`, and printed by the generator.
- A different seed may be passed explicitly for variation, but then every
  produced artifact must record the seed that produced it. An artifact without a
  recorded seed is invalid.

### Deterministic generation

The future generator must obey:

1. **Derived sub-seeds, no shared global state.** Each stage and each scenario
   instance derives its own generator from the master seed and its own
   identifier (for example a hash of `master_seed`, stage name and instance ID).
   Adding a new instance must not change previously generated instances.
2. **No iteration-order dependence.** Never iterate over `set` or unordered
   `dict` when output order matters; sort keys explicitly. Never depend on hash
   randomisation.
3. **No wall-clock or environment dependence.** Record timestamps come from the
   scenario configuration, never from the current time. No locale-sensitive
   formatting; decimals, dates and separators are formatted explicitly.
4. **Stable sorts and stable ID assignment.** Merge all records, sort by
   `timestamp` with `source_record_id` as tiebreaker, then assign
   `source_record_id` in that order.
5. **Deterministic numeric handling.** Use fixed rounding at a single defined
   point (8 decimals for BTC) and avoid order-dependent floating-point
   accumulation; prefer integer satoshi arithmetic internally and format to BTC
   on output.
6. **Byte-identical regeneration check.** Running the generator twice with the
   same seed and configuration must produce byte-identical files. A SHA-256
   comparison of the regenerated dataset is part of generator acceptance.

### Versions

| Version | Meaning |
| --- | --- |
| `dataset_version` | Semantic version of the produced dataset (`1.0.0` initially). Any change to schema, seed, scenario parameters or generator behaviour that alters output requires a new version. |
| `schema_version` | Version of the canonical schema in Section 2 (`1` initially). Independent of the dataset version. |
| `generator_version` | Version of the generator code (`0.1.0` initially), plus the source revision if available. |

The dataset filename embeds the dataset version, for example
`synthetic_traffic_v1.0.0.csv`, so two versions can never be confused in a demo.

### Scenario configuration

All generation parameters live in one configuration artifact
(`metadata/generator_config.json`): per-family instance counts, amount
distributions, timing distributions, chain lengths, IP pool sizes, contamination
rates, label-strength assignments and any thresholds used by the audit. The
dataset must be reproducible from **seed + configuration + generator version**
alone. Nothing may be tuned by editing code silently.

### Fingerprint and manifest

- `metadata/dataset_fingerprint.txt` holds the SHA-256 fingerprint computed over
  the canonical per-record serialization plus the configuration hash.
- `metadata/dataset_manifest.json` holds: dataset version, schema version,
  generator version, master seed, configuration hash, record counts, entity
  counts, family and instance counts, ground-truth file hashes, the generation
  timestamp, and the fingerprint.
- Analysis runs reference the dataset ID, the dataset fingerprint and the code
  and model versions, as required by `docs/12` "Reproducibility". A run whose
  fingerprint does not match the registered dataset must be rejected rather than
  silently recomputed.

### What reproducibility does not mean

Reproducibility of the *synthetic dataset* is not a claim that analysis results
generalise to real Bitcoin traffic. It only guarantees that the same corpus can be
rebuilt and that a demonstration or evaluation can be replayed exactly.

## 13. Data Quality Rules

### Framework

- **Levels.** `ERROR` = record is invalid; it is moved to a quarantine set with a
  reason code and counted, and is **never silently discarded** (`docs/03`). It
  may not be fed to feature engineering. `WARNING` = record is accepted but
  flagged and counted. `INFO` = recorded statistic.
- **Rule IDs.** Each rule has a stable ID (`TS-01`, `IP-03`, …) so validation
  output can reference it and tests can assert on it.
- **Demo expectation.** The demo dataset must produce **zero ERRORs** and only a
  small, intentional set of WARNINGs (the ones this specification designs for). A
  separate invalid-sample fixture (Section 16) exists to exercise ERROR paths
  deliberately.
- **Outputs.** Validation writes `validation/validation_report.json` (rule-level
  counts, quarantine reasons, per-field statistics) and
  `validation/field_quality.json` in the shape the frontend already expects for
  dataset quality (`frontend/src/types/index.ts`: `field`, `coverage`, `invalid`,
  `status`).
- **Never reject a whole file silently.** A file that fails structurally is
  reported with counts and reasons; partial validity is always described.

### Timestamp rules

| ID | Level | Rule |
| --- | --- | --- |
| TS-01 | ERROR | `timestamp` matches exactly `YYYY-MM-DDTHH:MM:SSZ` (ISO 8601, UTC, second precision, no fractional seconds, no offset other than `Z`). |
| TS-02 | ERROR | `timestamp` lies inside the configured dataset window (demo: 2024-11-01T00:00:00Z → 2024-11-30T23:59:59Z). |
| TS-03 | WARNING | A later record reuses the exact tuple (`src_ip`, `dst_ip`, `txid`, `timestamp`) already present — a duplicated observation rather than a legitimate second observation. |

### IP address rules

| ID | Level | Rule |
| --- | --- | --- |
| IP-01 | ERROR | `src_ip` and `dst_ip` are well-formed IPv4 dotted quads: four octets, each 0–255, no leading zeros, no whitespace. |
| IP-02 | ERROR | Both IPs fall inside an approved reserved/documentation block (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) per Section 15. |
| IP-03 | ERROR | `src_ip != dst_ip`. |
| IP-04 | INFO | IPs are always the *observing* endpoints; an IP must never be borrowed from an input/output address field or vice versa. |

### Port rules

| ID | Level | Rule |
| --- | --- | --- |
| PT-01 | ERROR | `src_port` and `dst_port` are integers in the range 1024–65535. |
| PT-02 | ERROR | Each record's network class is internally consistent: `8333` (mainnet P2P) and `18333` (testnet P2P) must not be mixed inside one scenario instance, and a synthetic instance must declare which class it uses. |
| PT-03 | WARNING | `dst_port` is outside the approved set `{8333, 18333, 8332, 18332}`. This is permitted **only** for the family-G port-anomaly shape and must be counted, so the anomaly is visible at validation time rather than only to the model. |

### TXID rules

| ID | Level | Rule |
| --- | --- | --- |
| TX-01 | ERROR | `txid` matches `^[0-9a-f]{64}$` (64 lowercase hex characters, no truncation, no ellipsis). Display truncation such as `a1b2c3d4…e5f6a7b2` is a UI concern and must never appear in the dataset. |
| TX-02 | ERROR | All records sharing a `txid` carry **identical** blockchain-layer fields (`input_addresses`, `output_addresses`, `input_amounts`, `output_amounts`, `fee`, `script_type`). A conflicting duplicate is a generator defect. |
| TX-03 | WARNING | A `txid` is observed by more than the configured maximum number of distinct IPs (default 8), or observed from more than a configured number of countries. Legitimate public propagation is expected; the count is reported. |
| TX-04 | INFO | `txid` is **not** unique per record and must not be treated as the record key. Only `source_record_id` is a record key. |

### Wallet identifier rules

| ID | Level | Rule |
| --- | --- | --- |
| WA-01 | ERROR | Every address matches `^bc1q[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{38}$` — lowercase, bech32 charset, format-plausible (42 characters). One address format is used for the whole dataset so that no script-type hypothesis can be read from address shape. |
| WA-02 | ERROR | No generated address appears in the published-example denylist, and no address is derived from real key material. The denylist must include the placeholder addresses used in `frontend/src/mock-data`, so mock and dataset addresses can never be confused. On collision the generator regenerates deterministically. |
| WA-03 | WARNING | The same address appears more than once inside one `input_addresses` array. Permitted (separate spend entries can belong to one address) but counted, because co-spend deduplication and clustering depend on it. |
| WA-04 | INFO | An address's first appearance in the window defines its "first seen". Addresses are not reused across dataset versions unless the version reuses the same seed and configuration. |

### Amount and fee rules

| ID | Level | Rule |
| --- | --- | --- |
| AM-01 | ERROR | Amounts and `fee` are finite decimal numbers with at most 8 decimal places, `>= 0`, never `NaN`/`Infinity`, and never in exponent notation. |
| AM-02 | ERROR | Every `input_amounts[i] > 0` and every `output_amounts[j] > 0`, except an output declared as an `OP_RETURN` data output, which must be exactly `0` and must be the final element of `output_amounts`. |
| AM-03 | ERROR | No single amount and no per-record total exceeds 21,000,000 BTC, and no amount is formatted with more precision than the dataset's 8 decimals. |
| AM-04 | ERROR | `sum(input_amounts) > sum(output_amounts)` — a record may never create value. |
| AM-05 | ERROR | `fee == sum(input_amounts) - sum(output_amounts)` within a tolerance of `1e-8`. |
| AM-06 | WARNING | `fee == 0`. Allowed and counted, but it must be rare; a concentration of zero-fee records indicates a generator arithmetic error. |
| AM-07 | WARNING | `fee / sum(input_amounts) > 5 %` — an implausible fee ratio that should not occur in this dataset. |
| AM-08 | INFO | Fee statistics per script type and per scenario family are recorded, so arithmetic drift in the generator is detectable. |

### Array rules

| ID | Level | Rule |
| --- | --- | --- |
| AR-01 | ERROR | `len(input_addresses) == len(input_amounts)`. |
| AR-02 | ERROR | `len(output_addresses) == len(output_amounts)`. |
| AR-03 | ERROR | `1 <= len(input_addresses) <= 64` and `1 <= len(output_addresses) <= 64`; empty arrays are invalid in the demo dataset. |
| AR-04 | ERROR | Positional correspondence survives a serialization round-trip: CSV → record → CSV and CSV → NDJSON → CSV are byte-identical, and pairing address `i` with amount `i` is stable. |
| AR-05 | ERROR | Array fields are well-formed JSON arrays of strings (addresses) and numbers (amounts), in the documented order, with no whitespace and no trailing commas. |

### Duplicate rules

| ID | Level | Rule |
| --- | --- | --- |
| DU-01 | ERROR | No two records are identical across all 14 data fields (everything except `source_record_id`). Generation must deduplicate on the observation tuple. |
| DU-02 | WARNING | Two records share (`src_ip`, `dst_ip`, `txid`) with different timestamps less than 60 seconds apart — permitted (propagation-like) and counted. |
| DU-03 | ERROR | `source_record_id` values are unique, contiguous and zero-padded; an ID collision or a gap is a generator defect. |

### Missing and impossible value rules

| ID | Level | Rule |
| --- | --- | --- |
| MV-01 | ERROR | Every one of the 15 fields is present and non-empty in every demo record. There is no "unknown" or "n/a" value. |
| MV-02 | WARNING | A field equals a placeholder-like value (`unknown`, `N/A`, `ZZ`, a zero amount, an empty string) — must not occur in the demo dataset; counted as a quality signal for imported files. |
| MV-03 | ERROR | Impossible combinations are rejected: `src_ip == dst_ip`; identical input and output address sets with identical amounts and zero fee; a `script_type` outside the seven allowed enum values; negative values anywhere. |

### Relationship consistency rules

| ID | Level | Rule |
| --- | --- | --- |
| RP-01 | WARNING | An input address has no earlier output inside the window ("boundary funding"). Expected, because the corpus is a 30-day window rather than a complete chain history; the count must be reported because it bounds realistic linkage. |
| RP-02 | ERROR | For an address that is **not** boundary-funded, the sum spent by its inputs may never exceed the sum of its unspent in-window outputs at that moment. |
| RP-03 | ERROR | For an address that is **not** boundary-funded, it may never appear as an input before its first output record. |
| RP-04 | WARNING | An input and output address set fully overlap (change returned to a spent address). Allowed, counted, neutral for detection. |
| RP-05 | INFO | Edge-creation statistics (IP-observed-transaction, transaction-input-wallet, transaction-output-wallet, wallet-connected-wallet) are recorded, and every edge must resolve to at least one `source_record_id`. |

### Generation-side rules

| ID | Level | Rule |
| --- | --- | --- |
| GQ-01 | ERROR | The synthetic IP → (`geo_country`, `asn`) mapping is a total, stable function over the whole dataset: one IP never maps to two countries or two ASNs. The mapping table is written to `metadata/` so that offline enrichment results can be compared against it (`docs/13`). |
| GQ-02 | ERROR | The merged dataset passes the anti-triviality audit (Section 9); results are written to `metadata/anti_triviality_audit.json`. |
| GQ-03 | ERROR | Output ordering is `timestamp` ascending with `source_record_id` as the tiebreaker, and IDs are assigned after ordering. |
| GQ-04 | ERROR | No value depends on the current wall-clock time, the machine locale or the file system. Regeneration must be byte-identical (Section 12). |

### Consistency equations

The validator must be able to assert these directly:

```text
len(input_addresses)  == len(input_amounts)
len(output_addresses) == len(output_amounts)
sum(input_amounts)    == sum(output_amounts) + fee          (± 1e-8)
fee                   >= 0
input_amounts[i]      >  0
output_amounts[j]     >  0        (except a final OP_RETURN output, exactly 0)
src_ip                != dst_ip
1024                  <= src_port, dst_port <= 65535
timestamp             within [window_start, window_end]
```

### Validation outputs

| Artifact | Contents |
| --- | --- |
| `validation/validation_report.json` | Per-rule counts (pass/fail/quarantine), quarantine reason codes, structural parse results, total records seen vs accepted vs quarantined. |
| `validation/field_quality.json` | Per-field coverage, invalid count and status (`good` / `warning` / `critical`) — the shape the Dataset page already expects. |
| `validation/scenario_coverage.json` | Record and instance counts per family and per instance, label-strength counts, contamination cross-references. |
| `validation/duplicate_report.json` | Duplicate-record, duplicate-observation and duplicate-`source_record_id` results. |
| `validation/eval_report.json` | Produced later by the evaluation step (Section 11), not by generation. |

### What is deliberately not required

The dataset does not attempt to be a valid Bitcoin protocol implementation, and
validators must not impose protocol rules the documentation does not require. In
particular:

- address checksums do not need to verify, because addresses are synthetic;
- `script_type` does not need to be derivable from address prefixes;
- `OP_RETURN` payload contents are not modelled beyond a zero-amount output;
- coinbase transactions (input-less) are excluded by design, so
  "every record has at least one input" is a dataset convention rather than a
  protocol claim;
- block heights, confirmations, sequence numbers, locktimes and UTXO-set
  consistency outside the 30-day window are out of scope.

These exclusions are recorded as assumptions in Section 18 so no future
implementation invents them by accident.

## 14. Synthetic Data Realism

Realism here has one purpose: to make ML and graph analysis meaningful. A dataset
that is easy to separate is worthless for the demo, and a dataset with uniform
noise teaches the pipeline nothing. The generator must actively build in the
following properties.

### Background normal traffic

- Background is the majority of the corpus (≈85 %) and is generated first; all
  scenario families are then embedded *inside* it.
- Daily volume varies (±35 % day to day, with some days roughly twice as busy),
  there are quiet overnight hours, and both weekends and a few high-activity days
  exist.
- Traffic is never uniformly spread: activity clusters into working hours and
  into exchange-like batch windows.

### Temporal variation

- Arrival processes are Poisson-like with a diurnal envelope, not evenly spaced.
- Natural bursts exist in normal data (5–15 transactions inside 10 minutes for
  ≈8 % of wallets) and natural gaps exist inside scenario instances.
- Observation spread for a single `txid` ranges from sub-second to several
  minutes, mirroring propagation across peers.

### Amount variation

- Amounts are log-normal with median ≈0.05 BTC and a tail to ≈40 BTC in normal
  data; each family may shift the median but must keep overlapping support.
- Round-number amounts (0.1, 0.5, 1, 2.5, 10 BTC) appear naturally, as do
  exchange-like sweeps and dust-like outputs (0.0001–0.001 BTC).
- Fees vary with input count and script type (more inputs, higher fee) plus
  noise, so fee is informative but never decisive.

### Repeated IPs

- Public endpoints observe hundreds of unrelated wallets over many days.
- NAT-like reuse (many wallets behind one IP) and mobile-like reuse (one wallet
  across several IPs) both exist in normal traffic.
- Low-diversity, single-IP wallets also exist, so high IP diversity is not a
  general property of the corpus.

### Repeated wallets

- Service-like wallets (merchants, exchanges-like hubs) appear as outputs
  repeatedly, creating recurring counterparties and repeated edges.
- One-time and change addresses dominate by count, so address reuse is
  heavy-tailed rather than uniform — this is what makes co-spend clustering
  interesting.

### Multi-input and multi-output transactions

- Present in normal data (22 % multi-input, 31 % multi-output in family A) so
  that these shapes are not automatically anomalous.
- Consolidations with 8–12 inputs occur legitimately, which is exactly why
  fan-in alone may not be treated as mixing evidence.

### Overlapping behaviour

- Scenario records are interleaved with background records (Section 9), share
  IPs across families, and share wallets with background activity.
- Neighbour wallets one hop away from scenario wallets are normal and stay in the
  dataset.

### Realistic graph density variation

- Target ranges for the demo scale: mean wallet degree ≈5–10 over wallet↔transaction
  incidences (~1.4 inputs and ~1.5 outputs per unique transaction, ≈30,000 unique
  transactions, ≈12,000 wallets), with a heavy tail;
  local clustering coefficient from ≈0.02 in sparse background to >0.3 inside
  dense communities; connected components ranging from 2 nodes to a few hundred;
  maximum chain depth bounded (≈14 hops) so the UI can render any neighbourhood.
- No single component may contain the whole graph: the largest component should
  stay in the low hundreds of wallets, so that focused subgraph queries
  (`docs/06`) remain practical and the "avoid sending the entire graph to the
  browser" rule is respected.
- Dense and sparse periods must both exist in time, so that windowed features have
  variance to work with.

### Script type and structural variety

- All seven `script_type` values appear, with the newer types (`P2WPKH`, `P2TR`)
  more frequent in later parts of the window and older types (`P2PKH`, `P2SH`)
  more frequent early, creating a mild realistic drift.
- Output counts of 1–3 dominate; 4+ outputs occur in payouts and mixing-like
  batches only.

### Guardrails

All realism must remain inside the rules of Section 13. Realism is never a reason
to accept an inconsistent fee, an impossible IP, a duplicate record, or an amount
that exceeds the supply bound. If a realism requirement conflicts with a data
quality rule, the quality rule wins and the realism parameter is adjusted.

## 15. Privacy and Safety

The following statements are absolute requirements of the dataset:

1. **All wallet identifiers are synthetic.** Every address is generated by the
   generator, is not derived from any real key, seed, wallet, exchange or service,
   and must pass the published-example denylist check (WA-02). No real address,
   including any address appearing in this repository's frontend mock data, may
   appear in the dataset.
2. **All IP addresses are synthetic, reserved or documentation identifiers.**
   Only `192.0.2.0/24`, `198.51.100.0/24` and `203.0.113.0/24` (RFC 5737
   documentation ranges) and `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
   (RFC 1918 private ranges) are used. The dataset contains IPv4 only.
3. **All geographic and ASN values are synthetic assignments.** `geo_country`
   and `asn` come from a fixed, published-in-metadata IP→geo mapping table. ASNs
   must use private/reserved ASN numbering (e.g. the `AS64512`–`AS65534` private
   range) with clearly fictional organisation names, and must not reuse real
   organisations' names or real network allocations. The mapping is for
   exercising `docs/13` enrichment and geographic features, not a claim about any
   real host.
4. **No real investigative target is represented.** No real person,
   organisation, case, exchange, service or known-illicit cluster is modelled,
   named or implied.
5. **No real private information is included.** There are no names, accounts,
   identifiers, credentials, communications, or any personal data of any kind.
6. **No live interception data is used.** Nothing is captured from networks,
   nodes, peers or block explorers; generation is entirely offline and
   self-contained.
7. **No criminality claim is attached to any entity.** Scenario families describe
   *behavioural shapes* (velocity, chaining, co-spend, density, IP churn), never
   actors. Ground truth records generator intent, not allegations.
8. **Terminology is constrained.** All dataset-derived UI text, evidence
   descriptions and reports must use the neutral vocabulary of `docs/01`,
   `docs/09` and `docs/15` ("flagged for review", "anomalous", "candidate
   pattern", "observed association") and must never assert illicit activity.

If a future requirement appears to need real data, it must be raised as a
blocker rather than satisfied by adding real identifiers to this dataset.

## 16. Dataset Directory Structure

The following structure is **proposed and is NOT created by this document**. No
directory or file under `datasets/` exists at the time of writing.

```text
D:\A_SIH\prototype\datasets\
  raw\
    synthetic_traffic_v1.0.0.csv          # frozen source corpus (demo input)
    synthetic_traffic_v1.0.0.ndjson       # same records, NDJSON form
    sample_records_v1.0.0.json            # small human-readable sample
    invalid_samples_v1.0.0.csv            # validation fixture (never demo input)
  generated\
    synthetic_traffic_v1.0.0.csv          # fresh generator output
    synthetic_traffic_v1.0.0.ndjson
    sample_records_v1.0.0.json
  validation\
    validation_report.json
    field_quality.json
    scenario_coverage.json
    duplicate_report.json
    eval_report.json                      # written by the evaluation step
  metadata\
    dataset_manifest.json
    generator_config.json
    scenario_labels.csv
    entity_labels.csv
    instance_catalog.csv
    ip_geo_mapping.csv
    anti_triviality_audit.json
    dataset_fingerprint.txt
```

### Why the folders are separated

- **`raw/`** is the frozen corpus that demos and tests run against. It is
  treated as an input and is never edited by hand.
- **`generated/`** receives fresh output from the generator. Running the
  generator must produce files byte-identical to `raw/`; any difference is a
  determinism defect (Section 12) or a legitimate version bump.
- **`validation/`** holds machine-readable reports only, never dataset records.
- **`metadata/`** holds ground truth, the configuration, the IP→geo mapping and
  the manifest. Nothing here is ever ingested or served by the API
  (Section 10).
- **`invalid_samples_v1.0.0.csv`** exists so validation ERROR paths can be tested.
  It must never be registered as a demo dataset, and it is excluded from all
  counts in the manifest.

### Relationship to the existing storage layout

`docs/12` defines the backend storage layout:

```text
data/
  raw/ normalized/ derived/ graph/ runs/ reports/ app.sqlite
```

That layout describes where a **registered** dataset is staged and where pipeline
output lives. `datasets/` is a different concern: it is the corpus-authoring and
ground-truth area, upstream of dataset registration. The intended flow is:

```text
datasets/raw/…            (corpus + metadata + ground truth)
        │  register/upload (POST /api/v1/datasets/upload)
        ▼
data/raw/<dataset_id>/…   (staged copy, fingerprint recorded)
        ▼
data/normalized, derived, graph, runs, reports
```

No change to `docs/12` is required for this; the two trees serve different stages.

## 17. Future Dataset Generator

**Not implemented.** This section specifies what a future generator must do; no
Python file, dependency or directory is created by this document.

### Responsibility

The generator is an **offline development tool**, not part of the analysis API
runtime (`docs/02`). Its only job is to produce the corpus, its ground truth and
its reports deterministically, so that the backend, ML, graph and pattern stages
have a stable corpus to work against.

### Required steps

1. **Initialise the deterministic random seed.** Read `generator_config.json`,
   take the master seed (default `26146`), and derive per-stage and per-instance
   sub-seeds. Refuse to run if the configuration contains no explicit seed.
2. **Create entities.** Generate the address pool (format-plausible synthetic
   `bc1q…` addresses with denylist checks), the IP pool restricted to approved
   reserved ranges, the IP→(`geo_country`, `asn`) mapping with private ASN
   numbers and fictional organisation names, and the service-like wallets used
   by background traffic. No record may be created before its entities exist.
3. **Generate normal background traffic (family A).** Diurnal and weekday
   variation, log-normal amounts, 1–3 inputs/outputs typical, multi-input and
   multi-output minorities, natural bursts, repeated IPs, repeated service
   wallets and heavy-tailed address reuse.
4. **Generate scenario-specific behaviour (families B–H).** One generator routine
   per family, parameterised entirely from configuration, producing explicit
   *scenario records* and *scenario entity bookkeeping* per instance (instance
   ID, family, role, expected signals, contamination notes). Each routine must
   honour the overlap rules in Section 9 and the ambiguity requirements in
   Section 7.
5. **Combine scenarios.** Merge all families into one record stream, inject
   cross-family intersections and neighbour noise, and interleave everything with
   background records so no family occupies a contiguous block.
6. **Create ground-truth metadata separately.** After the record stream is
   finalised, emit `scenario_labels.csv`, `entity_labels.csv`,
   `instance_catalog.csv` and the audit results from the same in-memory
   bookkeeping. Ground truth must not influence record values, ordering or
   identifier assignment (Section 10, rule 4).
7. **Validate records.** Run the full Section 13 rule set, producing
   `validation_report.json`, `field_quality.json`, `duplicate_report.json` and
   `scenario_coverage.json`. Any ERROR must fail generation rather than being
   written out, because the demo dataset is required to be clean.
8. **Write CSV/JSON.** Emit the versioned CSV, the NDJSON file and the small JSON
   sample with the exact serialization rules of Sections 3 and 4. XML may be
   added later as an optional extra because `docs/04` supports it, but it is not
   required now.
9. **Produce the dataset manifest and statistics.** Emit
   `dataset_manifest.json` (versions, seed, counts, config hash, ground-truth
   hashes), `dataset_fingerprint.txt`, and `anti_triviality_audit.json`. Then
   regenerate once more and assert byte-identical output.

### Suggested future layout (not created here)

```text
tools/dataset_generator/
  cli.py                 # entry point: generate, validate, audit, fingerprint
  config.py              # configuration loading + seed derivation
  entities.py            # address / IP / geo-mapping pools
  background.py          # family A
  scenarios/             # one module per family B–H
  merge.py               # interleaving, contamination, ordering, ID assignment
  groundtruth.py         # label and catalog emission
  validation.py          # Section 13 rule set
  writers.py             # CSV / NDJSON / JSON serialization (Sections 3–4)
  audit.py               # anti-triviality separation audit (Section 9)
```

### Acceptance criteria

The generator is acceptable only when:

- the emitted dataset validates with **zero ERRORs** and only the designed
  WARNINGs;
- two consecutive runs produce byte-identical files (same seed and config);
- the anti-triviality audit shows no near-perfect single-feature separation;
- every scenario family is present with the configured instance counts, and the
  coverage report matches the manifest;
- ground truth joins cover exactly the accepted records, with no orphan
  `source_record_id`;
- no ground-truth field can reach the feature tables (verified by input listing
  and feature-column hashing);
- the demo-scale output loads in the ingestion pipeline within the expected
  runtime and memory envelope.

### Explicit non-goals

The generator must not: call any network service; download anything; consume
`frontend/` code or mock data as input; attempt to reproduce real Bitcoin chain
structure; embed supervised labels into records; or write into `data/` (the
backend staging area) directly.

## 18. Compatibility Check

### Existing Documentation Compatibility

| Document | Compatibility | Notes |
| --- | --- | --- |
| `PROJECT.md` | Compatible | Supplies the missing corpus. `PROJECT.md` says the schema must be confirmed against the actual SIH dataset; since the problem statement states the dataset is synthetic with a Nil link, this document defines that corpus explicitly and labels it as synthetic. Principles 1, 2, 4, 5 and 7 are honoured (offline, reproducible, provenance-preserving, observed-vs-derived separation, determinism). |
| `docs/01` Project Overview | Compatible | Supports the core investigative questions (unusual behaviour, related wallets, IP correlation, peeling/mixing-likeness, evidence) using only the approved neutral vocabulary. |
| `docs/02` Architecture | Compatible | Nothing added to the module list; the generator is a development tool, not a runtime module. All pipeline stages have data to process. |
| `docs/03` Data Schema | Compatible | The 14 SIH fields are reproduced exactly, and `source_record_id` is the provenance field already listed in the canonical normalized record. This document additionally fixes units, nullability, array encoding and timestamp format **for this corpus** (see conflict C1). |
| `docs/04` Ingestion Pipeline | Compatible | CSV and JSON (NDJSON) are produced; bulk scale, chunked reading and validation statistics are supported. XML support in `docs/04` is not exercised (gap C9). |
| `docs/05` Correlation Engine | Compatible | All primary correlation keys exist (`txid`, `timestamp`, `src_ip`, `dst_ip`, `src_port`, `dst_port`); repeated observations, temporal proximity and shared transaction relationships are generated by design, and exact / temporal / inferred classes are all represented. |
| `docs/06` Graph Engine | Compatible | Exactly the four node types and five edge types are produced. No new node or edge type is required; Network Observation maps to an `IP OBSERVED_TRANSACTION` edge rather than to a node. |
| `docs/07` ML Specification | Compatible | Every feature category (transaction, temporal, network, graph, flow) is derivable, and the corpus is designed to create variation in each of them. |
| `docs/08` Pattern Detection | Compatible | Peeling-chain candidates (family D) and mixing-like structures (family E) exist, with family C providing a deliberate near-miss contrast and family A providing low-confidence edge cases. |
| `docs/09` Risk & Explainability | Compatible | All lead fields are producible: entity IDs are derivable, signals and evidence map to the designed families, and `source_records` resolve to real `source_record_id` values. |
| `docs/10` API Contract | Compatible | Dataset, analysis, lead, entity, graph, pattern and cluster endpoints all have data behind them, and ground truth is never exposed (Section 10). |
| `docs/11` Frontend Integration | Compatible with one later gap | All screens have data. `DatasetPreviewRow` lacks `geo_country`/`asn` (conflict C7), which is a future frontend change rather than a dataset change. |
| `docs/12` Database/Storage | Compatible | DuckDB/Parquet analytics plus SQLite metadata are sufficient at every recommended scale; the new `datasets/` tree sits upstream of staging (Section 16). |
| `docs/13` GeoIP Offline | Compatible with a clarification | The dataset carries `geo_country`/`asn` because the SIH field list requires them, and the IP→geo mapping ships in metadata. Offline enrichment must still run and must record whether each value was supplied or enriched (conflict C3). |
| `docs/14` Reporting | Compatible | Reports can cite `source_record_id` evidence, analysis-run IDs, the dataset fingerprint and model versions. |
| `docs/15` Demo Flow | Compatible | Every demo step has material: validation counts, staged analysis, ranked leads, entity evidence, focused graph, candidate pattern, cluster, case/report. |
| `docs/16` Development Rules | Compatible | Offline (Rule 6), no fake backend (Rule 3), provenance preserved (Rule 7), typed contracts unaffected (Rule 4), neutral terminology (Rule 12), assumptions reported (Rule 10 — see Assumptions below). |

### Conflicts

| ID | Conflict | Resolution |
| --- | --- | --- |
| C1 | `docs/03` explicitly says not to assume delimiters, timestamp format, address array encoding, amount units or nullability, while this document fixes all of them. | Not a contradiction: `docs/03` protects against guessing about an unknown real corpus. Here the corpus is *defined* by us, so these are documented decisions (`docs/16` Rule 10). If real data ever appears, `docs/03` applies again unchanged. |
| C2 | `docs/12` defines a `data/` tree; this document proposes `datasets/`. | Compatible, different stages: `datasets/` is corpus authoring plus ground truth, `data/` is staging plus pipeline output. No change to `docs/12`. |
| C3 | `docs/13` derives `geo_country`/`asn` by offline enrichment, but the dataset already contains them. | Enrichment still runs. The pipeline must record the provenance of each value (`supplied` vs `enriched`) and may compare against `metadata/ip_geo_mapping.csv`. No new dataset field is added and the canonical record is unchanged. |
| C4 | Frontend mock data uses non-reserved IPs (`185.220.101.34`, `45.83.221.90`, `91.243.59.12`), real-looking ASN/organisation names (`AS14061 DigitalOcean`, `AS16509 Amazon AWS`, `AS200651 Tor Exit Relay`) and real geographic names, which conflicts with the privacy rules in Section 15. Placeholder addresses may also coincide with published example constants. | Mock data is illustrative scaffolding, not a dataset. It must not be copied into the dataset, and the WA-02 denylist explicitly includes those placeholder addresses. No frontend change is made (and none is permitted by this task); the conflict is recorded so nobody later treats mock values as corpus values. |
| C5 | Frontend mock preview rows break the fee identity (for example input `4.2` → output `4.19` with `fee 0.00012`, and input `10.0` → output `9.99` with `fee 0.00025`), because amounts are display-rounded to two decimals. | The dataset must satisfy AM-05 exactly. Display rounding that visibly contradicts the fee identity should be avoided, or the fee shown separately. That is a future UI change and is out of scope here. |
| C6 | Frontend mock dataset statistics show 48,521 records with 23 invalid records and 12 duplicates, while this specification requires zero ERRORs and zero full-record duplicates in the demo dataset. | Mock numbers are placeholders. The Dataset screen must show counts produced by the real validation report. Duplicate *observations* are permitted (DU-02) and reported honestly; full-record duplicates are forbidden (DU-01). |
| C7 | Frontend `DatasetPreviewRow` has no `geo_country`/`asn`, although `docs/03` lists them. | Later frontend change (extend the preview row type and the table) when the backend preview endpoint is implemented. Recorded, not executed. |
| C8 | The frontend restricts `script_type` to seven values, while real Bitcoin has additional output script forms. | Controlled simplification: the dataset uses only those seven values, interpreted as the dominant output script type, and MV-03 rejects anything else. This keeps the already-typed data contract unchanged. |
| C9 | `docs/04` supports XML ingestion; this specification produces CSV and NDJSON only. | Recorded gap, not a blocker: CSV and JSON satisfy the SIH requirement. XML can be added later as an optional generator output; until then XML ingestion cannot be demonstrated with this corpus. |
| C10 | This specification excludes coinbase/input-less transactions, whereas real Bitcoin includes them. | Stated assumption (A5), not a conflict: no existing document requires coinbase records, and including them would complicate the array-length rules without adding investigative value for this prototype. |
| C11 | `docs/README.md` lists documents 1–16 and does not mention this file. | Documentation follow-up: `17_SYNTHETIC_DATASET.md` should be added to the reading list. **Not applied**, because this task forbids modifying existing files. |
| C12 | `PROJECT.md` says the production ingestion schema "must be confirmed against the actual SIH dataset". | The problem statement states the dataset is synthetic with a Nil link, so there is nothing to inspect. This document is the explicit, clearly labelled substitute corpus; `PROJECT.md` remains unchanged and its warning stays valid for any future real corpus. |

### Required Schema Changes

**None.** No change is required to:

- the canonical record shape in `docs/03` — the dataset uses exactly the 14 SIH
  fields plus the `source_record_id` provenance field already documented there;
- the graph node and edge types in `docs/06` — four nodes, five edges, unchanged;
- the API contract in `docs/10` — no new endpoints or fields are needed;
- the storage layout in `docs/12` — `datasets/` is upstream of staging;
- the feature categories in `docs/07` — all are derivable from the corpus.

Recommended, **not applied** by this task (documentation only, existing files
untouched):

1. Add `17_SYNTHETIC_DATASET.md` to the reading list in `docs/README.md` (C11).
2. Add a one-line note in `docs/03` pointing to this document as the definition
   of the synthetic corpus, so a future reader does not wait for a real dataset.
3. Add `geo_country`/`asn` to the frontend `DatasetPreviewRow` type and preview
   table when the backend preview endpoint is implemented (C7); this is a
   frontend change and requires its own approval.
4. Record `supplied` vs `enriched` provenance for `geo_country`/`asn` in the
   enrichment stage (C3); this is an internal pipeline concern needing no schema
   change.
5. Optionally add an XML writer to the future generator (C9).

### Assumptions

| ID | Assumption |
| --- | --- |
| A1 | The corpus is synthetic, because the SIH problem statement declares the dataset synthetic with a Nil dataset link. No real corpus will be supplied for the prototype. |
| A2 | The dataset contains IPv4 only, restricted to RFC 5737 documentation ranges and RFC 1918 private ranges. |
| A3 | Amounts and fees are denominated in BTC with 8-decimal precision. |
| A4 | The fee identity `fee = sum(inputs) - sum(outputs)` holds for every record. |
| A5 | Coinbase/input-less transactions are excluded; every record has at least one input and at least one output. |
| A6 | All addresses use one synthetic bech32-style format (`bc1q` + 38 bech32-charset characters); checksums are not required to verify, and `script_type` is not derivable from the address. |
| A7 | `script_type` is restricted to the seven values already typed in the frontend and is interpreted as the transaction's dominant output script type. |
| A8 | `geo_country` and `asn` are synthetic assignments over reserved IPs and private ASN numbers with fictional organisation names; offline enrichment (`docs/13`) may reproduce or cross-check them but is not their only source. |
| A9 | The 15-field record is the complete dataset; no additional columns are added and all derived quantities are computed by the pipeline. |
| A10 | Ground truth is metadata-only, is never ingested, is never served by the API, and is used exclusively for post-hoc evaluation and generator auditing. |
| A11 | The 30-day window `2024-11-01` → `2024-11-30` is a demo convention chosen to align with the existing frontend mock range, not a claim about any real period. |
| A12 | `txid` values use the 64-hex format for realism only; they are synthetic and do not correspond to real hashes. |
| A13 | `source_record_id` (`R` + 8 digits) is emitted by the generator and preserved as the provenance key end to end. |
| A14 | The generator is an offline development tool, not part of the runtime API, and is not required for the system to run — only to (re)produce the corpus. |

### Implementation Readiness

**Ready for dataset-generator implementation.** The specification is complete
enough to build against:

- the canonical schema, serialization rules for CSV/JSON and provenance key are
  fully specified (Sections 2–4);
- the entity/relationship model maps cleanly onto the existing graph engine,
  requiring no new node or edge types (Sections 5–6);
- all eight scenario families have quantified targets — record counts, wallet
  counts, IP behaviour, timings, amounts, transaction shapes, graph structure and
  expected signals (Section 7);
- three scales with concrete counts and file-size expectations are defined
  (Section 8);
- mixing, contamination and anti-triviality requirements are explicit
  (Section 9);
- ground truth lives outside the ingestible corpus with leakage-prevention rules
  (Section 10);
- evaluation is defined as post-hoc, unsupervised-first and honestly reported
  (Section 11);
- determinism, seeding, versioning and fingerprinting rules are set
  (Section 12);
- a numbered, level-tagged validation rule set plus the consistency equations is
  ready to be implemented as tests (Section 13);
- realism targets, privacy constraints and the proposed directory layout are
  stated (Sections 14–16);
- the generator's required steps and acceptance criteria are enumerated
  (Section 17).

Nothing in Sections 1–17 is contradictory, and no conflict in this section
blocks generation. The optional items (C7, C9, and the documentation follow-ups
in "Required Schema Changes") can be decided later without changing the corpus
schema.

**Suggested implementation order for the follow-up task:**

1. generator skeleton: configuration, seed derivation, entity pools;
2. family A background generation;
3. families B–H, one at a time, each with its own ground-truth bookkeeping;
4. merge, interleave, order and assign `source_record_id`;
5. validation rule set (Section 13) and reports;
6. CSV/NDJSON writers and round-trip tests (Sections 3–4);
7. manifest, fingerprint and byte-identical regeneration check (Section 12);
8. anti-triviality audit and parameter tuning (Section 9);
9. only then ingest the corpus into the backend and begin feature/ML work —
   keeping the evaluation step (Section 11) separate from the pipeline.

**Explicitly out of scope for the generator task:** implementing the backend,
the ML models, the graph engine, the API or any frontend change.
