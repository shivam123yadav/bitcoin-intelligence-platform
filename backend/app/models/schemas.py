from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class DatasetMetadataResponse(BaseModel):
    dataset_id: str
    dataset_version: str
    generator_version: str
    schema_version: str
    record_count: int
    unique_txids: int
    wallet_pool_count: int
    ip_pool_count: int
    observed_country_count: int
    observed_asn_count: int
    scenario_instance_count: int
    time_start: str
    time_end: str
    validation_status: str
    ingestion_status: Literal["READY", "PARTIAL", "FAILED"]
    valid_records: int
    invalid_records: int
    missing_fields: list[str] = Field(default_factory=list)
    load_time_ms: float
    reference_validation_status: str | None = None


class IngestionStatusResponse(BaseModel):
    status: Literal["READY", "PARTIAL", "FAILED"]
    record_count: int
    valid_records: int
    invalid_records: int
    missing_fields: list[str] = Field(default_factory=list)
    load_time_ms: float
    dataset_version: str
    reference_validation_status: str | None = None


EntityType = Literal["wallet", "ip", "transaction"]


class GraphStatisticsResponse(BaseModel):
    total_nodes: int
    total_edges: int
    wallet_nodes: int
    transaction_nodes: int
    ip_nodes: int
    connected_components: int
    largest_component_nodes: int
    average_degree: float
    average_in_degree: float
    average_out_degree: float
    max_degree: int
    max_in_degree: int
    max_out_degree: int


class EntityLookupResponse(BaseModel):
    entity_type: EntityType
    entity_id: str
    node_id: str
    degree: int
    in_degree: int
    out_degree: int
    neighbor_count: int
    data: dict[str, Any]


class TransactionLookupResponse(BaseModel):
    txid: str
    first_seen: str | None
    last_seen: str | None
    observation_count: int
    input_wallets: list[str]
    input_wallet_count: int
    output_wallets: list[str]
    output_wallet_count: int
    input_amounts: list[float]
    output_amounts: list[float]
    fee: float | None
    script_type: str | None
    observing_ips: list[str]
    observing_ip_count: int
    src_ips: list[str]
    dst_ips: list[str]
    src_ports: list[int]
    dst_ports: list[int]
    geo_country: str | None
    asn: str | None
    source_record_ids: list[str]


class GraphNodeResponse(BaseModel):
    id: str
    type: EntityType
    entity_id: str
    address: str | None = None
    txid: str | None = None


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    relationship: str
    relationship_class: str
    timestamp: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    observation_count: int
    amount: float | None = None
    source_record_id: str | None = None
    source_record_count: int = 1
    txid: str | None = None
    txids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphNeighborhoodResponse(BaseModel):
    center: GraphNodeResponse
    depth: int
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    total_nodes: int
    total_edges: int
