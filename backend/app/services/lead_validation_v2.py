from __future__ import annotations

from datetime import datetime, timezone
import math
import threading
from typing import Any

import numpy as np

from app.services.analysis import analysis_service
from app.services.lead_fusion_v2 import lead_fusion_v2
from app.services.artifacts import load_artifact, save_artifact


class LeadValidationV2:
    """Phase 5B: audit the Phase 5A lead ranking without changing it.

    This layer measures evidence completeness, signal dependence, score
    sensitivity, overlap/concentration, and top-K stability. It does not
    promote, demote, or mutate the existing lead systems.
    """

    TOP_K = 150

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
            disk = load_artifact(version, "phase5b")
            if disk is not None:
                with self._lock:
                    self._cache[version] = disk
                return disk
        result = self._run(state)
        save_artifact(version, "phase5b", result)
        with self._lock:
            self._cache[version] = result
        return result

    def _run(self, state: Any) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        fusion = lead_fusion_v2.get(force=False)
        candidates = list(fusion.get("candidates", []))
        all_rows = list(fusion.get("allEligibleCandidates", []))
        if not candidates:
            return {"datasetVersion": state.dataset_version, "candidates": [], "summary": {}}

        top_ids = {str(x["entityId"]) for x in candidates}
        existing_ids = {str(x.get("entityId")) for x in state.leads}

        # Audit source completeness and avoid treating graph-propagated risk as
        # fully independent from anomaly: propagation is seeded by anomaly.
        audits: list[dict[str, Any]] = []
        for row in candidates:
            anomaly = self._b(row.get("anomalyScore"))
            propagated = self._b(row.get("propagatedRisk"))
            pattern = self._b(row.get("patternEvidenceScore"))
            graph = self._b(row.get("graphContextScore"))
            network = self._b(row.get("networkDiversityScore"))
            signals = list(row.get("signals") or [])
            evidence = list(row.get("evidence") or [])
            pattern_types = list(row.get("patternTypes") or [])

            evidence_kinds = sorted({str(x.get("kind", "")) for x in evidence if x.get("kind")})
            completeness = self._evidence_completeness(row)

            # Effective groups: anomaly/propagation are related, while pattern,
            # graph community, and network observations are separate evidence
            # dimensions. This avoids double-counting propagation as independent.
            independent_groups = 0
            if anomaly >= 0.45 or propagated >= 0.50:
                independent_groups += 1
            if pattern > 0:
                independent_groups += 1
            if graph > 0:
                independent_groups += 1
            if network > 0.20:
                independent_groups += 1

            overlap = self._pattern_overlap(row, candidates)
            reason = []
            if anomaly >= 0.45 and propagated >= 0.50:
                reason.append("anomaly-seeded graph propagation")
            if len(pattern_types) >= 2:
                reason.append("multiple pattern types")
            if network > 0.70:
                reason.append("high network diversity")
            if overlap > 0.75:
                reason.append("high pattern concentration")
            if not reason:
                reason.append("single dominant evidence path")

            audits.append({
                "entityId": row["entityId"],
                "leadId": row["leadId"],
                "originalRank": int(row.get("rank", 0)),
                "fusionScore": float(row.get("fusionScore", 0)),
                "existingLead": bool(row.get("existingLead", False)),
                "evidenceCompleteness": round(completeness, 4),
                "evidenceKinds": evidence_kinds,
                "independentSignalGroups": independent_groups,
                "rawSignalCount": int(row.get("signalCount", 0)),
                "patternCount": int(row.get("patternCount", 0)),
                "patternTypeCount": len(pattern_types),
                "patternTypes": pattern_types,
                "patternConcentration": round(overlap, 4),
                "anomalyScore": anomaly,
                "propagatedRisk": propagated,
                "patternEvidenceScore": pattern,
                "graphContextScore": graph,
                "networkDiversityScore": network,
                "reviewClassification": self._classification(completeness, independent_groups, overlap),
                "auditReason": "; ".join(reason),
            })

        # Correlation matrix across all eligible rows gives a dataset-level
        # dependence check for the numeric source dimensions.
        matrix = np.array([
            [self._b(x.get("anomalyScore")), self._b(x.get("propagatedRisk")),
             self._b(x.get("patternEvidenceScore")), self._b(x.get("graphContextScore")),
             self._b(x.get("networkDiversityScore"))]
            for x in all_rows
        ], dtype=float)
        corr = self._correlations(matrix)

        # Small weight perturbations test ranking stability rather than claiming
        # statistical calibration. Three deterministic scenarios are used.
        stability = self._sensitivity_analysis(all_rows, candidates)

        overlap_existing = sum(x["existingLead"] for x in audits)
        new_candidates = len(audits) - overlap_existing
        complete = sum(x["evidenceCompleteness"] >= 0.75 for x in audits)
        strong_independent = sum(x["independentSignalGroups"] >= 3 for x in audits)
        high_concentration = sum(x["patternConcentration"] > 0.75 for x in audits)

        # Pattern concentration by type, useful for spotting a queue dominated
        # by one detector even when the individual rows are valid.
        pattern_coverage: dict[str, int] = {}
        for row in audits:
            for p in row["patternTypes"]:
                pattern_coverage[p] = pattern_coverage.get(p, 0) + 1

        review_queue = [
            x for x in audits
            if x["reviewClassification"] in {"review", "high_concentration"}
        ]
        review_queue.sort(key=lambda x: (-x["fusionScore"], x["entityId"]))

        duration_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 2)
        return {
            "datasetVersion": state.dataset_version,
            "method": "Phase 5B lead validation and ranking audit",
            "destructive": False,
            "semantics": "Audit metrics identify evidence completeness, dependence and ranking sensitivity; they are not accuracy labels or probabilities.",
            "source": {
                "phase5ACandidates": len(candidates),
                "phase5AEligibleCandidates": len(all_rows),
                "existingLeads": len(state.leads),
            },
            "summary": {
                "auditedCandidates": len(audits),
                "evidenceCompleteCandidates": complete,
                "evidenceCompletenessRate": round(complete / max(len(audits), 1), 4),
                "strongIndependentSignalCandidates": strong_independent,
                "strongIndependentSignalRate": round(strong_independent / max(len(audits), 1), 4),
                "highPatternConcentrationCandidates": high_concentration,
                "existingLeadOverlap": overlap_existing,
                "newCandidatesOutsideExisting150": new_candidates,
                "reviewQueue": len(review_queue),
                "meanEvidenceCompleteness": round(float(np.mean([x["evidenceCompleteness"] for x in audits])), 4),
                "meanIndependentSignalGroups": round(float(np.mean([x["independentSignalGroups"] for x in audits])), 3),
                "meanPatternConcentration": round(float(np.mean([x["patternConcentration"] for x in audits])), 4),
                "patternTypeCoverage": pattern_coverage,
            },
            "dependence": corr,
            "rankingStability": stability,
            "candidates": audits,
            "reviewQueue": review_queue[:50],
            "deterministic": True,
            "durationMs": duration_ms,
        }

    @staticmethod
    def _b(v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v or 0.0)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _evidence_completeness(row: dict[str, Any]) -> float:
        checks = [
            bool(row.get("entityId")),
            bool(row.get("signals")),
            bool(row.get("evidence")),
            bool(row.get("patternIds")) or bool(row.get("patternTypes")),
            bool(row.get("clusterId")) or row.get("graphContextScore", 0) == 0,
            int(row.get("transactionCount", 0) or 0) > 0,
        ]
        return sum(checks) / len(checks)

    @staticmethod
    def _pattern_overlap(row: dict[str, Any], candidates: list[dict[str, Any]]) -> float:
        ids = set(row.get("patternIds") or [])
        types = set(row.get("patternTypes") or [])
        if not ids and not types:
            return 0.0
        overlaps = []
        for other in candidates:
            if other.get("entityId") == row.get("entityId"):
                continue
            other_ids = set(other.get("patternIds") or [])
            other_types = set(other.get("patternTypes") or [])
            if ids and other_ids:
                union = ids | other_ids
                overlaps.append(len(ids & other_ids) / max(len(union), 1))
            elif types and other_types:
                union = types | other_types
                overlaps.append(len(types & other_types) / max(len(union), 1))
        return max(overlaps, default=0.0)

    @staticmethod
    def _classification(completeness: float, independent_groups: int, concentration: float) -> str:
        if concentration > 0.75:
            return "high_concentration"
        if completeness < 0.75 or independent_groups < 2:
            return "review"
        return "validated"

    @staticmethod
    def _correlations(matrix: np.ndarray) -> dict[str, Any]:
        names = ["anomaly", "propagatedRisk", "patternEvidence", "graphContext", "networkDiversity"]
        if len(matrix) < 2:
            return {"features": names, "matrix": [], "maxAbsoluteOffDiagonal": 0.0}
        c = np.corrcoef(matrix, rowvar=False)
        c = np.nan_to_num(c, nan=0.0).clip(-1.0, 1.0)
        max_off = 0.0
        pairs = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                value = float(c[i, j])
                max_off = max(max_off, abs(value))
                pairs.append({"a": names[i], "b": names[j], "correlation": round(value, 4)})
        return {"features": names, "matrix": [[round(float(v), 4) for v in row] for row in c], "pairs": pairs, "maxAbsoluteOffDiagonal": round(max_off, 4)}

    @classmethod
    def _score(cls, row: dict[str, Any], weights: tuple[float, float, float, float]) -> float:
        a, p, b, g = weights
        return 100.0 * (a * cls._b(row.get("anomalyScore")) + p * cls._b(row.get("propagatedRisk")) + b * cls._b(row.get("patternEvidenceScore")) + g * cls._b(row.get("graphContextScore")))

    @classmethod
    def _sensitivity_analysis(cls, all_rows: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> dict[str, Any]:
        base = (0.25, 0.30, 0.35, 0.10)
        scenarios = {
            "pattern_plus": (0.22, 0.28, 0.40, 0.10),
            "graph_plus": (0.24, 0.30, 0.31, 0.15),
            "anomaly_plus": (0.30, 0.30, 0.30, 0.10),
        }
        base_order = [x["entityId"] for x in sorted(all_rows, key=lambda r: (-cls._score(r, base), r["entityId"]))[:cls.TOP_K]]
        results = []
        for name, weights in scenarios.items():
            order = [x["entityId"] for x in sorted(all_rows, key=lambda r: (-cls._score(r, weights), r["entityId"]))[:cls.TOP_K]]
            aset, bset = set(base_order), set(order)
            intersection = len(aset & bset)
            results.append({
                "scenario": name,
                "weights": dict(zip(["anomaly", "propagatedRisk", "patternEvidence", "graphContext"], weights)),
                "topKOverlap": intersection,
                "topKStability": round(intersection / cls.TOP_K, 4),
                "rankCorrelation": round(cls._spearman_overlap(base_order, order), 4),
            })
        return {
            "baselineWeights": dict(zip(["anomaly", "propagatedRisk", "patternEvidence", "graphContext"], base)),
            "scenarios": results,
            "meanTopKStability": round(float(np.mean([x["topKStability"] for x in results])), 4),
        }

    @staticmethod
    def _spearman_overlap(base: list[str], other: list[str]) -> float:
        common = [x for x in base if x in set(other)]
        if len(common) < 2:
            return 0.0
        br = {x: i for i, x in enumerate(base)}
        orank = {x: i for i, x in enumerate(other)}
        a = np.array([br[x] for x in common], dtype=float)
        b = np.array([orank[x] for x in common], dtype=float)
        if np.std(a) == 0 or np.std(b) == 0:
            return 1.0
        return float(np.corrcoef(a, b)[0, 1])


lead_validation_v2 = LeadValidationV2()
