from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import threading
from typing import Any, Iterable

import duckdb
import networkx as nx
import pandas as pd

from app.services.correlation import CorrelationResult, CorrelationService
from app.services.paths import DATASET_MANIFEST_PATH, GRAPH_STORAGE_ROOT


GRAPH_EDGE_FIELDS = {
    "relationship",
    "relationship_class",
    "timestamp",
    "first_seen",
    "last_seen",
    "observation_count",
    "source_record_id",
    "source_record_count",
    "txid",
    "txids",
    "amount",
    "ip_roles",
    "wallet_roles",
    "wallet_role",
    "common_input_count",
    "co_occurrence_count",
    "transactions_shared",
}


class GraphDataError(RuntimeError):
    pass


class EntityNotFoundError(GraphDataError):
    pass


@dataclass
class GraphStoragePaths:
    duckdb_path: Path
    nodes_parquet_path: Path
    edges_parquet_path: Path


class GraphStorage:
    def __init__(self, root: Path, dataset_version: str) -> None:
        self.root = root
        self.dataset_version = dataset_version
        safe_version = "".join(
            character if character.isalnum() or character in "._-" else "_"
            for character in dataset_version
        ).strip("._")
        self.paths = GraphStoragePaths(
            duckdb_path=root / f"graph_v{safe_version}.duckdb",
            nodes_parquet_path=root / f"graph_nodes_v{safe_version}.parquet",
            edges_parquet_path=root / f"graph_edges_v{safe_version}.parquet",
        )

    def exists(self) -> bool:
        return all(
            path.is_file()
            for path in (
                self.paths.duckdb_path,
                self.paths.nodes_parquet_path,
                self.paths.edges_parquet_path,
            )
        )

    def write(self, nodes: pd.DataFrame, edges: pd.DataFrame) -> GraphStoragePaths:
        nodes = nodes.copy()
        edges = edges.copy()
        for frame in (nodes, edges):
            for field in frame.columns:
                if (
                    frame[field]
                    .map(
                        lambda value: isinstance(value, set)
                        or (
                            hasattr(value, "tolist")
                            and not isinstance(value, (str, bytes))
                        )
                    )
                    .any()
                ):
                    frame[field] = frame[field].map(
                        lambda value: (
                            sorted(value)
                            if isinstance(value, set)
                            else value.tolist()
                            if hasattr(value, "tolist")
                            and not isinstance(value, (str, bytes))
                            else value
                        )
                    )
        self.root.mkdir(parents=True, exist_ok=True)
        duckdb_temp = self.paths.duckdb_path.with_name(
            f".{self.paths.duckdb_path.name}.tmp"
        )
        nodes_temp = self.paths.nodes_parquet_path.with_name(
            f".{self.paths.nodes_parquet_path.name}.tmp"
        )
        edges_temp = self.paths.edges_parquet_path.with_name(
            f".{self.paths.edges_parquet_path.name}.tmp"
        )
        for temporary_path in (duckdb_temp, nodes_temp, edges_temp):
            temporary_path.unlink(missing_ok=True)

        connection = duckdb.connect(str(duckdb_temp))
        try:
            connection.register("graph_nodes", nodes)
            try:
                connection.execute(
                    "CREATE OR REPLACE TABLE nodes AS SELECT * FROM graph_nodes"
                )
                nodes_parquet = str(nodes_temp).replace("'", "''")
                connection.execute(
                    f"COPY nodes TO '{nodes_parquet}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)"
                )
            finally:
                connection.unregister("graph_nodes")

            connection.register("graph_edges", edges)
            try:
                connection.execute(
                    "CREATE OR REPLACE TABLE edges AS SELECT * FROM graph_edges"
                )
                edges_parquet = str(edges_temp).replace("'", "''")
                connection.execute(
                    f"COPY edges TO '{edges_parquet}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)"
                )
            finally:
                connection.unregister("graph_edges")

            connection.execute(
                "CREATE OR REPLACE TABLE metadata AS SELECT "
                f"'{self.dataset_version}' AS dataset_version, "
                f"{len(nodes)} AS node_count, {len(edges)} AS edge_count"
            )
        except Exception as exc:
            raise GraphDataError("Failed to persist graph artifacts") from exc
        finally:
            connection.close()

        duckdb_temp.replace(self.paths.duckdb_path)
        nodes_temp.replace(self.paths.nodes_parquet_path)
        edges_temp.replace(self.paths.edges_parquet_path)
        return self.paths

    def load_nodes(self) -> pd.DataFrame:
        if not self.paths.duckdb_path.is_file():
            raise GraphDataError("Graph cache is missing")
        connection = duckdb.connect(str(self.paths.duckdb_path))
        try:
            metadata_row = connection.execute(
                "SELECT dataset_version FROM metadata"
            ).fetchone()
            if metadata_row is None or metadata_row[0] != self.dataset_version:
                raise GraphDataError(
                    "Graph cache belongs to a different dataset version"
                )
            return connection.execute("SELECT * FROM nodes").df()
        except GraphDataError:
            raise
        except Exception as exc:
            raise GraphDataError("Failed to load graph node cache") from exc
        finally:
            connection.close()

    def iter_edges(self) -> Iterable[tuple[Any, ...]]:
        if not self.paths.duckdb_path.is_file():
            raise GraphDataError("Graph cache is missing")
        connection = duckdb.connect(str(self.paths.duckdb_path))
        try:
            metadata_row = connection.execute(
                "SELECT dataset_version FROM metadata"
            ).fetchone()
            if metadata_row is None or metadata_row[0] != self.dataset_version:
                raise GraphDataError(
                    "Graph cache belongs to a different dataset version"
                )
            cursor = connection.execute("SELECT * FROM edges")
            columns = [description[0] for description in cursor.description]
            while True:
                rows = cursor.fetchmany(10_000)
                if not rows:
                    break
                for row in rows:
                    yield (columns, row)
        except GraphDataError:
            raise
        except Exception as exc:
            raise GraphDataError("Failed to stream graph edge cache") from exc
        finally:
            connection.close()

    def load(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not self.paths.duckdb_path.is_file():
            raise GraphDataError("Graph cache is missing")
        connection = duckdb.connect(str(self.paths.duckdb_path))
        try:
            metadata_row = connection.execute(
                "SELECT dataset_version FROM metadata"
            ).fetchone()
            if metadata_row is None or metadata_row[0] != self.dataset_version:
                raise GraphDataError(
                    "Graph cache belongs to a different dataset version"
                )
            nodes = connection.execute("SELECT * FROM nodes").df()
            edges = connection.execute("SELECT * FROM edges").df()
        except GraphDataError:
            raise
        except Exception as exc:
            raise GraphDataError("Failed to load graph cache") from exc
        finally:
            connection.close()
        return nodes, edges


class GraphService:
    def __init__(
        self,
        correlation_service: CorrelationService | None = None,
        storage_root: Path = GRAPH_STORAGE_ROOT,
        manifest_path: Path = DATASET_MANIFEST_PATH,
    ) -> None:
        self.correlation_service = correlation_service or CorrelationService()
        self.storage_root = storage_root
        self.manifest_path = manifest_path
        self._graph: nx.MultiDiGraph | None = None
        self._result: CorrelationResult | None = None
        self._entity_index: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def get_graph(self) -> nx.MultiDiGraph:
        with self._lock:
            if self._graph is not None:
                return self._graph
            dataset_version = self._dataset_version()
            storage = GraphStorage(self.storage_root, dataset_version)
            if storage.exists():
                try:
                    nodes = storage.load_nodes()
                    graph = self._graph_from_cached_edges(
                        nodes,
                        storage.iter_edges(),
                    )
                except GraphDataError:
                    graph, result = self._build_and_persist(storage)
                    self._result = result
            else:
                graph, result = self._build_and_persist(storage)
                self._result = result
            self._graph = graph
            self._build_entity_index(graph)
            return graph

    def statistics(self) -> dict[str, Any]:
        graph = self.get_graph()
        type_counts = Counter(
            attributes.get("type", "unknown")
            for _, attributes in graph.nodes(data=True)
        )
        degrees = [degree for _, degree in graph.degree()]
        in_degrees = [degree for _, degree in graph.in_degree()]
        out_degrees = [degree for _, degree in graph.out_degree()]
        components = list(nx.weakly_connected_components(graph)) if graph else []
        largest_component = max((len(component) for component in components), default=0)
        return {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "wallet_nodes": type_counts.get("wallet", 0),
            "transaction_nodes": type_counts.get("transaction", 0),
            "ip_nodes": type_counts.get("ip", 0),
            "connected_components": len(components),
            "largest_component_nodes": largest_component,
            "average_degree": round(sum(degrees) / len(degrees), 4) if degrees else 0.0,
            "average_in_degree": (
                round(sum(in_degrees) / len(in_degrees), 4) if in_degrees else 0.0
            ),
            "average_out_degree": (
                round(sum(out_degrees) / len(out_degrees), 4) if out_degrees else 0.0
            ),
            "max_degree": max(degrees, default=0),
            "max_in_degree": max(in_degrees, default=0),
            "max_out_degree": max(out_degrees, default=0),
        }

    def entity_summary(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        graph = self.get_graph()
        node_id = self._resolve_entity(entity_type, entity_id)
        if node_id not in graph:
            raise EntityNotFoundError(f"{entity_type} entity not found: {entity_id}")
        attributes = dict(graph.nodes[node_id])
        degree = graph.degree(node_id)
        in_degree = graph.in_degree(node_id)
        out_degree = graph.out_degree(node_id)
        neighbors = self._neighbor_ids(graph, node_id)

        if entity_type == "wallet":
            input_transactions = set(attributes.get("input_transaction_ids", []))
            output_transactions = set(attributes.get("output_transaction_ids", []))
            related_transactions = sorted(input_transactions | output_transactions)
            related_ips = sorted(set(attributes.get("related_ips", [])))
            associations = self._common_input_associations(graph, node_id, limit)
            data = {
                "address": attributes.get("entity_id"),
                "transaction_count": len(input_transactions | output_transactions),
                "input_transaction_count": len(input_transactions),
                "output_transaction_count": len(output_transactions),
                "related_ips": related_ips[:limit],
                "related_ip_count": len(related_ips),
                "related_transactions": related_transactions[:limit],
                "related_transaction_count": len(related_transactions),
                "common_input_associations": associations,
                "first_seen": attributes.get("first_seen"),
                "last_seen": attributes.get("last_seen"),
            }
        elif entity_type == "ip":
            transactions = sorted(set(attributes.get("transaction_ids", [])))
            wallets = sorted(set(attributes.get("wallets", [])))
            data = {
                "address": attributes.get("entity_id"),
                "observed_transaction_count": len(transactions),
                "related_wallets": wallets[:limit],
                "related_wallet_count": len(wallets),
                "related_transactions": transactions[:limit],
                "related_transaction_count": len(transactions),
                "countries": sorted(set(attributes.get("countries", []))),
                "asns": sorted(set(attributes.get("asns", []))),
                "first_seen": attributes.get("first_seen"),
                "last_seen": attributes.get("last_seen"),
            }
        else:
            input_wallets = sorted(set(attributes.get("input_wallets", [])))
            output_wallets = sorted(set(attributes.get("output_wallets", [])))
            observing_ips = sorted(set(attributes.get("observing_ips", [])))
            data = {
                "txid": attributes.get("txid"),
                "first_seen": attributes.get("first_seen"),
                "last_seen": attributes.get("last_seen"),
                "observation_count": attributes.get("observation_count", 0),
                "input_wallets": input_wallets[:limit],
                "input_wallet_count": len(input_wallets),
                "output_wallets": output_wallets[:limit],
                "output_wallet_count": len(output_wallets),
                "input_amounts": list(attributes.get("input_amounts", []))[:limit],
                "output_amounts": list(attributes.get("output_amounts", []))[:limit],
                "fee": attributes.get("fee"),
                "script_type": attributes.get("script_type"),
                "observing_ips": observing_ips[:limit],
                "observing_ip_count": len(observing_ips),
                "src_ips": sorted(set(attributes.get("src_ips", [])))[:limit],
                "dst_ips": sorted(set(attributes.get("dst_ips", [])))[:limit],
                "src_ports": sorted(set(attributes.get("src_ports", []))),
                "dst_ports": sorted(set(attributes.get("dst_ports", []))),
                "geo_country": attributes.get("geo_country"),
                "asn": attributes.get("asn"),
                "source_record_ids": sorted(
                    set(attributes.get("source_record_ids", []))
                )[:limit],
            }

        return {
            "node_id": node_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "degree": degree,
            "in_degree": in_degree,
            "out_degree": out_degree,
            "neighbor_count": len(neighbors),
            "data": data,
        }

    def transaction_summary(self, txid: str, limit: int = 100) -> dict[str, Any]:
        return self.entity_summary("transaction", txid, limit)["data"]

    def neighborhood(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 1,
        node_types: set[str] | None = None,
        edge_types: set[str] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        graph = self.get_graph()
        center = self._resolve_entity(entity_type, entity_id)
        if center not in graph:
            raise EntityNotFoundError(f"{entity_type} entity not found: {entity_id}")

        visited = {center}
        current = {center}
        selected_nodes = {center}
        selected_edges: dict[tuple[str, str], dict[str, Any]] = {}
        for _ in range(max(0, min(depth, 2))):
            next_nodes: set[str] = set()
            for node_id in current:
                for neighbor, _, attributes in graph.in_edges(node_id, data=True):
                    if edge_types and attributes.get("relationship") not in edge_types:
                        continue
                    if neighbor not in visited and self._node_type_allowed(
                        graph, neighbor, node_types
                    ):
                        next_nodes.add(neighbor)
                    selected_edges[(neighbor, node_id)] = dict(attributes)
                    selected_nodes.add(neighbor)
                for _, neighbor, attributes in graph.out_edges(node_id, data=True):
                    if edge_types and attributes.get("relationship") not in edge_types:
                        continue
                    if neighbor not in visited and self._node_type_allowed(
                        graph, neighbor, node_types
                    ):
                        next_nodes.add(neighbor)
                    selected_edges[(node_id, neighbor)] = dict(attributes)
                    selected_nodes.add(neighbor)
            current = next_nodes
            visited.update(next_nodes)
            if not current:
                break

        ordered_node_ids = [center] + sorted(selected_nodes - {center})
        node_rows = [
            self._node_response(graph, node_id)
            for node_id in ordered_node_ids
            if self._node_type_allowed(graph, node_id, node_types)
        ][:limit]
        returned_node_ids = {row["id"] for row in node_rows}
        edge_rows = [
            self._edge_response(source, target, attributes)
            for (source, target), attributes in selected_edges.items()
            if source in returned_node_ids and target in returned_node_ids
        ][:limit]
        return {
            "center": self._node_response(graph, center),
            "depth": max(0, min(depth, 2)),
            "nodes": node_rows,
            "edges": edge_rows,
            "total_nodes": len(selected_nodes),
            "total_edges": len(selected_edges),
        }

    def _graph_from_cached_edges(
        self,
        nodes: pd.DataFrame,
        edge_rows: Iterable[tuple[list[str], tuple[Any, ...]]],
    ) -> nx.MultiDiGraph:
        graph = nx.MultiDiGraph()
        node_columns = list(nodes.columns)
        for values in nodes.itertuples(index=False, name=None):
            row = dict(zip(node_columns, values))
            node_id = str(row.pop("id"))
            graph.add_node(node_id, **self._clean_attributes(row))
        for columns, values in edge_rows:
            row = dict(zip(columns, values))
            source = str(row.pop("source"))
            target = str(row.pop("target"))
            edge_attributes = {
                field: row[field]
                for field in GRAPH_EDGE_FIELDS
                if field in row and row[field] is not None
            }
            graph.add_edge(source, target, **self._clean_attributes(edge_attributes))
        return graph

    def _build_and_persist(
        self,
        storage: GraphStorage,
    ) -> tuple[nx.MultiDiGraph, CorrelationResult]:
        result = self.correlation_service.correlate()
        storage.write(result.nodes, result.edges)
        graph = self._graph_from_frames(result.nodes, result.edges)
        return graph, result

    def _graph_from_frames(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
    ) -> nx.MultiDiGraph:
        graph = nx.MultiDiGraph()
        node_columns = list(nodes.columns)
        for values in nodes.itertuples(index=False, name=None):
            row = dict(zip(node_columns, values))
            node_id = str(row.pop("id"))
            graph.add_node(node_id, **self._clean_attributes(row))
        edge_columns = list(edges.columns)
        for values in edges.itertuples(index=False, name=None):
            row = dict(zip(edge_columns, values))
            source = str(row.pop("source"))
            target = str(row.pop("target"))
            edge_attributes = {
                field: row[field]
                for field in GRAPH_EDGE_FIELDS
                if field in row and row[field] is not None
            }
            graph.add_edge(source, target, **self._clean_attributes(edge_attributes))
        return graph

    def _build_entity_index(self, graph: nx.MultiDiGraph) -> None:
        self._entity_index = {}
        for node_id, attributes in graph.nodes(data=True):
            entity_type = str(attributes.get("type", ""))
            entity_id = str(attributes.get("entity_id", ""))
            if entity_type and entity_id:
                self._entity_index[(entity_type, entity_id)] = node_id

    def _resolve_entity(self, entity_type: str, entity_id: str) -> str:
        normalized_type = entity_type.lower()
        if normalized_type not in {"wallet", "ip", "transaction"}:
            raise EntityNotFoundError(f"Unsupported entity type: {entity_type}")
        prefixed = f"{normalized_type}:{entity_id}"
        if prefixed in self._entity_index:
            return prefixed
        node_id = self._entity_index.get((normalized_type, entity_id))
        if node_id is None:
            raise EntityNotFoundError(
                f"{normalized_type} entity not found: {entity_id}"
            )
        return node_id

    @staticmethod
    def _node_type_allowed(
        graph: nx.MultiDiGraph,
        node_id: str,
        node_types: set[str] | None,
    ) -> bool:
        if not node_types:
            return True
        return graph.nodes[node_id].get("type") in node_types

    @staticmethod
    def _neighbor_ids(graph: nx.MultiDiGraph, node_id: str) -> set[str]:
        return set(graph.predecessors(node_id)) | set(graph.successors(node_id))

    @staticmethod
    def _common_input_associations(
        graph: nx.MultiDiGraph,
        node_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        associations: list[dict[str, Any]] = []
        for source, _, _, attributes in graph.in_edges(node_id, keys=True, data=True):
            if attributes.get("relationship") != "common_input_association":
                continue
            other = source
            associations.append(
                {
                    "wallet": graph.nodes[other].get("entity_id"),
                    "common_input_count": (
                        int(attributes["common_input_count"])
                        if attributes.get("common_input_count") is not None
                        else None
                    ),
                    "co_occurrence_count": (
                        int(attributes["co_occurrence_count"])
                        if attributes.get("co_occurrence_count") is not None
                        else None
                    ),
                    "transactions_shared": list(
                        attributes.get("transactions_shared", [])
                    )[:limit],
                }
            )
        for _, target, _, attributes in graph.out_edges(node_id, keys=True, data=True):
            if attributes.get("relationship") != "common_input_association":
                continue
            other = target
            associations.append(
                {
                    "wallet": graph.nodes[other].get("entity_id"),
                    "common_input_count": (
                        int(attributes["common_input_count"])
                        if attributes.get("common_input_count") is not None
                        else None
                    ),
                    "co_occurrence_count": (
                        int(attributes["co_occurrence_count"])
                        if attributes.get("co_occurrence_count") is not None
                        else None
                    ),
                    "transactions_shared": list(
                        attributes.get("transactions_shared", [])
                    )[:limit],
                }
            )
        return associations[:limit]

    @staticmethod
    def _node_response(graph: nx.MultiDiGraph, node_id: str) -> dict[str, Any]:
        attributes = graph.nodes[node_id]
        return {
            "id": node_id,
            "type": attributes.get("type"),
            "entity_id": attributes.get("entity_id"),
            "address": attributes.get("address"),
            "txid": attributes.get("txid"),
        }

    @staticmethod
    def _edge_response(
        source: str,
        target: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:
        cleaned = GraphService._clean_attributes(attributes)
        known_fields = {
            "source",
            "target",
            "relationship",
            "relationship_class",
            "timestamp",
            "first_seen",
            "last_seen",
            "observation_count",
            "amount",
            "source_record_id",
            "source_record_count",
            "txid",
            "txids",
        }
        return {
            "source": source,
            "target": target,
            **{
                field: value
                for field, value in cleaned.items()
                if field in known_fields
            },
            "metadata": {
                field: value
                for field, value in cleaned.items()
                if field not in known_fields
            },
        }

    @staticmethod
    def _clean_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for field, value in attributes.items():
            if isinstance(value, set):
                cleaned[field] = sorted(value)
            elif isinstance(value, tuple):
                cleaned[field] = list(value)
            elif hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
                cleaned[field] = value.tolist()
            elif isinstance(value, pd.Timestamp):
                cleaned[field] = value.isoformat()
            elif (
                value is None
                or (
                    not isinstance(value, (list, dict, set, tuple))
                    and hasattr(value, "isna")
                    and bool(value.isna())
                )
                or (isinstance(value, float) and value != value)
            ):
                cleaned[field] = None
            else:
                cleaned[field] = value
        return cleaned

    def _dataset_version(self) -> str:
        if not self.manifest_path.is_file():
            raise GraphDataError("Dataset manifest not found")
        try:
            with self.manifest_path.open("r", encoding="utf-8") as file:
                manifest = json.load(file)
        except Exception as exc:
            raise GraphDataError("Failed to read dataset manifest") from exc
        return str(manifest.get("dataset_version", "unknown"))
