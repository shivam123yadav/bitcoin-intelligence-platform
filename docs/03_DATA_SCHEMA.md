# 03 --- Data Schema

## Source fields required by the SIH problem statement

The stated minimum dataset fields include: - timestamp - src_ip -
dst_ip - src_port - dst_port - txid - input_addresses\[\] -
output_addresses\[\] - input_amounts\[\] - output_amounts\[\] - fee -
script_type - geo_country - asn

## Important implementation rule

The actual SIH dataset must be inspected before finalizing parser logic.

Do not assume: - exact CSV delimiters - JSON nesting - XML structure -
timestamp format - address array encoding - amount units - whether
geo_country/asn are populated - whether ports are numeric - whether
fields are nullable

## Canonical normalized transaction record

Proposed logical model:

``` text
TransactionRecord
  timestamp
  src_ip
  dst_ip
  src_port
  dst_port
  txid
  input_addresses[]
  output_addresses[]
  input_amounts[]
  output_amounts[]
  fee
  script_type
  geo_country
  asn
  source_record_id
```

Additional normalized metadata may be added only when supported by
source data.

## Data quality

Validation should record: - missing required fields - malformed
timestamps - invalid IPs - invalid ports - invalid amounts - malformed
addresses - duplicate records - inconsistent input/output array
lengths - unsupported script types - parsing errors

Never silently discard invalid records. Preserve counts and reasons.

## Provenance

Every normalized record should retain a source reference sufficient to
trace an investigation finding back to source records.
