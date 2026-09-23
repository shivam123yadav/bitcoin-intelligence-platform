from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

import numpy as np
import pandas as pd

from app.services.analysis import analysis_service
from app.services.graph import GraphService, EntityNotFoundError
from app.services.lead_fusion_v2 import lead_fusion_v2
from app.services.lead_validation_v2 import lead_validation_v2
from app.services.pattern_refinement_v2 import pattern_refinement_v2
from app.services.artifacts import load_artifact, save_artifact


PRODUCTION_DATASET_VERSION = "1.0.0"


def _safe_seq(value: Any) -> list[Any]:
    """Normalize parquet/pandas list-like values without ambiguous truth checks."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    return list(value) if isinstance(value, pd.Series) else [value]


class LeadExplainabilityV2:
    """Phase 5C: final investigative lead ranking and explainability.

    This is a non-destructive presentation/ranking layer over the validated
    Phase 5A candidates and Phase 5B audit. The final score is an investigative
    priority score, not a probability and not a finding of wrongdoing.
    """

    TOP_K = 150

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._graph = GraphService()

    def get(self, force: bool = False) -> dict[str, Any]:
        # Production deployment does not have the local analysis runtime.
        # Load the completed Phase 5C artifact directly for normal requests.
        version = PRODUCTION_DATASET_VERSION

        with self._lock:
            if not force and version in self._cache:
                return self._cache[version]

        # Normal read-only requests must use the completed artifact instead
        # of triggering the expensive Phase 4/5 analysis chain.
        if not force:
            disk = load_artifact(version, "phase5c")
            if disk is not None:
                with self._lock:
                    self._cache[version] = disk
                return disk

        # Explicit force/local analysis can use the runtime analysis state.
        state = analysis_service.get_state()
        version = state.dataset_version

        if not force:
            disk = load_artifact(version, "phase5c")
            if disk is not None:
                with self._lock:
                    self._cache[version] = disk
                return disk

        try:
            result = self._run(state)
        except Exception as exc:
            result = self._legacy_fallback(state, str(exc))

        save_artifact(version, "phase5c", result)

        with self._lock:
            self._cache[version] = result

        return result

    def _legacy_fallback(self, state: Any, reason: str) -> dict[str, Any]:
        """Create a stable Phase 5C compatibility view from persisted run data.

        This path is intentionally read-only and deterministic. It is used only
        when a completed run predates the Phase 4/5 artifact files or when a
        legacy artifact chain cannot be loaded safely. It does not claim to
        recreate validated behavioral patterns; those are left empty rather
        than being invented. The persisted anomaly score and graph/cluster
        fields remain useful investigative signals for the SIH dashboard.
        """
        frame = state.wallet_features.copy()
        if "entity_id" not in frame.columns or frame.empty:
            return {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "version": "phase5c-compat-1",
                "summary": {"finalLeads": 0, "compatibilityMode": True},
                "leads": [],
                "warnings": ["No persisted wallet feature rows are available."],
            }

        score_col = "anomaly_score" if "anomaly_score" in frame.columns else None
        if score_col:
            frame[score_col] = pd.to_numeric(frame[score_col], errors="coerce").fillna(0.0)
        else:
            frame["_compat_score"] = 0.0
            score_col = "_compat_score"
        frame = frame.sort_values(
            [score_col, "entity_id"], ascending=[False, True], kind="mergesort"
        ).head(self.TOP_K)

        leads: list[dict[str, Any]] = []
        for idx, (_, row) in enumerate(frame.iterrows(), 1):
            entity_id = str(row.get("entity_id", ""))
            anomaly = max(0.0, min(1.0, float(row.get(score_col, 0.0) or 0.0)))
            priority_score = round(anomaly * 100.0, 2)
            cluster_id = row.get("cluster_id")
            tx_count = int(row.get("transaction_count", 0) or 0)
            ip_count = int(row.get("unique_ip_count", 0) or 0)
            first_seen = str(row.get("first_seen", ""))
            last_seen = str(row.get("last_activity", ""))
            leads.append({
                "leadId": f"COMPAT-{idx:04d}",
                "entityId": entity_id,
                "entityLabel": entity_id,
                "type": "wallet",
                "rank": idx,
                "finalPriorityScore": priority_score,
                "priority": "high" if priority_score >= 70 else "medium" if priority_score >= 40 else "low",
                "scoreSemantics": "Investigative priority score derived from persisted anomaly evidence; not a probability and not a claim of wrongdoing.",
                "analyticalConfidenceIndicator": round(anomaly, 4),
                "signalBreakdown": {
                    "fusionScore": priority_score,
                    "anomalyScore": round(anomaly, 4),
                    "propagatedRisk": 0.0,
                    "patternEvidenceScore": 0.0,
                    "graphContextScore": 0.0,
                    "networkDiversityScore": 0.0,
                    "evidenceCompleteness": 0.0,
                    "independentSignalGroups": 1 if anomaly > 0 else 0,
                    "topKStability": 0.0,
                },
                "validatedPatterns": [],
                "validatedPatternInstances": [],
                "supportingEntities": {"wallets": [entity_id], "transactions": [], "ips": []},
                "supportingTransactions": [],
                "networkObservations": {
                    "ips": [], "countries": _safe_seq(row.get("countries", []))[:50],
                    "asns": _safe_seq(row.get("asns", []))[:50],
                    "observationCount": tx_count, "transactionCount": tx_count,
                },
                "graphContext": {
                    "clusterId": str(cluster_id) if cluster_id is not None else None,
                    "clusterLabel": str(cluster_id) if cluster_id is not None else None,
                    "neighborCount": 0,
                },
                "temporalRange": {"firstSeen": first_seen, "lastSeen": last_seen},
                "evidenceProvenance": {
                    "mode": "persisted-run-compatibility",
                    "source": state.run_id,
                    "note": "Phase 4/5 artifacts were unavailable; no behavioral pattern was inferred in compatibility mode.",
                },
                "warnings": [
                    "Compatibility mode: validated Phase 4/5 behavioral-pattern artifacts were unavailable.",
                    "Priority is based on the persisted anomaly signal only.",
                ],
                "reviewClassification": "requires_analyst_review",
                "existingLead": False,
                "explanation": f"Persisted anomaly evidence produced an investigative priority of {priority_score:.2f}. Phase 4/5 validation artifacts were unavailable after restart; the system therefore did not infer additional patterns. Compatibility reason: {reason[:300]}",
            })

        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "version": "phase5c-compat-1",
            "datasetVersion": state.dataset_version,
            "summary": {
                "finalLeads": len(leads),
                "highPriority": sum(x["priority"] == "high" for x in leads),
                "mediumPriority": sum(x["priority"] == "medium" for x in leads),
                "lowPriority": sum(x["priority"] == "low" for x in leads),
                "compatibilityMode": True,
            },
            "warnings": [
                "Phase 5C compatibility mode is active because persisted Phase 4/5 artifacts were unavailable or could not be loaded.",
                "No validated behavioral pattern is claimed by this compatibility result.",
            ],
            "dependenceAudit": {},
            "rankingStability": {},
            "leads": leads,
        }

    def get_entity(self, entity_id: str, force: bool = False) -> dict[str, Any] | None:
        result = self.get(force=force)
        for lead in result["leads"]:
            if lead["entityId"] == entity_id:
                return lead
        return None

    def _run(self, state: Any) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        fusion = lead_fusion_v2.get(force=False)
        audit = lead_validation_v2.get(force=False)
        refinement = pattern_refinement_v2.get(force=False)

        candidates = list(fusion.get("candidates", []))
        audits = {str(x["entityId"]): x for x in audit.get("candidates", [])}
        promoted = {
            str(x["patternId"]): x
            for x in refinement.get("patterns", [])
            if x.get("validationStatus") == "promoted_candidate"
        }

        # Only load observations that can contribute context to the 150 final
        # candidates. The old implementation loaded and materialized all 48k
        # observations here on every cold process, which could exhaust a small
        # deployment even though scoring itself uses cached Phase 5A/5B output.
        tx_map, wallet_ips, wallet_network = self._build_targeted_observation_maps(
            state.dataset_version, candidates, promoted
        )

        leads: list[dict[str, Any]] = []
        for candidate in candidates:
            entity_id = str(candidate["entityId"])
            audit_row = audits.get(entity_id, {})
            pattern_ids = [str(x) for x in candidate.get("patternIds", [])]
            patterns = [
                promoted[pid]
                for pid in pattern_ids
                if pid in promoted
            ]

            evidence_completeness = self._b(audit_row.get("evidenceCompleteness"))
            topk_stability = self._b(audit.get("rankingStability", {}).get("meanTopKStability"))
            independent_groups = int(audit_row.get("independentSignalGroups", 0) or 0)
            independence_indicator = min(1.0, independent_groups / 3.0)

            # Phase 5C score deliberately keeps the Phase 5A fusion as the
            # dominant input. Audit quality/stability refine the priority rather
            # than creating a new probability-like model.
            fusion_score = float(candidate.get("fusionScore", 0.0) or 0.0)
            final_score = (
                0.70 * fusion_score
                + 15.0 * evidence_completeness
                + 10.0 * topk_stability
                + 5.0 * independence_indicator
            )
            final_score = round(max(0.0, min(100.0, final_score)), 2)

            tx_ids = self._supporting_transaction_ids(candidate, patterns, state)
            tx_context = [tx_map[x] for x in tx_ids if x in tx_map][:20]

            ips = sorted(wallet_ips.get(entity_id, set()))
            network = wallet_network.get(entity_id, {})
            graph_context = self._graph_context(entity_id)

            provenance = self._provenance(candidate, audit_row, patterns, network)
            warnings = self._warnings(candidate, audit_row, patterns, audit)
            review_classification = self._review_classification(
                audit_row, warnings, evidence_completeness
            )

            explanation = self._explanation(
                candidate=candidate,
                audit_row=audit_row,
                patterns=patterns,
                network=network,
                graph_context=graph_context,
                warnings=warnings,
                review_classification=review_classification,
            )

            leads.append({
                "leadId": str(candidate["leadId"]),
                "entityId": entity_id,
                "entityLabel": str(candidate.get("entityLabel", entity_id)),
                "type": "wallet",
                "rank": 0,
                "finalPriorityScore": final_score,
                "priority": (
                    "high" if final_score >= 70
                    else "medium" if final_score >= 40
                    else "low"
                ),
                "scoreSemantics": "Investigative priority score from 0-100; not a probability and not a claim of wrongdoing.",
                "analyticalConfidenceIndicator": self._confidence_indicator(
                    candidate, audit_row, evidence_completeness
                ),
                "signalBreakdown": {
                    "fusionScore": round(fusion_score, 2),
                    "anomalyScore": self._b(candidate.get("anomalyScore")),
                    "propagatedRisk": self._b(candidate.get("propagatedRisk")),
                    "patternEvidenceScore": self._b(candidate.get("patternEvidenceScore")),
                    "graphContextScore": self._b(candidate.get("graphContextScore")),
                    "networkDiversityScore": self._b(candidate.get("networkDiversityScore")),
                    "evidenceCompleteness": round(evidence_completeness, 4),
                    "independentSignalGroups": independent_groups,
                    "topKStability": round(topk_stability, 4),
                },
                # Keep individual pattern evidence available, but expose the
                # investigator-facing validatedPatterns list as one entry per
                # pattern type. This avoids UI output such as the same
                # ``peeling_chain`` label appearing ten times while preserving
                # the underlying pattern IDs in validatedPatternInstances.
                "validatedPatterns": self._pattern_type_summaries(patterns),
                "validatedPatternInstances": [
                    {
                        "patternId": p["patternId"],
                        "patternType": p["patternType"],
                        "priorityScore": p["priorityScore"],
                        "confidenceScore": p["confidenceScore"],
                        "evidenceSupportScore": p["evidenceSupportScore"],
                        "confidenceEvidenceGap": p["confidenceEvidenceGap"],
                        "overlapGroup": p.get("overlapGroup"),
                        "supportingWalletCount": p["supportingWalletCount"],
                        "supportingTransactionCount": p["supportingTransactionCount"],
                        "supportingIpEvidence": bool(p["supportingIpEvidence"]),
                        "temporalConsistent": bool(p["temporalConsistent"]),
                        "validationNotes": p.get("validationNotes", []),
                    }
                    for p in patterns
                ],
                "supportingEntities": {
                    "wallets": sorted({
                        w
                        for p in patterns
                        for w in p.get("walletIds", [])
                    } | {entity_id})[:50],
                    "transactions": tx_ids[:50],
                    "ips": ips[:50],
                },
                "supportingTransactions": tx_context,
                "networkObservations": {
                    "ips": ips[:50],
                    "countries": network.get("countries", [])[:50],
                    "asns": network.get("asns", [])[:50],
                    "observationCount": network.get("observationCount", 0),
                    "transactionCount": network.get("transactionCount", 0),
                },
                "graphContext": graph_context,
                "temporalRange": self._temporal_range(candidate, tx_context),
                "evidenceProvenance": provenance,
                "warnings": warnings,
                "reviewClassification": review_classification,
                "existingLead": bool(candidate.get("existingLead", False)),
                "explanation": explanation,
            })

        leads.sort(
            key=lambda x: (
                -x["finalPriorityScore"],
                -x["signalBreakdown"]["fusionScore"],
                x["entityId"],
            )
        )
        for rank, lead in enumerate(leads, 1):
            lead["rank"] = rank

        summary = {
            "finalLeads": len(leads),
            "highPriority": sum(x["priority"] == "high" for x in leads),
            "mediumPriority": sum(x["priority"] == "medium" for x in leads),
            "lowPriority": sum(x["priority"] == "low" for x in leads),
            "existingLeadOverlap": sum(bool(x["existingLead"]) for x in leads),
            "newCandidatesOutsideExisting150": sum(not x["existingLead"] for x in leads),
            "reviewQueue": sum(
                x["reviewClassification"] in {"review", "high_concentration"}
                for x in leads
            ),
            "meanFinalPriorityScore": round(
                sum(x["finalPriorityScore"] for x in leads) / max(len(leads), 1), 2
            ),
            "meanEvidenceCompleteness": round(
                sum(x["signalBreakdown"]["evidenceCompleteness"] for x in leads)
                / max(len(leads), 1), 4
            ),
            "meanIndependentSignalGroups": round(
                sum(x["signalBreakdown"]["independentSignalGroups"] for x in leads)
                / max(len(leads), 1), 3
            ),
            "meanTopKStability": audit.get("rankingStability", {}).get(
                "meanTopKStability", 0.0
            ),
        }

        duration_ms = round(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000, 2
        )
        return {
            "datasetVersion": state.dataset_version,
            "method": "Phase 5C final investigative lead ranking and explainability",
            "destructive": False,
            "scoreSemantics": "Final investigative priority score from 0-100; not a probability and not a claim of wrongdoing.",
            "rankingMethod": {
                "fusionWeight": 0.70,
                "evidenceCompletenessWeight": 0.15,
                "rankingStabilityWeight": 0.10,
                "effectiveSignalGroupWeight": 0.05,
            },
            "semantics": {
                "observedFact": "Directly observed dataset value or observation.",
                "derivedFeature": "Feature calculated from observed data.",
                "mlFinding": "Output of the existing unsupervised anomaly model.",
                "behavioralPattern": "Validated Phase 4C detector output.",
                "investigativePriority": "Evidence-priority ordering for analyst review, not a probability or conclusion.",
            },
            "summary": summary,
            "dependenceAudit": audit.get("dependence", {}),
            "rankingStability": audit.get("rankingStability", {}),
            "leads": leads,
            "durationMs": duration_ms,
        }

    @staticmethod
    def _pattern_type_summaries(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggregate validated pattern instances by detector type for display.

        The underlying instances remain available separately so aggregation is
        presentation-only and does not discard evidence.
        """
        grouped: dict[str, list[dict[str, Any]]] = {}
        for pattern in patterns:
            grouped.setdefault(str(pattern.get("patternType", "unknown")), []).append(pattern)

        summaries: list[dict[str, Any]] = []
        for pattern_type in sorted(grouped):
            items = grouped[pattern_type]
            summaries.append({
                "patternType": pattern_type,
                "instanceCount": len(items),
                "patternIds": [str(x.get("patternId")) for x in items],
                "meanPriorityScore": round(
                    sum(float(x.get("priorityScore", 0) or 0) for x in items) / max(len(items), 1), 2
                ),
                "meanConfidenceScore": round(
                    sum(float(x.get("confidenceScore", 0) or 0) for x in items) / max(len(items), 1), 4
                ),
                "meanEvidenceSupportScore": round(
                    sum(float(x.get("evidenceSupportScore", 0) or 0) for x in items) / max(len(items), 1), 4
                ),
                "supportingWalletCount": len({
                    wallet
                    for x in items
                    for wallet in x.get("walletIds", [])
                }),
                "supportingTransactionCount": len({
                    txid
                    for x in items
                    for txid in x.get("transactionIds", [])
                }),
                "supportingIpEvidence": any(bool(x.get("supportingIpEvidence")) for x in items),
                "temporalConsistent": all(bool(x.get("temporalConsistent")) for x in items),
            })
        return summaries

    @staticmethod
    def _build_targeted_observation_maps(
        version: str,
        candidates: list[dict[str, Any]],
        promoted: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[str, dict[str, Any]]]:
        """Read only rows relevant to final-lead provenance from DuckDB.

        This avoids materializing the complete normalized dataset in pandas
        during a read-only Phase 5C request.
        """
        import duckdb
        from app.services.paths import NORMALIZED_STORAGE_ROOT

        wallets: set[str] = {str(x.get("entityId")) for x in candidates}
        for candidate in candidates:
            for pattern_id in candidate.get("patternIds", []):
                pattern = promoted.get(str(pattern_id))
                if pattern:
                    wallets.update(str(x) for x in pattern.get("walletIds", []) if x)

        path = NORMALIZED_STORAGE_ROOT / f"observations_v{version}.duckdb"
        if not path.is_file() or not wallets:
            return {}, {}, {}

        con = duckdb.connect(str(path), read_only=True)
        try:
            rows = con.execute(
                """
                SELECT timestamp, src_ip, dst_ip, txid, input_addresses,
                       output_addresses, input_amounts, output_amounts, fee,
                       script_type, geo_country, asn, source_record_id
                FROM observations
                WHERE list_has_any(input_addresses, ?)
                   OR list_has_any(output_addresses, ?)
                ORDER BY timestamp, source_record_id
                """,
                [sorted(wallets), sorted(wallets)],
            ).fetchall()
            columns = [
                "timestamp", "src_ip", "dst_ip", "txid", "input_addresses",
                "output_addresses", "input_amounts", "output_amounts", "fee",
                "script_type", "geo_country", "asn", "source_record_id",
            ]
        finally:
            con.close()

        tx_map: dict[str, dict[str, Any]] = {}
        wallet_ips: dict[str, set[str]] = {}
        network: dict[str, dict[str, Any]] = {}
        for values in rows:
            row = dict(zip(columns, values))
            txid = str(row.get("txid", "") or "")
            if not txid:
                continue
            inputs = [str(x) for x in _safe_seq(row.get("input_addresses")) if x]
            outputs = [str(x) for x in _safe_seq(row.get("output_addresses")) if x]
            wallets_in_row = set(inputs + outputs)
            ips = {str(x) for x in (row.get("src_ip"), row.get("dst_ip")) if x}
            tx_map[txid] = {
                "txid": txid,
                "timestamp": str(row.get("timestamp")) if row.get("timestamp") is not None else None,
                "inputWallets": sorted(set(inputs)),
                "outputWallets": sorted(set(outputs)),
                "inputAmounts": [float(x) for x in _safe_seq(row.get("input_amounts"))],
                "outputAmounts": [float(x) for x in _safe_seq(row.get("output_amounts"))],
                "fee": float(row.get("fee") or 0.0),
                "scriptType": row.get("script_type"),
                "ips": sorted(ips),
                "srcIp": str(row.get("src_ip") or ""),
                "dstIp": str(row.get("dst_ip") or ""),
                "geoCountry": str(row.get("geo_country") or ""),
                "asn": str(row.get("asn") or ""),
                "sourceRecordId": str(row.get("source_record_id") or ""),
            }
            for wallet in wallets_in_row:
                wallet_ips.setdefault(wallet, set()).update(ips)
                item = network.setdefault(wallet, {
                    "countries": set(), "asns": set(), "observationCount": 0,
                    "transactionIds": set(),
                })
                if row.get("geo_country"):
                    item["countries"].add(str(row["geo_country"]))
                if row.get("asn"):
                    item["asns"].add(str(row["asn"]))
                item["observationCount"] += 1
                item["transactionIds"].add(txid)

        for item in network.values():
            item["countries"] = sorted(item["countries"])
            item["asns"] = sorted(item["asns"])
            item["transactionCount"] = len(item["transactionIds"])
            item["transactionIds"] = sorted(item["transactionIds"])
        return tx_map, wallet_ips, network

    @staticmethod
    def _build_observation_maps(
        df: pd.DataFrame,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[str, dict[str, Any]]]:
        tx_map: dict[str, dict[str, Any]] = {}
        wallet_ips: dict[str, set[str]] = {}
        network: dict[str, dict[str, Any]] = {}

        for row in df.to_dict("records"):
            txid = str(row.get("txid", "") or "")
            if not txid:
                continue
            ts = row.get("timestamp")
            inputs = [str(x) for x in _safe_seq(row.get("input_addresses")) if x]
            outputs = [str(x) for x in _safe_seq(row.get("output_addresses")) if x]
            wallets = set(inputs + outputs)
            ips = {
                str(x)
                for x in (row.get("src_ip"), row.get("dst_ip"))
                if x
            }
            tx_map[txid] = {
                "txid": txid,
                "timestamp": str(ts) if ts is not None else None,
                "inputWallets": sorted(set(inputs)),
                "outputWallets": sorted(set(outputs)),
                "inputAmounts": [float(x) for x in _safe_seq(row.get("input_amounts"))],
                "outputAmounts": [float(x) for x in _safe_seq(row.get("output_amounts"))],
                "fee": float(row.get("fee") or 0.0),
                "scriptType": row.get("script_type"),
                "ips": sorted(ips),
                "srcIp": str(row.get("src_ip") or ""),
                "dstIp": str(row.get("dst_ip") or ""),
                "geoCountry": str(row.get("geo_country") or ""),
                "asn": str(row.get("asn") or ""),
                "sourceRecordId": str(row.get("source_record_id") or ""),
            }
            for wallet in wallets:
                wallet_ips.setdefault(wallet, set()).update(ips)
                item = network.setdefault(
                    wallet,
                    {"countries": set(), "asns": set(), "observationCount": 0, "transactionIds": set()},
                )
                item["countries"].add(str(row.get("geo_country") or ""))
                item["asns"].add(str(row.get("asn") or ""))
                item["observationCount"] += 1
                item["transactionIds"].add(txid)

        for wallet, item in network.items():
            item["countries"] = sorted(x for x in item["countries"] if x)
            item["asns"] = sorted(x for x in item["asns"] if x)
            item["transactionCount"] = len(item["transactionIds"])
            del item["transactionIds"]

        return tx_map, wallet_ips, network

    @staticmethod
    def _supporting_transaction_ids(
        candidate: dict[str, Any],
        patterns: list[dict[str, Any]],
        state: Any,
    ) -> list[str]:
        ids: set[str] = set()
        for pattern in patterns:
            ids.update(str(x) for x in pattern.get("transactionIds", []) if x)
        if not ids:
            for txid in candidate.get("supportingTransactionIds", []) or []:
                ids.add(str(txid))
        if not ids:
            row = state.wallet_features[
                state.wallet_features["entity_id"] == candidate["entityId"]
            ]
            if not row.empty:
                ids.update(str(x) for x in _safe_seq(row.iloc[0].get("transaction_ids")))
        return sorted(ids)

    def _graph_context(self, entity_id: str) -> dict[str, Any]:
        try:
            result = self._graph.neighborhood(
                "wallet",
                entity_id,
                depth=1,
                limit=50,
            )
            neighbors = []
            for node in result.get("nodes", []):
                if node.get("entity_id") == entity_id:
                    continue
                neighbors.append({
                    "id": node.get("entity_id", node.get("id")),
                    "type": node.get("type"),
                })
            relationships = []
            for edge in result.get("edges", [])[:50]:
                relationships.append({
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "relationship": edge.get("relationship"),
                    "relationshipClass": edge.get("relationship_class"),
                    "txid": edge.get("txid"),
                    "txids": edge.get("txids", []),
                    "firstSeen": edge.get("first_seen"),
                    "lastSeen": edge.get("last_seen"),
                    "observationCount": edge.get("observation_count", 0),
                })
            return {
                "neighborCount": len(neighbors),
                "neighbors": neighbors,
                "relationships": relationships,
                "depth": 1,
            }
        except (EntityNotFoundError, KeyError):
            return {"neighborCount": 0, "neighbors": [], "relationships": [], "depth": 1}

    @staticmethod
    def _temporal_range(candidate: dict[str, Any], transactions: list[dict[str, Any]]) -> dict[str, Any]:
        timestamps = [
            str(x["timestamp"])
            for x in transactions
            if x.get("timestamp")
        ]
        if timestamps:
            return {"firstSeen": min(timestamps), "lastSeen": max(timestamps)}
        return {"firstSeen": None, "lastSeen": None}

    @staticmethod
    def _provenance(
        candidate: dict[str, Any],
        audit_row: dict[str, Any],
        patterns: list[dict[str, Any]],
        network: dict[str, Any],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [
            {
                "stage": "observedFact",
                "source": "frozen observation dataset",
                "items": ["wallet identity", "transaction references", "IP/network observations"],
            },
            {
                "stage": "derivedFeature",
                "source": "AnalysisService",
                "items": [
                    "transaction activity",
                    "network diversity",
                    "anomaly features",
                ],
            },
            {
                "stage": "mlFinding",
                "source": "IsolationForest",
                "items": ["anomaly score"],
            },
        ]
        if candidate.get("propagatedRisk", 0) > 0:
            out.append({
                "stage": "derivedFeature",
                "source": "RiskPropagationV2",
                "items": ["bounded graph-propagated risk"],
            })
        if patterns:
            out.append({
                "stage": "behavioralPattern",
                "source": "Phase4C",
                "items": sorted({p["patternType"] for p in patterns}),
            })
        out.append({
            "stage": "investigativePriority",
            "source": "Phase5C",
            "items": ["final priority score and review ordering"],
        })
        return out

    @staticmethod
    def _warnings(
        candidate: dict[str, Any],
        audit_row: dict[str, Any],
        patterns: list[dict[str, Any]],
        audit: dict[str, Any],
    ) -> list[str]:
        warnings: list[str] = []
        if candidate.get("propagatedRisk", 0) > 0 and candidate.get("anomalyScore", 0) > 0:
            warnings.append(
                "Propagated risk is seeded by anomaly signals; do not count these as fully independent evidence."
            )
        if len(patterns) > 1:
            warnings.append(
                "Multiple patterns may share underlying wallets or transactions; pattern convergence is not necessarily independent evidence."
            )
        if audit_row.get("patternConcentration", 0) > 0.75:
            warnings.append("High pattern concentration; review overlapping detector evidence.")
        if audit.get("dependence", {}).get("maxAbsoluteOffDiagonal", 0) > 0.90:
            warnings.append(
                "Phase 5B detected strong dependence among some signal dimensions; ranking should be interpreted as evidence aggregation, not independent proof."
            )
        if not candidate.get("existingLead", False):
            warnings.append("Candidate is outside the original 150-lead production queue.")
        return warnings

    @staticmethod
    def _review_classification(
        audit_row: dict[str, Any],
        warnings: list[str],
        completeness: float,
    ) -> str:
        base = str(audit_row.get("reviewClassification", "review"))
        if completeness < 0.75:
            return "review"
        if base == "high_concentration":
            return "high_concentration"
        if warnings and audit_row.get("patternConcentration", 0) > 0.75:
            return "high_concentration"
        return base if base in {"validated", "review", "high_concentration"} else "review"

    @staticmethod
    def _confidence_indicator(
        candidate: dict[str, Any],
        audit_row: dict[str, Any],
        completeness: float,
    ) -> dict[str, Any]:
        source_conf = float(candidate.get("confidence", 0.0) or 0.0)
        evidence = float(audit_row.get("evidenceCompleteness", completeness) or completeness)
        gap = abs(source_conf - evidence)
        label = "high" if evidence >= 0.90 and gap <= 0.20 else "moderate" if evidence >= 0.75 else "limited"
        return {
            "label": label,
            "sourceConfidence": round(source_conf, 3),
            "evidenceCompleteness": round(evidence, 4),
            "confidenceEvidenceGap": round(gap, 4),
            "semantics": "Analytical confidence/evidence indicator; not a probability.",
        }

    @staticmethod
    def _explanation(
        candidate: dict[str, Any],
        audit_row: dict[str, Any],
        patterns: list[dict[str, Any]],
        network: dict[str, Any],
        graph_context: dict[str, Any],
        warnings: list[str],
        review_classification: str,
    ) -> str:
        parts = []
        anomaly = float(candidate.get("anomalyScore", 0) or 0)
        propagated = float(candidate.get("propagatedRisk", 0) or 0)
        if anomaly >= 0.45:
            parts.append(f"anomaly score {anomaly:.3f}")
        if propagated >= 0.50:
            parts.append(f"graph-propagated risk {propagated:.3f}")
        if patterns:
            kinds = ", ".join(sorted({p["patternType"] for p in patterns}))
            parts.append(f"validated behavioral pattern evidence ({kinds})")
        if network.get("observationCount", 0):
            parts.append(
                f"{network['observationCount']} observed network-layer records across "
                f"{len(network.get('countries', []))} countries and {len(network.get('asns', []))} ASNs"
            )
        if graph_context.get("neighborCount", 0):
            parts.append(f"{graph_context['neighborCount']} graph-context neighbors")

        if parts:
            text = "This wallet is prioritized because the analyzed data shows " + "; ".join(parts) + "."
        else:
            text = "This wallet is prioritized from the available analytical evidence."

        text += (
            f" The Phase 5C investigative priority score is "
            f"{float(candidate.get('fusionScore', 0)):.2f}-anchored and refined with evidence completeness and ranking stability."
        )
        if review_classification != "validated":
            text += f" Review classification: {review_classification}."
        if warnings:
            text += " " + warnings[0]
        return text

    @staticmethod
    def _b(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value or 0.0)))
        except (TypeError, ValueError):
            return 0.0


lead_explainability_v2 = LeadExplainabilityV2()

