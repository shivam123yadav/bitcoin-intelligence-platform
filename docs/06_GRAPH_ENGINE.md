# 06 --- Graph Engine

## Node types

-   IP
-   Transaction
-   Wallet
-   Cluster

## Edge types

-   IP OBSERVED_TRANSACTION
-   TRANSACTION_INPUT_WALLET
-   TRANSACTION_OUTPUT_WALLET
-   WALLET_CONNECTED_WALLET
-   WALLET_MEMBER_OF_CLUSTER

## Graph requirements

The graph engine should support: - node/edge creation - deduplication -
node metadata - edge provenance - degree calculation - neighborhood
queries - connected components - path queries - centrality metrics where
useful - export/serialization for frontend use

## Investigation graph

The frontend should be able to request a focused subgraph around: -
wallet - transaction - IP - cluster

Avoid sending the entire graph to the browser when a focused
neighborhood is sufficient.

## Graph evidence

Every investigative graph relationship should be traceable to one or
more source observations or derived analytical relationships.
