"""Graph-based risk propagation over wallet relationships.

This service is intentionally separate from the anomaly, clustering and lead
pipeline. It consumes the completed analysis state and the existing graph cache
and produces an additional, bounded graph-derived signal for investigation UI.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import threading
from typing import Any

import pandas as pd

from app.services.analysis import analysis_service
from app.services.graph import GraphService
from app.services.artifacts import load_artifact, save_artifact


@dataclass(frozen=True)
class PropagationContributor:
    source_entity_id: str
    relationship: str
    hop: int
    contribution: float
    edge_weight: float
    source_anomaly_score: float
    detail: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "sourceEntityId": self.source_entity_id,
            "relationship": self.relationship,
            "hop": self.hop,
            "contribution": round(self.contribution, 6),
            "edgeWeight": round(self.edge_weight, 6),
            "sourceAnomalyScore": round(self.source_anomaly_score, 6),
            "detail": self.detail,
        }


class RiskPropagationService:
    """Calculate a bounded graph-derived risk signal without changing ML output."""

    MAX_HOPS = 2
    GAMMA = 0.5
    COMMON_INPUT_CAP = 5
    TOP_CONTRIBUTORS = 5
    CONTRIBUTION_FLOOR = 0.01
    MIN_SEED_SCORE = 0.45

    def __init__(self, graph_service: GraphService | None = None) -> None:
        self.graph_service = graph_service or GraphService()
        self._lock = threading.RLock()
        self._dataset_version: str | None = None
        self._results: dict[str, dict[str, Any]] | None = None

    def all(self, version: str | None = None, force: bool = False) -> dict[str, dict[str, Any]]:
        with self._lock:
            state = analysis_service.get_state()
            dataset_version = version or state.dataset_version
            if self._results is not None and self._dataset_version == dataset_version:
                return self._results
            if not force:
                disk = load_artifact(dataset_version, "phase2a_risk_propagation")
                if disk is not None:
                    self._dataset_version = dataset_version
                    self._results = disk
                    return disk
            results = self._calculate(state.wallet_features, dataset_version)
            save_artifact(dataset_version, "phase2a_risk_propagation", results)
            self._dataset_version = dataset_version
            self._results = results
            return results

    def get(self, entity_id: str, version: str | None = None) -> dict[str, Any]:
        results = self.all(version)
        result = results.get(entity_id)
        if result is None:
            raise KeyError(entity_id)
        return result

    def _calculate(self, wallet_features: pd.DataFrame, dataset_version: str) -> dict[str, dict[str, Any]]:
        graph = self.graph_service.get_graph()
        scores = {
            str(row.entity_id): max(0.0, min(1.0, float(row.anomaly_score)))
            for row in wallet_features[["entity_id", "anomaly_score"]].itertuples(index=False)
        }
        adjacency = self._build_wallet_adjacency(graph)

        # Propagation is seeded by the existing anomaly score. No common-input
        # feature is mixed into the seed, so Phase 2A cannot alter the ML result.
        signal_by_target: dict[str, float] = {wallet: 0.0 for wallet in scores}
        contributors: dict[str, list[PropagationContributor]] = {wallet: [] for wallet in scores}

        # Only medium/high anomaly seeds meaningfully contribute. Every wallet
        # still receives a result; this keeps propagation focused and prevents
        # a dense graph from becoming a global low-signal smoothing operation.
        seeds = sorted(
            ((wallet, score) for wallet, score in scores.items() if score >= self.MIN_SEED_SCORE),
            key=lambda item: (-item[1], item[0]),
        )

        for source, source_score in seeds:
            first_hop = adjacency.get(source, ())
            if not first_hop:
                continue
            source_degree = len(first_hop)
            frontier: dict[str, tuple[float, str, float, dict[str, Any]]] = {}
            for target, edge in first_hop:
                if target == source:
                    continue
                contribution = source_score * edge["weight"] / source_degree * self.GAMMA
                if contribution < self.CONTRIBUTION_FLOOR:
                    continue
                previous = frontier.get(target)
                candidate = (contribution, edge["relationship"], edge["weight"], edge["detail"])
                if previous is None or candidate[0] > previous[0]:
                    frontier[target] = candidate

            self._apply_contributions(
                signal_by_target,
                contributors,
                source,
                source_score,
                hop=1,
                frontier=frontier,
            )

            # Second hop starts from the first-hop wallet, retaining the source
            # identity so the explanation remains tied to the original seed.
            for middle, (first_contribution, first_rel, first_weight, first_detail) in sorted(
                frontier.items(), key=lambda item: item[0]
            ):
                next_edges = adjacency.get(middle, ())
                if not next_edges:
                    continue
                middle_degree = len(next_edges)
                for target, edge in next_edges:
                    if target == source or target == middle:
                        continue
                    second = (
                        source_score
                        * first_weight
                        * edge["weight"]
                        / max(source_degree * middle_degree, 1)
                        * (self.GAMMA ** 2)
                    )
                    if second < self.CONTRIBUTION_FLOOR:
                        continue
                    detail = {
                        "viaEntityId": middle,
                        "firstRelationship": first_rel,
                        "secondRelationship": edge["relationship"],
                        "firstDetail": first_detail,
                        "secondDetail": edge["detail"],
                    }
                    self._add_contributor(
                        signal_by_target,
                        contributors,
                        target,
                        PropagationContributor(
                            source_entity_id=source,
                            relationship=f"{first_rel} -> {edge['relationship']}",
                            hop=2,
                            contribution=second,
                            edge_weight=first_weight * edge["weight"],
                            source_anomaly_score=source_score,
                            detail=detail,
                        ),
                    )

        results: dict[str, dict[str, Any]] = {}
        for wallet in sorted(scores):
            base = scores[wallet]
            graph_signal = max(0.0, min(1.0, signal_by_target.get(wallet, 0.0)))
            # Combine without allowing propagation to push the result over 1.
            # This keeps the original anomaly score intact while treating the
            # graph signal as additional bounded evidence.
            propagated = base + (1.0 - base) * (1.0 - math.exp(-graph_signal))
            items = sorted(
                contributors.get(wallet, []),
                key=lambda c: (-c.contribution, c.source_entity_id, c.relationship, c.hop),
            )[: self.TOP_CONTRIBUTORS]
            results[wallet] = {
                "entityId": wallet,
                "datasetVersion": dataset_version,
                "baseAnomalyScore": round(base, 6),
                "graphPropagatedSignal": round(graph_signal, 6),
                "propagatedRisk": round(min(1.0, propagated), 6),
                "contributors": [item.as_dict() for item in items],
            }
        return results

    @classmethod
    def _build_wallet_adjacency(cls, graph: Any) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        """Build a logical wallet graph from the existing MultiDiGraph.

        Common-input associations are treated as bidirectional inferred links.
        Transaction-linked propagation follows input-wallet -> output-wallet
        direction. IP-layer edges are intentionally excluded.
        """
        candidates: dict[tuple[str, str], dict[str, Any]] = {}

        def add(source: str, target: str, relationship: str, weight: float, detail: dict[str, Any]) -> None:
            if source == target:
                return
            key = (source, target)
            existing = candidates.get(key)
            item = {"relationship": relationship, "weight": float(weight), "detail": detail}
            if existing is None or float(weight) > float(existing["weight"]):
                candidates[key] = item

        for source, target, _, attrs in graph.edges(keys=True, data=True):
            if attrs.get("relationship") != "common_input_association":
                continue
            source_attrs = graph.nodes.get(source, {})
            target_attrs = graph.nodes.get(target, {})
            if source_attrs.get("type") != "wallet" or target_attrs.get("type") != "wallet":
                continue
            source_id = str(source_attrs.get("entity_id") or source).removeprefix("wallet:")
            target_id = str(target_attrs.get("entity_id") or target).removeprefix("wallet:")
            count = int(attrs.get("common_input_count") or 0)
            weight = min(count, cls.COMMON_INPUT_CAP) / cls.COMMON_INPUT_CAP
            if weight <= 0:
                continue
            detail = {
                "commonInputCount": count,
                "coOccurrenceCount": int(attrs.get("co_occurrence_count") or 0),
                "transactionsShared": list(attrs.get("transactions_shared") or [])[:5],
            }
            add(source_id, target_id, "common_input_association", weight, detail)
            add(target_id, source_id, "common_input_association", weight, detail)

        # Existing transaction nodes encode role through the input_wallet and
        # output_wallet edges. Convert those bipartite edges into a logical,
        # directional wallet-to-wallet relationship without modifying the graph.
        for tx_node, tx_attrs in graph.nodes(data=True):
            if tx_attrs.get("type") != "transaction":
                continue
            inputs: list[str] = []
            outputs: list[str] = []
            for _, wallet_node, _, attrs in graph.out_edges(tx_node, keys=True, data=True):
                if graph.nodes[wallet_node].get("type") != "wallet":
                    continue
                wallet_id = str(graph.nodes[wallet_node].get("entity_id") or wallet_node).removeprefix("wallet:")
                relationship = attrs.get("relationship")
                if relationship == "input_wallet":
                    inputs.append(wallet_id)
                elif relationship == "output_wallet":
                    outputs.append(wallet_id)
            for source in sorted(set(inputs)):
                for target in sorted(set(outputs)):
                    if source == target:
                        continue
                    add(
                        source,
                        target,
                        "transaction_link",
                        1.0,
                        {"txid": tx_attrs.get("txid") or tx_attrs.get("entity_id")},
                    )

        adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for (source, target), edge in candidates.items():
            adjacency.setdefault(source, []).append((target, edge))
        for source in adjacency:
            adjacency[source].sort(key=lambda item: (item[0], item[1]["relationship"], -item[1]["weight"]))
        return adjacency

    def _apply_contributions(
        self,
        signal_by_target: dict[str, float],
        contributors: dict[str, list[PropagationContributor]],
        source: str,
        source_score: float,
        hop: int,
        frontier: dict[str, tuple[float, str, float, dict[str, Any]]],
    ) -> None:
        for target, (contribution, relationship, weight, detail) in frontier.items():
            self._add_contributor(
                signal_by_target,
                contributors,
                target,
                PropagationContributor(
                    source_entity_id=source,
                    relationship=relationship,
                    hop=hop,
                    contribution=contribution,
                    edge_weight=weight,
                    source_anomaly_score=source_score,
                    detail=detail,
                ),
            )

    @staticmethod
    def _add_contributor(
        signal_by_target: dict[str, float],
        contributors: dict[str, list[PropagationContributor]],
        target: str,
        contributor: PropagationContributor,
    ) -> None:
        signal_by_target[target] = signal_by_target.get(target, 0.0) + contributor.contribution
        contributors.setdefault(target, []).append(contributor)


risk_propagation_service = RiskPropagationService()
