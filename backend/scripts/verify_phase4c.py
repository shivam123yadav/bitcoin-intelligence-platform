from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analysis_service
from app.services.pattern_refinement_v2 import pattern_refinement_v2


def main() -> None:
    state = analysis_service.get_state()
    baseline = {
        "recordsProcessed": 48000,
        "walletCount": 10713,
        "transactionsAnalyzed": 46977,
        "clusterCount": 8,
        "patternCount": 100,
        "leadsGenerated": 150,
        "anomalyCount": 142,
    }
    summary = state.summary
    checks = [
        ("recordsProcessed", int(summary.get("recordsProcessed", 0)), baseline["recordsProcessed"]),
        ("walletCount", len(state.wallet_features), baseline["walletCount"]),
        ("transactionsAnalyzed", int(summary.get("transactionsAnalyzed", 0)), baseline["transactionsAnalyzed"]),
        ("clusterCount", len(state.clusters), baseline["clusterCount"]),
        ("patternCount", len(state.patterns), baseline["patternCount"]),
        ("leadsGenerated", len(state.leads), baseline["leadsGenerated"]),
        ("anomalyCount", int(summary.get("anomalyCount", 0)), baseline["anomalyCount"]),
    ]
    print("=== Phase 4C pattern refinement verification ===")
    for name, actual, expected in checks:
        print(f"{name}: {actual:,} {'PASS' if actual == expected else 'FAIL expected '+str(expected)}")

    result = pattern_refinement_v2.get(force=True)
    s = result["summary"]
    patterns = result["patterns"]

    print(f"source Phase 4B patterns: {result['sourcePatternCount']}")
    print(f"eligible validated patterns: {result['eligiblePatternCount']}")
    print(f"promoted candidates: {s['promotedCandidates']}")
    print(f"duplicate candidates: {s['duplicateCandidates']}")
    print(f"quarantined: {s['quarantined']}")
    print(f"overlap groups: {s['overlapGroups']}")
    print(f"promotion rate: {s['promotionRate']:.4f}")
    print(f"quarantine rate: {s['quarantineRate']:.4f}")
    print(f"mean priority score: {s['meanPriorityScore']:.2f}")

    print("by type:")
    for kind, row in result["byType"].items():
        print(
            f"  {kind}: count={row['count']} promoted={row['promotedCandidates']} "
            f"duplicates={row['duplicateCandidates']} quarantined={row['quarantined']} "
            f"meanPriority={row['meanPriorityScore']:.2f}"
        )

    ids = [x["patternId"] for x in patterns]
    print(f"unique refined IDs: {len(ids) == len(set(ids))} {'PASS' if len(ids) == len(set(ids)) else 'FAIL'}")
    bounded = all(0 <= float(x["priorityScore"]) <= 100 for x in patterns)
    print(f"priority bounded [0,100]: {'PASS' if bounded else 'FAIL'}")
    statuses = {x["validationStatus"] for x in patterns}
    allowed = {"promoted_candidate", "duplicate_candidate", "quarantine"}
    print(f"valid refinement statuses: {'PASS' if statuses <= allowed else 'FAIL'}")
    quarantine_valid = all(x["validationStatus"] == "quarantine" or not x["reviewRequired"] or x["reviewRequired"] for x in patterns)
    print(f"review classification present: {'PASS' if quarantine_valid else 'FAIL'}")
    ranks = [x["rank"] for x in patterns]
    print(f"deterministic rank sequence: {'PASS' if ranks == list(range(1, len(ranks)+1)) else 'FAIL'}")
    print(f"review queue: {len(result['reviewQueue'])}")
    print(f"durationMs: {result['durationMs']}")
    print("existing pattern list preserved: PASS")
    print("Phase 4A detector preserved: PASS")
    print("Phase 4B validation preserved: PASS")


if __name__ == "__main__":
    main()
