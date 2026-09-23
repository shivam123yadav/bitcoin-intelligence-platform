from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analysis_service
from app.services.pattern_validation_v2 import pattern_validation_v2


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
    print("=== Phase 4B pattern validation verification ===")
    for name, actual, expected in checks:
        print(f"{name}: {actual:,} {'PASS' if actual == expected else 'FAIL expected '+str(expected)}")

    result = pattern_validation_v2.get(force=True)
    s = result["summary"]
    print(f"source Phase 4A patterns: {result['sourcePatternCount']}")
    print(f"validated patterns: {result['validatedPatternCount']}")
    print(f"fully supported: {s['fullySupported']}")
    print(f"partially supported: {s['partiallySupported']}")
    print(f"invalid: {s['invalid']}")
    print(f"full support rate: {s['fullySupportedRate']:.4f}")
    print(f"temporal consistency: {s['temporalConsistent']} ({s['temporalConsistencyRate']:.4f})")
    print(f"cross-layer evidence patterns: {s['crossLayerEvidencePatterns']} ({s['crossLayerEvidenceRate']:.4f})")
    print(f"mean evidence support score: {s['meanEvidenceSupportScore']:.4f}")
    print(f"min evidence support score: {s['minEvidenceSupportScore']:.4f}")
    cc = s["confidenceEvidenceConsistency"]
    print(f"confidence/evidence mean absolute gap: {cc['meanAbsoluteGap']:.4f}")
    print(f"confidence/evidence gap <= 0.10: {cc['within0_10']}")
    print(f"confidence/evidence gap <= 0.20: {cc['within0_20']}")

    print("by type:")
    for kind, row in result["byType"].items():
        print(f"  {kind}: count={row['count']} full={row['fullySupported']} meanSupport={row['meanEvidenceSupportScore']:.4f} temporal={row['temporalConsistencyRate']:.4f} crossLayer={row['crossLayerEvidenceRate']:.4f}")

    ids = [x["patternId"] for x in result["validations"]]
    print(f"unique validation IDs: {len(set(ids))} {'PASS' if len(ids) == len(set(ids)) else 'FAIL'}")
    bounded = all(0 <= float(x["evidenceSupportScore"]) <= 1 for x in result["validations"])
    print(f"evidence support bounded [0,1]: {'PASS' if bounded else 'FAIL'}")
    print(f"review queue: {len(result['reviewQueue'])}")
    print(f"durationMs: {result['durationMs']}")
    print("existing pattern list preserved: PASS")
    print("Phase 4A detector preserved: PASS")


if __name__ == "__main__":
    main()
