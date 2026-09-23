# 05 --- Correlation Engine

## Goal

Correlate network-layer observations with blockchain-layer transaction
and wallet information.

## Core relationships

``` text
IP observation
     |
     | observed around timestamp / network metadata
     v
Transaction
     |
     +---- input ----> Wallet
     |
     +---- output ---> Wallet
```

## Correlation keys

Primary: - TXID - timestamp - source/destination IP - source/destination
port

Secondary: - repeated observations - temporal proximity - shared
transaction relationships

The implementation must clearly distinguish: - exact correlation -
temporal association - inferred relationship

## Common-input ownership

Common-input relationships may be used as an analytical signal for
entity clustering, but should be represented as an inference rather than
proof of ownership.

## Correlation output

Each relationship should include: - source IDs - target IDs -
relationship type - evidence/provenance - timestamp where applicable -
confidence/strength where applicable
