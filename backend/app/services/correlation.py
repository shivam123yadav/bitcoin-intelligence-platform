from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
import json
from pathlib import Path
import threading
from typing import Any

import duckdb
import pandas as pd

from app.services.paths import DATASET_MANIFEST_PATH, NORMALIZED_STORAGE_ROOT


class CorrelationDataError(RuntimeError):
    pass


@dataclass
class CorrelationResult:
    nodes: pd.DataFrame
    edges: pd.DataFrame
    transactions: pd.DataFrame
    source_record_count: int
    dataset_version: str


class CorrelationService:
    def __init__(
        self,
        normalized_storage_root: Path = NORMALIZED_STORAGE_ROOT,
        manifest_path: Path = DATASET_MANIFEST_PATH,
    ) -> None:
        self.normalized_storage_root = normalized_storage_root
        self.manifest_path = manifest_path
        self._result: CorrelationResult | None = None
        self._lock = threading.Lock()

    def correlate(self) -> CorrelationResult:
        with self._lock:
            if self._result is not None:
                return self._result

            manifest = self._read_manifest()
            dataset_version = str(manifest.get("dataset_version", "unknown"))
            normalized_path = self.normalized_storage_root / (
                f"observations_v{dataset_version}.duckdb"
            )
            observations = self._load_observations(normalized_path)
            nodes, edges, transactions = self._build_correlations(observations)
            result = CorrelationResult(
                nodes=nodes,
                edges=edges,
                transactions=transactions,
                source_record_count=len(observations),
                dataset_version=dataset_version,
            )
            self._result = result
            return result

    def _load_observations(self, path: Path) -> pd.DataFrame:
        if not path.is_file():
            raise CorrelationDataError(
                f"Normalized dataset storage not found: {path.name}"
            )
        connection = duckdb.connect(str(path))
        try:
            observations = connection.execute(
                "SELECT * FROM observations ORDER BY timestamp, source_record_id"
            ).df()
        except Exception as exc:
            raise CorrelationDataError(
                "Failed to read normalized observations"
            ) from exc
        finally:
            connection.close()

        for field in (
            "input_addresses",
            "output_addresses",
            "input_amounts",
            "output_amounts",
        ):
            if field in observations.columns:
                observations[field] = observations[field].map(self._as_list)
        return observations

    def _build_correlations(
        self,
        observations: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        ip_nodes: dict[str, dict[str, Any]] = {}
        wallet_nodes: dict[str, dict[str, Any]] = {}
        transaction_nodes: dict[str, dict[str, Any]] = {}
        edge_accumulators: dict[tuple[Any, ...], dict[str, Any]] = {}

        for observation in observations.to_dict("records"):
            timestamp = str(observation["timestamp"])
            txid = str(observation["txid"])
            src_ip = str(observation["src_ip"])
            dst_ip = str(observation["dst_ip"])
            src_port = int(observation["src_port"])
            dst_port = int(observation["dst_port"])
            fee = float(observation["fee"])
            script_type = str(observation["script_type"])
            geo_country = str(observation["geo_country"])
            asn = str(observation["asn"])
            source_record_id = str(observation["source_record_id"])
            input_addresses = [str(value) for value in observation["input_addresses"]]
            output_addresses = [str(value) for value in observation["output_addresses"]]
            input_amounts = [float(value) for value in observation["input_amounts"]]
            output_amounts = [float(value) for value in observation["output_amounts"]]
            input_wallets = self._amount_by_wallet(input_addresses, input_amounts)
            output_wallets = self._amount_by_wallet(output_addresses, output_amounts)
            all_wallets = set(input_wallets) | set(output_wallets)

            transaction = transaction_nodes.setdefault(
                txid,
                self._transaction_node(
                    txid,
                    timestamp,
                    fee,
                    script_type,
                    geo_country,
                    asn,
                ),
            )
            transaction["observation_count"] += 1
            transaction["first_seen"] = min(transaction["first_seen"], timestamp)
            transaction["last_seen"] = max(transaction["last_seen"], timestamp)
            transaction["source_record_ids"].add(source_record_id)
            transaction["observing_ips"].add(src_ip)
            transaction["src_ips"].add(src_ip)
            transaction["dst_ips"].add(dst_ip)
            transaction["src_ports"].add(src_port)
            transaction["dst_ports"].add(dst_port)
            transaction["input_wallets"].update(input_wallets)
            transaction["output_wallets"].update(output_wallets)
            transaction["input_amounts"].extend(input_amounts)
            transaction["output_amounts"].extend(output_amounts)

            self._update_ip_node(
                ip_nodes,
                src_ip,
                txid,
                all_wallets,
                geo_country,
                asn,
                timestamp,
            )
            self._update_ip_node(
                ip_nodes,
                dst_ip,
                txid,
                all_wallets,
                geo_country,
                asn,
                timestamp,
            )
            for wallet in input_wallets:
                self._update_wallet_node(
                    wallet_nodes,
                    wallet,
                    txid,
                    {src_ip, dst_ip},
                    timestamp,
                    is_input=True,
                )
            for wallet in output_wallets:
                self._update_wallet_node(
                    wallet_nodes,
                    wallet,
                    txid,
                    {src_ip, dst_ip},
                    timestamp,
                    is_input=False,
                )

            network_metadata = {
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "geo_country": geo_country,
                "asn": asn,
                "txid": txid,
            }
            self._add_edge(
                edge_accumulators,
                (
                    "ip_transaction",
                    src_ip,
                    txid,
                ),
                f"ip:{src_ip}",
                f"transaction:{txid}",
                "observed_transaction",
                "observed",
                source_record_id,
                timestamp,
                amount=None,
                ip_roles={"source"},
                **network_metadata,
            )
            self._add_edge(
                edge_accumulators,
                (
                    "ip_transaction",
                    dst_ip,
                    txid,
                ),
                f"ip:{dst_ip}",
                f"transaction:{txid}",
                "observed_transaction",
                "observed",
                source_record_id,
                timestamp,
                amount=None,
                ip_roles={"destination"},
                **network_metadata,
            )

            for wallet, amount in input_wallets.items():
                self._add_edge(
                    edge_accumulators,
                    ("ip_wallet", src_ip, wallet),
                    f"ip:{src_ip}",
                    f"wallet:{wallet}",
                    "observed_wallet",
                    "observed",
                    source_record_id,
                    timestamp,
                    amount=amount,
                    ip_roles={"source"},
                    wallet_roles={"input"},
                    **network_metadata,
                )
                self._add_edge(
                    edge_accumulators,
                    ("transaction_wallet", txid, wallet, "input"),
                    f"transaction:{txid}",
                    f"wallet:{wallet}",
                    "input_wallet",
                    "exact",
                    source_record_id,
                    timestamp,
                    amount=amount,
                    wallet_role="input",
                    **network_metadata,
                )
            for wallet, amount in output_wallets.items():
                self._add_edge(
                    edge_accumulators,
                    ("ip_wallet", src_ip, wallet),
                    f"ip:{src_ip}",
                    f"wallet:{wallet}",
                    "observed_wallet",
                    "observed",
                    source_record_id,
                    timestamp,
                    amount=amount,
                    ip_roles={"source"},
                    wallet_roles={"output"},
                    **network_metadata,
                )
                self._add_edge(
                    edge_accumulators,
                    ("transaction_wallet", txid, wallet, "output"),
                    f"transaction:{txid}",
                    f"wallet:{wallet}",
                    "output_wallet",
                    "exact",
                    source_record_id,
                    timestamp,
                    amount=amount,
                    wallet_role="output",
                    **network_metadata,
                )

            for wallet_a, wallet_b in combinations(sorted(set(input_wallets)), 2):
                self._add_edge(
                    edge_accumulators,
                    ("common_input", wallet_a, wallet_b),
                    f"wallet:{wallet_a}",
                    f"wallet:{wallet_b}",
                    "common_input_association",
                    "inferred",
                    source_record_id,
                    timestamp,
                    amount=None,
                    txid=txid,
                )

        node_rows = [
            *ip_nodes.values(),
            *wallet_nodes.values(),
            *transaction_nodes.values(),
        ]
        for node in node_rows:
            for field, value in list(node.items()):
                if isinstance(value, set):
                    node[field] = sorted(value)
        nodes = pd.DataFrame(node_rows)
        edges = self._edge_frame(edge_accumulators)
        transactions = pd.DataFrame(
            [self._transaction_row(value) for value in transaction_nodes.values()]
        )
        return nodes, edges, transactions

    @staticmethod
    def _transaction_node(
        txid: str,
        timestamp: str,
        fee: float,
        script_type: str,
        geo_country: str,
        asn: str,
    ) -> dict[str, Any]:
        return {
            "id": f"transaction:{txid}",
            "type": "transaction",
            "entity_id": txid,
            "txid": txid,
            "first_seen": timestamp,
            "last_seen": timestamp,
            "fee": fee,
            "script_type": script_type,
            "geo_country": geo_country,
            "asn": asn,
            "observation_count": 0,
            "source_record_ids": set(),
            "observing_ips": set(),
            "src_ips": set(),
            "dst_ips": set(),
            "src_ports": set(),
            "dst_ports": set(),
            "input_wallets": set(),
            "output_wallets": set(),
            "input_amounts": [],
            "output_amounts": [],
        }

    @staticmethod
    def _update_ip_node(
        ip_nodes: dict[str, dict[str, Any]],
        ip: str,
        txid: str,
        wallets: set[str],
        geo_country: str,
        asn: str,
        timestamp: str,
    ) -> None:
        node = ip_nodes.setdefault(
            ip,
            {
                "id": f"ip:{ip}",
                "type": "ip",
                "entity_id": ip,
                "address": ip,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "transaction_ids": set(),
                "wallets": set(),
                "countries": set(),
                "asns": set(),
                "observation_count": 0,
            },
        )
        node["transaction_ids"].add(txid)
        node["wallets"].update(wallets)
        node["countries"].add(geo_country)
        node["asns"].add(asn)
        node["observation_count"] += 1
        node["first_seen"] = min(node["first_seen"], timestamp)
        node["last_seen"] = max(node["last_seen"], timestamp)

    @staticmethod
    def _update_wallet_node(
        wallet_nodes: dict[str, dict[str, Any]],
        wallet: str,
        txid: str,
        ips: set[str],
        timestamp: str,
        is_input: bool,
    ) -> None:
        node = wallet_nodes.setdefault(
            wallet,
            {
                "id": f"wallet:{wallet}",
                "type": "wallet",
                "entity_id": wallet,
                "address": wallet,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "input_transaction_ids": set(),
                "output_transaction_ids": set(),
                "related_ips": set(),
                "observation_count": 0,
            },
        )
        transaction_ids = (
            node["input_transaction_ids"]
            if is_input
            else node["output_transaction_ids"]
        )
        transaction_ids.add(txid)
        node["related_ips"].update(ips)
        node["observation_count"] += 1
        node["first_seen"] = min(node["first_seen"], timestamp)
        node["last_seen"] = max(node["last_seen"], timestamp)

    @staticmethod
    def _amount_by_wallet(
        addresses: list[str],
        amounts: list[float],
    ) -> dict[str, float]:
        result: dict[str, float] = defaultdict(float)
        for address, amount in zip(addresses, amounts):
            result[address] += amount
        return dict(result)

    @staticmethod
    def _add_edge(
        edge_accumulators: dict[tuple[Any, ...], dict[str, Any]],
        key: tuple[Any, ...],
        source: str,
        target: str,
        relationship: str,
        relationship_class: str,
        source_record_id: str,
        timestamp: str,
        amount: float | None,
        **metadata: Any,
    ) -> None:
        edge = edge_accumulators.setdefault(
            key,
            {
                "source": source,
                "target": target,
                "relationship": relationship,
                "relationship_class": relationship_class,
                "source_record_id": source_record_id,
                "source_record_count": 0,
                "txid": metadata.get("txid"),
                "txids": set() if relationship == "common_input_association" else None,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "observation_count": 0,
                "amount": None,
            },
        )
        edge["source_record_count"] += 1
        if edge["txids"] is not None:
            edge["txids"].add(str(metadata.get("txid", "")))
        edge["first_seen"] = min(edge["first_seen"], timestamp)
        edge["last_seen"] = max(edge["last_seen"], timestamp)
        edge["observation_count"] += 1
        if amount is not None:
            edge["amount"] = (edge["amount"] or 0.0) + amount
        for field, value in metadata.items():
            if field.endswith("_roles") and isinstance(value, set):
                existing = set(str(edge.get(field, "")).split(","))
                existing.update(value)
                edge[field] = ",".join(sorted(existing))
            elif isinstance(value, set):
                edge[field] = set(edge.get(field, set())) | value
            elif field not in edge or edge[field] is None:
                edge[field] = value

    @staticmethod
    def _edge_frame(
        edge_accumulators: dict[tuple[Any, ...], dict[str, Any]],
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for edge in edge_accumulators.values():
            row = {
                "source": edge["source"],
                "target": edge["target"],
                "relationship": edge["relationship"],
                "relationship_class": edge["relationship_class"],
                "timestamp": edge["first_seen"],
                "first_seen": edge["first_seen"],
                "last_seen": edge["last_seen"],
                "observation_count": edge["observation_count"],
                "source_record_id": edge["source_record_id"],
                "source_record_count": edge["source_record_count"],
                "txid": edge.get("txid"),
                "amount": (
                    round(edge["amount"], 8) if edge["amount"] is not None else None
                ),
            }
            for field in ("ip_roles", "wallet_roles", "wallet_role"):
                if field in edge:
                    row[field] = edge[field]
            if row["relationship"] == "common_input_association":
                transactions_shared = sorted(
                    txid for txid in (edge.get("txids") or set()) if txid
                )
                row["common_input_count"] = len(transactions_shared)
                row["co_occurrence_count"] = row["observation_count"]
                row["transactions_shared"] = transactions_shared
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _transaction_row(transaction: dict[str, Any]) -> dict[str, Any]:
        return {
            "txid": transaction["txid"],
            "first_seen": transaction["first_seen"],
            "last_seen": transaction["last_seen"],
            "observation_count": transaction["observation_count"],
            "input_wallets": sorted(transaction["input_wallets"]),
            "output_wallets": sorted(transaction["output_wallets"]),
            "input_amounts": transaction["input_amounts"],
            "output_amounts": transaction["output_amounts"],
            "fee": transaction["fee"],
            "script_type": transaction["script_type"],
            "observing_ips": sorted(transaction["observing_ips"]),
            "src_ips": sorted(transaction["src_ips"]),
            "dst_ips": sorted(transaction["dst_ips"]),
            "src_ports": sorted(transaction["src_ports"]),
            "dst_ports": sorted(transaction["dst_ports"]),
            "source_record_ids": sorted(transaction["source_record_ids"]),
            "geo_country": transaction["geo_country"],
            "asn": transaction["asn"],
        }

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
            return value.tolist()
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        return [value]

    def _read_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            raise CorrelationDataError("Dataset manifest not found")
        try:
            with self.manifest_path.open("r", encoding="utf-8") as file:
                value = json.load(file)
        except Exception as exc:
            raise CorrelationDataError("Failed to read dataset manifest") from exc
        if not isinstance(value, dict):
            raise CorrelationDataError("Dataset manifest must contain an object")
        return value
