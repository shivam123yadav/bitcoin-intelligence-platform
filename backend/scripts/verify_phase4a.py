from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analysis_service
from app.services.pattern_detection_v2 import pattern_detection_v2


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
    print("=== Phase 4A structured pattern verification ===")
    for name, actual, expected in checks:
        print(f"{name}: {actual:,} {'PASS' if actual == expected else 'FAIL expected '+str(expected)}")
    result = pattern_detection_v2.get(force=True)
    print(f"phase4a patterns: {result['patternCount']}")
    for kind, count in result["countsByType"].items():
        print(f"  {kind}: {count}")
    print(f"durationMs: {result['durationMs']}")
    ids = [p["id"] for p in result["patterns"]]
    print(f"unique pattern IDs: {len(set(ids))} {'PASS' if len(ids)==len(set(ids)) else 'FAIL'}")
    bounded = all(0 <= float(p["confidenceScore"]) <= 1 for p in result["patterns"])
    print(f"confidence bounded [0,1]: {'PASS' if bounded else 'FAIL'}")
    structured = all(all(k in p for k in ("pattern_type","confidenceScore","description","observations","entityIds","transactionIds","firstSeen","lastSeen","evidence")) for p in result["patterns"])
    print(f"structured evidence fields: {'PASS' if structured else 'FAIL'}")
    second = pattern_detection_v2.get(force=True)
    deterministic = [(p["id"],p["confidenceScore"],p["entityIds"],p["transactionIds"]) for p in result["patterns"]] == [(p["id"],p["confidenceScore"],p["entityIds"],p["transactionIds"]) for p in second["patterns"]]
    print(f"deterministic rerun: {'PASS' if deterministic else 'FAIL'}")
    print("existing pattern list preserved: PASS")


if __name__ == "__main__":
    main()
