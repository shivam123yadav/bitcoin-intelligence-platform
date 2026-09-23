from __future__ import annotations

from datetime import datetime
import threading
from typing import Any

import pandas as pd
import numpy as np

from app.services.analysis import analysis_service
from app.services.artifacts import load_artifact, save_artifact
from app.services.pattern_detection_v2 import pattern_detection_v2


def _safe_seq(value: Any) -> list[Any]:
    """Normalize list-like parquet values without ambiguous numpy truth tests."""
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


class PatternValidationV2:
    """Phase 4B validation layer for the Phase 4A pattern experiment.

    This service is intentionally non-destructive: it validates the 4A output
    against the frozen observation dataset and never changes the existing
    100-pattern production result or the 4A detector.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, force: bool = False) -> dict[str, Any]:
        version = analysis_service.get_state().dataset_version
        with self._lock:
            if not force and version in self._cache:
                return self._cache[version]
        if not force:
            disk = load_artifact(version, "phase4b")
            if disk is not None:
                with self._lock:
                    self._cache[version] = disk
                return disk
        result = self._run(version)
        save_artifact(version, "phase4b", result)
        with self._lock:
            self._cache[version] = result
        return result

    def _run(self, version: str) -> dict[str, Any]:
        started = datetime.utcnow()
        phase4a = pattern_detection_v2.get(force=force_refresh_needed(False))
        referenced_txids = sorted({
            str(txid)
            for pattern in phase4a.get("patterns", [])
            for txid in pattern.get("transactionIds", [])
            if txid
        })
        tx_map: dict[str, dict[str, Any]] = {}
        wallet_tx: dict[str, set[str]] = {}
        wallet_ip: dict[str, set[str]] = {}

        if referenced_txids:
            import duckdb
            from app.services.paths import NORMALIZED_STORAGE_ROOT
            path = NORMALIZED_STORAGE_ROOT / f"observations_v{version}.duckdb"
            con = duckdb.connect(str(path), read_only=True)
            try:
                placeholders = ",".join("?" for _ in referenced_txids)
                rows = con.execute(
                    f"SELECT timestamp, txid, input_addresses, output_addresses, input_amounts, output_amounts, src_ip, dst_ip FROM observations WHERE txid IN ({placeholders})",
                    referenced_txids,
                ).fetchall()
            finally:
                con.close()
            for timestamp, txid, input_addresses, output_addresses, input_amounts, output_amounts, src_ip, dst_ip in rows:
                inputs = {str(x) for x in _safe_seq(input_addresses) if x}
                outputs = {str(x) for x in _safe_seq(output_addresses) if x}
                wallets = inputs | outputs
                ips = {str(x) for x in (src_ip, dst_ip) if x}
                tx_map[str(txid)] = {
                    "timestamp": pd.to_datetime(timestamp, errors="coerce", utc=True),
                    "inputs": inputs,
                    "outputs": outputs,
                    "wallets": wallets,
                    "ips": ips,
                    "input_amounts": [float(x) for x in _safe_seq(input_amounts)],
                    "output_amounts": [float(x) for x in _safe_seq(output_amounts)],
                }
                for wallet in wallets:
                    wallet_tx.setdefault(wallet, set()).add(str(txid))
                    wallet_ip.setdefault(wallet, set()).update(ips)

        validations: list[dict[str, Any]] = []
        for pattern in phase4a["patterns"]:
            validations.append(self._validate_pattern(pattern, tx_map, wallet_tx, wallet_ip))

        valid_count = sum(v["valid"] for v in validations)
        partially_supported = sum(v["supportLevel"] == "partial" for v in validations)
        invalid_count = len(validations) - valid_count
        evidence_scores = [v["evidenceSupportScore"] for v in validations]
        cross_layer_count = sum(v["crossLayerEvidence"] for v in validations)
        temporal_count = sum(v["temporalConsistent"] for v in validations)

        overlap = self._overlap(validations)
        by_type = self._aggregate_by_type(validations)
        confidence_consistency = self._confidence_consistency(validations)
        review_queue = sorted(
            validations,
            key=lambda x: (-x["reviewPriority"], x["patternId"]),
        )[:50]

        duration_ms = round((datetime.utcnow() - started).total_seconds() * 1000, 2)
        return {
            "datasetVersion": version,
            "method": "Phase 4B Phase 4A pattern validation and temporal evidence analysis",
            "destructive": False,
            "sourcePatternCount": len(phase4a["patterns"]),
            "validatedPatternCount": len(validations),
            "summary": {
                "fullySupported": valid_count,
                "partiallySupported": partially_supported,
                "invalid": invalid_count,
                "fullySupportedRate": round(valid_count / max(len(validations), 1), 4),
                "temporalConsistent": temporal_count,
                "temporalConsistencyRate": round(temporal_count / max(len(validations), 1), 4),
                "crossLayerEvidencePatterns": cross_layer_count,
                "crossLayerEvidenceRate": round(cross_layer_count / max(len(validations), 1), 4),
                "meanEvidenceSupportScore": round(sum(evidence_scores) / max(len(evidence_scores), 1), 4),
                "minEvidenceSupportScore": round(min(evidence_scores or [0.0]), 4),
                "confidenceEvidenceConsistency": confidence_consistency,
            },
            "byType": by_type,
            "overlap": overlap,
            "reviewQueue": review_queue,
            "validations": validations,
            "durationMs": duration_ms,
        }

    def _validate_pattern(
        self,
        pattern: dict[str, Any],
        tx_map: dict[str, dict[str, Any]],
        wallet_tx: dict[str, set[str]],
        wallet_ip: dict[str, set[str]],
    ) -> dict[str, Any]:
        pid = str(pattern.get("id", ""))
        kind = str(pattern.get("pattern_type", ""))
        txids = sorted(set(str(x) for x in pattern.get("transactionIds", []) if x))
        wallets = sorted(set(str(x) for x in pattern.get("entityIds", []) if x))
        existing_txs = [tx_map[x] for x in txids if x in tx_map]
        observed_wallets = set().union(*(x["wallets"] for x in existing_txs)) if existing_txs else set()
        missing_txs = [x for x in txids if x not in tx_map]
        missing_wallets = [x for x in wallets if x not in wallet_tx]

        timestamps = [x["timestamp"] for x in existing_txs if pd.notna(x["timestamp"])]
        first = min(timestamps) if timestamps else None
        last = max(timestamps) if timestamps else None
        first_declared = pd.to_datetime(pattern.get("firstSeen"), errors="coerce", utc=True)
        last_declared = pd.to_datetime(pattern.get("lastSeen"), errors="coerce", utc=True)
        temporal = bool(first is not None and last is not None and first <= last)
        declared_temporal = bool(pd.notna(first_declared) and pd.notna(last_declared) and first_declared <= last_declared)
        if temporal and pd.notna(first_declared) and pd.notna(last_declared):
            temporal = bool(first_declared <= last_declared and first_declared <= last and last_declared >= first)

        all_wallets_observed = bool(wallets) and all(w in observed_wallets for w in wallets)
        all_txs_exist = len(missing_txs) == 0 and bool(txids)
        support_base = 0.0
        support_base += 0.30 if all_txs_exist else 0.0
        support_base += 0.25 if all_wallets_observed else 0.0
        support_base += 0.20 if temporal and declared_temporal else 0.0
        support_base += 0.25 if self._type_specific_valid(kind, pattern, existing_txs) else 0.0

        cross_layer = any(wallet_ip.get(w) for w in wallets) and bool(existing_txs)
        if cross_layer:
            support_base += 0.05
        support_score = round(min(1.0, support_base), 3)

        support_level = "full" if support_score >= 0.90 else "partial" if support_score >= 0.60 else "weak"
        valid = bool(all_txs_exist and all_wallets_observed and temporal and declared_temporal and support_score >= 0.75)

        confidence = float(pattern.get("confidenceScore", 0.0) or 0.0)
        consistency_gap = round(abs(confidence - support_score), 3)
        review_priority = round(
            min(100.0, 45 * confidence + 40 * support_score + 15 * (1 if cross_layer else 0)), 2
        )
        reasons = []
        if missing_txs:
            reasons.append("missing transaction references")
        if missing_wallets:
            reasons.append("missing wallet references")
        if not temporal or not declared_temporal:
            reasons.append("temporal inconsistency")
        if not self._type_specific_valid(kind, pattern, existing_txs):
            reasons.append("type-specific evidence does not fully satisfy detector condition")
        if cross_layer:
            reasons.append("network-layer IP evidence available for referenced wallet(s)")
        if not reasons:
            reasons.append("all core evidence checks passed")

        return {
            "patternId": pid,
            "patternType": kind,
            "confidenceScore": round(confidence, 3),
            "evidenceSupportScore": support_score,
            "confidenceSupportGap": consistency_gap,
            "supportLevel": support_level,
            "valid": valid,
            "temporalConsistent": temporal and declared_temporal,
            "crossLayerEvidence": cross_layer,
            "transactionReferenceCount": len(txids),
            "transactionReferencesResolved": len(existing_txs),
            "walletReferenceCount": len(wallets),
            "walletReferencesResolved": sum(1 for w in wallets if w in observed_wallets),
            "missingTransactionIds": missing_txs,
            "missingWalletIds": missing_wallets,
            "observedFirstSeen": first.isoformat() if first is not None else None,
            "observedLastSeen": last.isoformat() if last is not None else None,
            "declaredFirstSeen": pattern.get("firstSeen"),
            "declaredLastSeen": pattern.get("lastSeen"),
            "reviewPriority": review_priority,
            "walletIds": wallets,
            "transactionIds": txids,
            "validationNotes": reasons,
        }

    @staticmethod
    def _type_specific_valid(kind: str, pattern: dict[str, Any], txs: list[dict[str, Any]]) -> bool:
        if not txs:
            return False
        evidence = pattern.get("evidence") or []
        if kind == "high_velocity":
            ev = next((x for x in evidence if x.get("type") == "velocity_window"), {})
            return int(ev.get("count", 0) or 0) >= 8
        if kind == "rapid_multi_hop":
            ev = next((x for x in evidence if x.get("type") == "hop_sequence"), {})
            times = [x["timestamp"] for x in txs if pd.notna(x["timestamp"])]
            return int(ev.get("hopCount", 0) or 0) >= 3 and len(times) >= 3 and all(a <= b for a, b in zip(times, times[1:]))
        if kind == "peeling_chain":
            ev = next((x for x in evidence if x.get("type") == "amount_decline"), {})
            start = float(ev.get("start", 0) or 0)
            end = float(ev.get("end", 0) or 0)
            decline = float(ev.get("decline", 0) or 0)
            return start > 0 and end >= 0 and end <= start and decline >= 0.05
        if kind == "mixing_like":
            ev = next((x for x in evidence if x.get("type") == "fan_in_out"), {})
            return int(ev.get("inputs", 0) or 0) >= 3 and int(ev.get("outputs", 0) or 0) >= 3
        if kind == "dense_wallet_interaction":
            ev = next((x for x in evidence if x.get("type") == "repeated_wallet_pair"), {})
            return int(ev.get("transactionCount", 0) or 0) >= 3 and ev.get("walletA") and ev.get("walletB")
        return False

    @staticmethod
    def _aggregate_by_type(validations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for kind in sorted({x["patternType"] for x in validations}):
            rows = [x for x in validations if x["patternType"] == kind]
            out[kind] = {
                "count": len(rows),
                "fullySupported": sum(x["valid"] for x in rows),
                "partialOrWeak": sum(not x["valid"] for x in rows),
                "meanEvidenceSupportScore": round(sum(x["evidenceSupportScore"] for x in rows) / max(len(rows), 1), 4),
                "temporalConsistencyRate": round(sum(x["temporalConsistent"] for x in rows) / max(len(rows), 1), 4),
                "crossLayerEvidenceRate": round(sum(x["crossLayerEvidence"] for x in rows) / max(len(rows), 1), 4),
            }
        return out

    @staticmethod
    def _confidence_consistency(validations: list[dict[str, Any]]) -> dict[str, Any]:
        if not validations:
            return {"meanAbsoluteGap": 0.0, "within0_10": 0, "within0_20": 0}
        gaps = [x["confidenceSupportGap"] for x in validations]
        return {
            "note": "Evidence-consistency diagnostic; true statistical calibration requires labeled ground truth, which this synthetic dataset does not provide.",
            "meanAbsoluteGap": round(sum(gaps) / len(gaps), 4),
            "within0_10": sum(g <= 0.10 for g in gaps),
            "within0_20": sum(g <= 0.20 for g in gaps),
        }

    @staticmethod
    def _overlap(validations: list[dict[str, Any]]) -> dict[str, Any]:
        pairs = []
        for i, a in enumerate(validations):
            aw = set(a.get("walletIds", []))
            at = set(a.get("transactionIds", []))
            for b in validations[i + 1:]:
                bw = set(b.get("walletIds", []))
                bt = set(b.get("transactionIds", []))
                w_union = aw | bw
                t_union = at | bt
                w_j = len(aw & bw) / len(w_union) if w_union else 0.0
                t_j = len(at & bt) / len(t_union) if t_union else 0.0
                if w_j == 0 and t_j == 0:
                    continue
                pairs.append({
                    "patternA": a["patternId"],
                    "patternB": b["patternId"],
                    "typeA": a["patternType"],
                    "typeB": b["patternType"],
                    "walletJaccard": round(w_j, 4),
                    "transactionJaccard": round(t_j, 4),
                })
        pairs.sort(key=lambda x: (-max(x["walletJaccard"], x["transactionJaccard"]), x["patternA"], x["patternB"]))
        cross_type = sum(1 for x in pairs if x["typeA"] != x["typeB"])
        mean_w = sum(x["walletJaccard"] for x in pairs) / len(pairs) if pairs else 0.0
        mean_t = sum(x["transactionJaccard"] for x in pairs) / len(pairs) if pairs else 0.0
        return {
            "overlappingPatternPairs": len(pairs),
            "crossTypeOverlappingPairs": cross_type,
            "meanWalletJaccard": round(mean_w, 4),
            "meanTransactionJaccard": round(mean_t, 4),
            "topOverlaps": pairs[:25],
            "note": "Overlap is descriptive only; repeated flags may represent corroborating signals rather than duplicate findings."
        }



def force_refresh_needed(_value: bool) -> bool:
    # Phase 4B owns its cache; 4A is deterministic and can safely be read from cache.
    return False


pattern_validation_v2 = PatternValidationV2()
