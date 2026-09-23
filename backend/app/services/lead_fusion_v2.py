from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

import pandas as pd

from app.services.analysis import analysis_service
from app.services.entity_clustering import entity_clustering_service
from app.services.pattern_refinement_v2 import pattern_refinement_v2
from app.services.risk_propagation import risk_propagation_service
from app.services.artifacts import load_artifact, save_artifact


class LeadFusionV2:
    """Phase 5A: non-destructive multi-signal investigative lead fusion.

    Combines independent analytical outputs for wallet-level investigation
    candidates without changing the existing 150-lead production pipeline.
    Scores are transparent weighted evidence aggregates, not probabilities.
    """

    TOP_K = 150
    MIN_ANOMALY = 0.45
    MIN_PROPAGATED_RISK = 0.50
    MIN_PATTERN_PRIORITY = 60.0

    WEIGHTS = {
        "anomaly": 0.25,
        "propagatedRisk": 0.30,
        "patternEvidence": 0.35,
        "graphContext": 0.10,
    }

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, force: bool = False) -> dict[str, Any]:
        state = analysis_service.get_state()
        version = state.dataset_version
        with self._lock:
            if not force and version in self._cache:
                return self._cache[version]
        if not force:
            disk = load_artifact(version, "phase5a")
            if disk is not None:
                with self._lock:
                    self._cache[version] = disk
                return disk
        result = self._run(state)
        save_artifact(version, "phase5a", result)
        with self._lock:
            self._cache[version] = result
        return result

    def _run(self, state: Any) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        version = state.dataset_version

        propagation = risk_propagation_service.all(version)
        refinement = pattern_refinement_v2.get()
        graph_clusters = entity_clustering_service.get(version)

        promoted = [
            x for x in refinement["patterns"]
            if x["validationStatus"] == "promoted_candidate"
        ]

        # Pattern evidence is assigned to every referenced wallet. Keep the
        # strongest pattern score plus the number/type diversity as explanation.
        pattern_by_wallet: dict[str, list[dict[str, Any]]] = {}
        for pattern in promoted:
            for wallet in pattern.get("walletIds", []):
                pattern_by_wallet.setdefault(str(wallet), []).append(pattern)

        graph_cluster_by_wallet: dict[str, dict[str, Any]] = {}
        for cluster in graph_clusters.get("clusters", []):
            for wallet in cluster.get("memberWalletIds", []):
                graph_cluster_by_wallet[str(wallet)] = cluster

        # Existing leads are used only for comparison; they are never modified.
        existing_ids = {str(x.get("entityId")) for x in state.leads}
        rows: list[dict[str, Any]] = []
        for row in state.wallet_features.itertuples(index=False):
            wallet = str(row.entity_id)
            anomaly = self._bounded(getattr(row, "anomaly_score", 0.0))
            propagated_item = propagation.get(wallet, {})
            propagated = self._bounded(propagated_item.get("propagatedRisk", anomaly))

            patterns = sorted(
                pattern_by_wallet.get(wallet, []),
                key=lambda x: (-float(x.get("priorityScore", 0)), str(x.get("patternId", ""))),
            )
            top_pattern = patterns[0] if patterns else None
            pattern_priority = self._bounded((float(top_pattern["priorityScore"]) / 100.0) if top_pattern else 0.0)
            pattern_types = sorted({str(x["patternType"]) for x in patterns})
            pattern_count = len(patterns)
            # Multiple independent promoted pattern types strengthen the
            # evidence dimension, but it is capped so repeated patterns do not
            # dominate the lead score.
            diversity_bonus = min(0.20, max(0, len(pattern_types) - 1) * 0.10)
            pattern_evidence = min(1.0, pattern_priority * 0.80 + diversity_bonus)

            cluster = graph_cluster_by_wallet.get(wallet)
            if cluster:
                cluster_anomaly = self._bounded(cluster.get("avgAnomalyScore", 0.0))
                graph_context = 0.70 * cluster_anomaly + 0.30 * self._bounded(cluster.get("avgCommonInputStrength", 0.0))
            else:
                graph_context = 0.0

            network_diversity = min(1.0, float(getattr(row, "unique_ip_count", 0) or 0) / 5.0)
            graph_signal = self._bounded(propagated_item.get("graphPropagatedSignal", 0.0))
            score = 100.0 * (
                self.WEIGHTS["anomaly"] * anomaly
                + self.WEIGHTS["propagatedRisk"] * propagated
                + self.WEIGHTS["patternEvidence"] * pattern_evidence
                + self.WEIGHTS["graphContext"] * graph_context
            )

            eligible = bool(
                anomaly >= self.MIN_ANOMALY
                or propagated >= self.MIN_PROPAGATED_RISK
                or pattern_priority * 100.0 >= self.MIN_PATTERN_PRIORITY
            )
            if not eligible:
                continue

            independent_signal_count = sum([
                anomaly >= self.MIN_ANOMALY,
                propagated >= self.MIN_PROPAGATED_RISK,
                bool(patterns),
                bool(cluster),
            ])

            signals: list[str] = []
            evidence: list[dict[str, Any]] = []
            if anomaly >= self.MIN_ANOMALY:
                signals.append("ML anomaly signal")
                evidence.append({
                    "kind": "ML finding",
                    "source": "IsolationForest",
                    "metric": "anomaly_score",
                    "value": round(anomaly, 6),
                    "description": "Relative anomaly score produced by the existing unsupervised model.",
                })
            if propagated >= self.MIN_PROPAGATED_RISK:
                signals.append("Graph-propagated risk signal")
                evidence.append({
                    "kind": "graph finding",
                    "source": "RiskPropagationV2",
                    "metric": "propagatedRisk",
                    "value": round(propagated, 6),
                    "graphSignal": round(graph_signal, 6),
                    "contributors": propagated_item.get("contributors", [])[:5],
                    "description": "Bounded graph-derived signal propagated from anomalous wallet relationships.",
                })
            if patterns:
                signals.append("Validated behavioral pattern")
                evidence.append({
                    "kind": "pattern finding",
                    "source": "Phase4C",
                    "patternCount": pattern_count,
                    "patternTypes": pattern_types,
                    "topPatternId": top_pattern["patternId"],
                    "topPatternPriority": round(float(top_pattern["priorityScore"]), 2),
                    "description": "Promoted Phase 4C behavioral pattern evidence associated with the wallet.",
                })
            if cluster:
                signals.append("Graph-aware community context")
                evidence.append({
                    "kind": "cluster context",
                    "source": "Phase3",
                    "clusterId": cluster["id"],
                    "clusterWalletCount": int(cluster.get("walletCount", 0)),
                    "clusterAvgAnomalyScore": round(float(cluster.get("avgAnomalyScore", 0.0)), 6),
                    "avgCommonInputStrength": round(float(cluster.get("avgCommonInputStrength", 0.0)), 6),
                    "description": "Graph-aware cluster context; not itself a finding of wrongdoing.",
                })

            rows.append({
                "entityId": wallet,
                "entityLabel": wallet,
                "type": "wallet",
                "fusionScore": round(min(100.0, score), 2),
                "confidence": round(min(0.99, 0.40 + 0.15 * independent_signal_count + 0.25 * pattern_evidence), 3),
                "signalCount": independent_signal_count,
                "anomalyScore": round(anomaly, 6),
                "propagatedRisk": round(propagated, 6),
                "graphPropagatedSignal": round(graph_signal, 6),
                "patternEvidenceScore": round(pattern_evidence, 6),
                "graphContextScore": round(graph_context, 6),
                "networkDiversityScore": round(network_diversity, 6),
                "patternCount": pattern_count,
                "patternTypes": pattern_types,
                "patternIds": [x["patternId"] for x in patterns[:10]],
                "clusterId": cluster["id"] if cluster else "",
                "uniqueIpCount": int(getattr(row, "unique_ip_count", 0) or 0),
                "transactionCount": int(getattr(row, "transaction_count", 0) or 0),
                "signals": signals or ["Observed analytical signal"],
                "evidence": evidence,
                "contributors": propagated_item.get("contributors", [])[:5],
                "existingLead": wallet in existing_ids,
            })

        rows.sort(key=lambda x: (-x["fusionScore"], -x["signalCount"], x["entityId"]))
        for rank, row in enumerate(rows, 1):
            row["candidateRank"] = rank
            row["leadId"] = f"FUSION-{rank:04d}"
            row["priority"] = "high" if row["fusionScore"] >= 70 else "medium" if row["fusionScore"] >= 40 else "low"
            row["reviewReason"] = self._review_reason(row)

        top = rows[: self.TOP_K]
        for rank, row in enumerate(top, 1):
            row["rank"] = rank

        top_ids = {x["entityId"] for x in top}
        existing_overlap = sum(x["entityId"] in existing_ids for x in top)
        new_candidates = [x for x in top if x["entityId"] not in existing_ids]
        multi_signal = sum(x["signalCount"] >= 2 for x in top)
        triple_signal = sum(x["signalCount"] >= 3 for x in top)

        by_pattern_type: dict[str, int] = {}
        for row in top:
            for kind in row["patternTypes"]:
                by_pattern_type[kind] = by_pattern_type.get(kind, 0) + 1

        duration_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 2)
        return {
            "datasetVersion": version,
            "method": "Phase 5A transparent multi-signal investigative lead fusion",
            "destructive": False,
            "scoreSemantics": "Weighted evidence priority score from 0-100; not a probability and not a claim of wrongdoing.",
            "weights": dict(self.WEIGHTS),
            "eligibility": {
                "minimumAnomaly": self.MIN_ANOMALY,
                "minimumPropagatedRisk": self.MIN_PROPAGATED_RISK,
                "minimumPatternPriority": self.MIN_PATTERN_PRIORITY,
            },
            "sourceCounts": {
                "walletsAnalyzed": int(len(state.wallet_features)),
                "existingLeads": int(len(state.leads)),
                "phase4CPromotedPatterns": len(promoted),
                "graphAwareClusters": len(graph_clusters.get("clusters", [])),
            },
            "summary": {
                "eligibleWallets": len(rows),
                "fusionCandidates": len(top),
                "multiSignalCandidates": multi_signal,
                "tripleOrMoreSignalCandidates": triple_signal,
                "overlapWithExisting150Leads": existing_overlap,
                "newCandidatesOutsideExisting150": len(new_candidates),
                "meanFusionScoreTopK": round(sum(x["fusionScore"] for x in top) / max(len(top), 1), 2),
                "meanSignalCountTopK": round(sum(x["signalCount"] for x in top) / max(len(top), 1), 2),
                "patternTypeCoverage": by_pattern_type,
            },
            "candidates": top,
            "allEligibleCandidates": rows,
            "durationMs": duration_ms,
        }

    @staticmethod
    def _bounded(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value or 0.0)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _review_reason(row: dict[str, Any]) -> str:
        signals = row["signalCount"]
        types = ", ".join(row["patternTypes"][:3])
        if signals >= 3:
            return f"Convergence of {signals} independent analytical signal groups" + (f", including {types}" if types else "")
        if signals == 2:
            return "Convergence of two analytical signal groups; review supporting evidence"
        return "Single strong analytical signal; inspect underlying evidence before escalation"


lead_fusion_v2 = LeadFusionV2()
