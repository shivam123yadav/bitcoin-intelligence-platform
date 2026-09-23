"""Experimental graph-aware wallet/entity clustering.

This service deliberately sits beside the existing behavioral DBSCAN pipeline.
It does not overwrite ``wallet_features.cluster_id`` or change the existing
8-cluster baseline.  It exists so graph-aware clustering can be measured before
being considered for promotion into the main analysis pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from app.services.analysis import analysis_service
from app.services.graph import GraphService
from app.services.artifacts import load_artifact, save_artifact


PRODUCTION_DATASET_VERSION = "1.0.0"


@dataclass(frozen=True)
class GraphAwareConfig:
    eps: float = 1.45
    min_samples: int = 5
    graph_weight: float = 1.0


class EntityClusteringService:
    """Run a non-destructive graph-aware clustering experiment."""

    BEHAVIORAL_FEATURES = (
        "transaction_count",
        "input_volume",
        "output_volume",
        "unique_ip_count",
        "country_count",
        "asn_count",
        "transactions_per_day",
        "in_out_ratio",
        "anomaly_score",
    )
    GRAPH_FEATURES = (
        "graph_degree",
        "graph_unique_neighbors",
        "component_size",
        "common_input_degree",
        "common_input_transaction_count",
        "common_input_strength",
    )

    def __init__(self, graph_service: GraphService | None = None) -> None:
        self.graph_service = graph_service or GraphService()
        self.config = GraphAwareConfig()
        self._lock = threading.RLock()
        self._dataset_version: str | None = None
        self._result: dict[str, Any] | None = None

    def get(self, version: str | None = None, force: bool = False) -> dict[str, Any]:
        with self._lock:
            dataset_version = (
                version
                or self._dataset_version
                or PRODUCTION_DATASET_VERSION
            )

            if (
                not force
                and self._result is not None
                and self._dataset_version == dataset_version
            ):
                return self._result

            # Read the completed persisted artifact first. This is important
            # for production deployments where the local analysis runtime
            # state is intentionally not restored.
            if not force:
                disk = load_artifact(
                    dataset_version,
                    "phase3_graph_clusters",
                )
                if disk is not None:
                    self._dataset_version = dataset_version
                    self._result = disk
                    return disk

            # Only local analysis/recalculation should reach this point.
            state = analysis_service.get_state()
            dataset_version = version or state.dataset_version

            result = self._calculate(
                state.wallet_features,
                dataset_version,
            )
            save_artifact(
                dataset_version,
                "phase3_graph_clusters",
                result,
            )

            self._dataset_version = dataset_version
            self._result = result
            return result

    def clusters(self, version: str | None = None, force: bool = False) -> list[dict[str, Any]]:
        return self.get(version, force)["clusters"]

    def _calculate(self, wallet_df: pd.DataFrame, dataset_version: str) -> dict[str, Any]:
        df = wallet_df.copy()
        required = [*self.BEHAVIORAL_FEATURES, *self.GRAPH_FEATURES]
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise RuntimeError(f"Graph-aware clustering requires missing features: {missing}")

        x = df[required].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)
        # Heavy-tailed count/volume features are compressed before scaling.
        for column in required:
            if column != "common_input_strength":
                x[column] = np.log1p(np.clip(x[column], 0.0, None))

        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x)

        # Keep behavioral and graph contributions explicit.  A weight of 1.0
        # gives each graph feature the same standardized influence as a
        # behavioral feature while leaving the existing model untouched.
        graph_indexes = [required.index(column) for column in self.GRAPH_FEATURES]
        x_scaled[:, graph_indexes] *= self.config.graph_weight

        labels = DBSCAN(
            eps=self.config.eps,
            min_samples=self.config.min_samples,
            n_jobs=-1,
        ).fit_predict(x_scaled)

        df["graph_aware_cluster_label"] = labels
        clusters: list[dict[str, Any]] = []
        for label, group in df[df["graph_aware_cluster_label"] >= 0].groupby(
            "graph_aware_cluster_label"
        ):
            members = group.sort_values(
                ["anomaly_score", "entity_id"], ascending=[False, True]
            )
            member_ids = members["entity_id"].tolist()
            clusters.append(
                {
                    "id": f"GC-{int(label):03d}",
                    "name": f"Graph-aware entity cluster {int(label):03d}",
                    "walletCount": len(member_ids),
                    "memberWalletIds": member_ids,
                    "avgAnomalyScore": round(float(members["anomaly_score"].mean()), 6),
                    "totalVolumeBtc": round(float(members["total_volume"].sum()), 8),
                    "avgCommonInputStrength": round(
                        float(members["common_input_strength"].mean()), 6
                    ),
                    "avgGraphDegree": round(float(members["graph_degree"].mean()), 6),
                    "avgCommonInputDegree": round(
                        float(members["common_input_degree"].mean()), 6
                    ),
                }
            )

        clusters.sort(key=lambda item: (-item["avgAnomalyScore"], item["id"]))
        label_to_id = {
            int(cluster["id"].split("-")[-1]): cluster["id"] for cluster in clusters
        }

        non_noise = labels >= 0
        unique_labels = sorted(set(int(x) for x in labels if x >= 0))
        silhouette = None
        silhouette_sample_size = 0
        if len(unique_labels) >= 2 and int(non_noise.sum()) > len(unique_labels):
            try:
                non_noise_x = x_scaled[non_noise]
                non_noise_labels = labels[non_noise]

                # Silhouette score requires pairwise distances. Running it over
                # all 10k+ wallets creates an O(n^2) dense matrix and can
                # exceed memory on a normal SIH demo machine. Keep the metric
                # deterministic while bounding its memory use.
                silhouette_sample_size = min(2000, len(non_noise_x))
                silhouette = round(
                    float(
                        silhouette_score(
                            non_noise_x,
                            non_noise_labels,
                            sample_size=silhouette_sample_size,
                            random_state=26146,
                        )
                    ),
                    6,
                )
            except ValueError:
                silhouette = None
                silhouette_sample_size = 0

        existing_labels = (
            pd.to_numeric(df.get("cluster_label", pd.Series([-1] * len(df))), errors="coerce")
            .fillna(-1)
            .to_numpy(dtype=int)
        )
        existing_non_noise = existing_labels >= 0
        existing_cluster_labels = sorted(set(int(x) for x in existing_labels if x >= 0))
        ari = round(float(adjusted_rand_score(existing_labels, labels)), 6)

        graph = self.graph_service.get_graph()
        common_edges = 0
        internal_common_edges = 0
        entity_to_label = {
            str(entity_id): int(label)
            for entity_id, label in zip(df["entity_id"].tolist(), labels.tolist())
        }
        for source, target, _, attrs in graph.edges(keys=True, data=True):
            if attrs.get("relationship") != "common_input_association":
                continue
            source_id = str(graph.nodes[source].get("entity_id", source)).removeprefix("wallet:")
            target_id = str(graph.nodes[target].get("entity_id", target)).removeprefix("wallet:")
            if source_id not in entity_to_label or target_id not in entity_to_label:
                continue
            common_edges += 1
            source_label = entity_to_label[source_id]
            target_label = entity_to_label[target_id]
            if source_label >= 0 and source_label == target_label:
                internal_common_edges += 1

        noise_count = int((labels < 0).sum())
        cluster_sizes = sorted((len(cluster["memberWalletIds"]) for cluster in clusters), reverse=True)
        metrics = {
            "walletCount": int(len(df)),
            "clusterCount": int(len(clusters)),
            "existingClusterCount": int(len(existing_cluster_labels)),
            "existingNoiseWalletCount": int((~existing_non_noise).sum()),
            "noiseWalletCount": noise_count,
            "noiseRate": round(noise_count / max(len(df), 1), 6),
            "largestClusterSize": int(cluster_sizes[0]) if cluster_sizes else 0,
            "medianClusterSize": float(np.median(cluster_sizes)) if cluster_sizes else 0.0,
            "silhouetteScore": silhouette,
            "silhouetteSampleSize": silhouette_sample_size,
            "silhouetteMethod": "deterministic_sample",
            "adjustedRandAgainstExisting": ari,
            "commonInputEdgeCount": common_edges,
            "internalCommonInputEdgeCount": internal_common_edges,
            "internalCommonInputEdgeRate": round(
                internal_common_edges / common_edges, 6
            ) if common_edges else 0.0,
        }

        # Deterministic compact assignment map is useful for comparison and
        # future frontend integration, while the original cluster_id remains
        # untouched.
        assignments = {
            str(row.entity_id): label_to_id.get(int(row.graph_aware_cluster_label), "")
            for row in df[["entity_id", "graph_aware_cluster_label"]].itertuples(index=False)
        }

        return {
            "datasetVersion": dataset_version,
            "method": "DBSCAN graph-aware experiment",
            "config": {
                "eps": self.config.eps,
                "minSamples": self.config.min_samples,
                "graphWeight": self.config.graph_weight,
                "behavioralFeatures": list(self.BEHAVIORAL_FEATURES),
                "graphFeatures": list(self.GRAPH_FEATURES),
            },
            "metrics": metrics,
            "clusters": clusters,
            "assignments": assignments,
        }


entity_clustering_service = EntityClusteringService()
