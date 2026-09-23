from __future__ import annotations

from datetime import datetime
import threading
from typing import Any

from app.services.pattern_validation_v2 import pattern_validation_v2
from app.services.artifacts import load_artifact, save_artifact


class PatternRefinementV2:
    """Phase 4C refinement layer over Phase 4A + 4B.

    Non-destructive: existing 100-pattern production output, Phase 4A detector,
    and Phase 4B validation remain unchanged. Phase 4C only ranks, groups,
    and classifies the experimental patterns.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, force: bool = False) -> dict[str, Any]:
        validation = pattern_validation_v2.get(force=force)
        version = validation["datasetVersion"]
        with self._lock:
            if not force and version in self._cache:
                return self._cache[version]
        if not force:
            disk = load_artifact(version, "phase4c")
            if disk is not None:
                with self._lock:
                    self._cache[version] = disk
                return disk
        result = self._run(validation)
        save_artifact(version, "phase4c", result)
        with self._lock:
            self._cache[version] = result
        return result

    def _run(self, validation: dict[str, Any]) -> dict[str, Any]:
        started = datetime.utcnow()
        rows = [dict(x) for x in validation["validations"]]

        # Only fully valid patterns are eligible for promotion. Patterns that
        # fail validation remain visible as quarantine/review records.
        eligible = [x for x in rows if x["valid"]]
        quarantined = [x for x in rows if not x["valid"]]

        # Group near-duplicate patterns only within the same detector type.
        # Cross-type overlap is retained because multiple independent signals
        # can legitimately describe the same investigative event.
        overlap_groups = self._build_overlap_groups(eligible)
        group_members: dict[str, list[str]] = {}
        for pid, gid in overlap_groups.items():
            group_members.setdefault(gid, []).append(pid)

        by_id = {x["patternId"]: x for x in eligible}
        representatives: set[str] = set()
        for gid, pids in group_members.items():
            winner = sorted(
                pids,
                key=lambda pid: (
                    -self._priority(by_id[pid]),
                    -by_id[pid]["evidenceSupportScore"],
                    pid,
                ),
            )[0]
            representatives.add(winner)

        refined: list[dict[str, Any]] = []
        for row in rows:
            pid = row["patternId"]
            gid = overlap_groups.get(pid)
            priority = self._priority(row)
            if not row["valid"]:
                status = "quarantine"
                reason = "Pattern did not satisfy all Phase 4B validation requirements."
            elif pid in representatives:
                status = "promoted_candidate"
                reason = "Validated pattern selected as the representative of its detector-specific overlap group."
            else:
                status = "duplicate_candidate"
                reason = "Validated pattern overlaps a stronger pattern of the same detector type; retained as supporting evidence."

            refined.append({
                "patternId": pid,
                "patternType": row["patternType"],
                "confidenceScore": row["confidenceScore"],
                "evidenceSupportScore": row["evidenceSupportScore"],
                "confidenceEvidenceGap": row["confidenceSupportGap"],
                "priorityScore": priority,
                "validationStatus": status,
                "overlapGroup": gid,
                "isRepresentative": pid in representatives,
                "reviewRequired": status != "promoted_candidate",
                "supportingWalletCount": row["walletReferenceCount"],
                "supportingTransactionCount": row["transactionReferenceCount"],
                "supportingIpEvidence": row["crossLayerEvidence"],
                "temporalConsistent": row["temporalConsistent"],
                "validationNotes": row["validationNotes"],
                "walletIds": row["walletIds"],
                "transactionIds": row["transactionIds"],
            })

        refined.sort(key=lambda x: (-x["priorityScore"], x["patternId"]))
        for rank, row in enumerate(refined, 1):
            row["rank"] = rank

        promoted = [x for x in refined if x["validationStatus"] == "promoted_candidate"]
        duplicates = [x for x in refined if x["validationStatus"] == "duplicate_candidate"]
        quarantine = [x for x in refined if x["validationStatus"] == "quarantine"]

        by_type: dict[str, dict[str, Any]] = {}
        for kind in sorted({x["patternType"] for x in refined}):
            subset = [x for x in refined if x["patternType"] == kind]
            by_type[kind] = {
                "count": len(subset),
                "promotedCandidates": sum(x["validationStatus"] == "promoted_candidate" for x in subset),
                "duplicateCandidates": sum(x["validationStatus"] == "duplicate_candidate" for x in subset),
                "quarantined": sum(x["validationStatus"] == "quarantine" for x in subset),
                "meanPriorityScore": round(sum(x["priorityScore"] for x in subset) / max(len(subset), 1), 2),
            }

        duration_ms = round((datetime.utcnow() - started).total_seconds() * 1000, 2)
        return {
            "datasetVersion": validation["datasetVersion"],
            "method": "Phase 4C validated pattern refinement, overlap grouping, and investigative prioritization",
            "destructive": False,
            "sourcePatternCount": len(rows),
            "eligiblePatternCount": len(eligible),
            "summary": {
                "promotedCandidates": len(promoted),
                "duplicateCandidates": len(duplicates),
                "quarantined": len(quarantine),
                "overlapGroups": len(group_members),
                "promotionRate": round(len(promoted) / max(len(rows), 1), 4),
                "quarantineRate": round(len(quarantine) / max(len(rows), 1), 4),
                "meanPriorityScore": round(sum(x["priorityScore"] for x in refined) / max(len(refined), 1), 2),
            },
            "byType": by_type,
            "reviewQueue": sorted(
                [x for x in refined if x["reviewRequired"]],
                key=lambda x: (-x["priorityScore"], x["patternId"]),
            )[:50],
            "patterns": refined,
            "durationMs": duration_ms,
        }

    @staticmethod
    def _priority(row: dict[str, Any]) -> float:
        confidence = max(0.0, min(1.0, float(row["confidenceScore"])))
        evidence = max(0.0, min(1.0, float(row["evidenceSupportScore"])))
        temporal = 1.0 if row["temporalConsistent"] else 0.0
        cross_layer = 1.0 if row["crossLayerEvidence"] else 0.0

        # Evidence and confidence dominate; temporal/cross-layer are
        # supporting dimensions rather than independent claims of risk.
        return round(
            min(100.0, 55.0 * confidence + 30.0 * evidence + 10.0 * temporal + 5.0 * cross_layer),
            2,
        )

    @staticmethod
    def _similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
        aw = set(a["walletIds"])
        bw = set(b["walletIds"])
        at = set(a["transactionIds"])
        bt = set(b["transactionIds"])
        wu = len(aw | bw)
        tu = len(at | bt)
        wallet_j = len(aw & bw) / wu if wu else 0.0
        tx_j = len(at & bt) / tu if tu else 0.0
        return 0.55 * wallet_j + 0.45 * tx_j

    def _build_overlap_groups(self, rows: list[dict[str, Any]]) -> dict[str, str]:
        # Connected components over same-type high-overlap patterns.
        adjacency: dict[str, set[str]] = {x["patternId"]: set() for x in rows}
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a["patternType"] != b["patternType"]:
                    continue
                if self._similarity(a, b) >= 0.75:
                    adjacency[a["patternId"]].add(b["patternId"])
                    adjacency[b["patternId"]].add(a["patternId"])

        groups: dict[str, str] = {}
        seen: set[str] = set()
        for pid in sorted(adjacency):
            if pid in seen:
                continue
            stack = [pid]
            component = []
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                component.append(cur)
                stack.extend(sorted(adjacency[cur] - seen, reverse=True))
            component.sort()
            gid = f"OV4C-{component[0]}"
            for member in component:
                groups[member] = gid
        return groups


pattern_refinement_v2 = PatternRefinementV2()
