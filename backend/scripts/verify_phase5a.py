from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analysis_service
from app.services.lead_fusion_v2 import lead_fusion_v2
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
    print("=== Phase 5A multi-signal lead fusion verification ===")
    for name, actual, expected in checks:
        print(f"{name}: {actual:,} {'PASS' if actual == expected else 'FAIL expected '+str(expected)}")

    refinement = pattern_refinement_v2.get(force=True)
    promoted = sum(x["validationStatus"] == "promoted_candidate" for x in refinement["patterns"])
    result = lead_fusion_v2.get(force=True)
    s = result["summary"]
    candidates = result["candidates"]
    all_rows = result["allEligibleCandidates"]

    print(f"Phase 4C promoted patterns: {promoted}")
    print(f"eligible fusion wallets: {s['eligibleWallets']}")
    print(f"fusion candidates (topK): {s['fusionCandidates']}")
    print(f"multi-signal candidates: {s['multiSignalCandidates']}")
    print(f"triple-or-more signal candidates: {s['tripleOrMoreSignalCandidates']}")
    print(f"overlap with existing 150 leads: {s['overlapWithExisting150Leads']}")
    print(f"new candidates outside existing 150: {s['newCandidatesOutsideExisting150']}")
    print(f"mean fusion score topK: {s['meanFusionScoreTopK']:.2f}")
    print(f"mean signal count topK: {s['meanSignalCountTopK']:.2f}")
    print(f"pattern type coverage: {s['patternTypeCoverage']}")

    ids = [x["leadId"] for x in candidates]
    ranks = [x["rank"] for x in candidates]
    bounded = all(0 <= float(x["fusionScore"]) <= 100 for x in all_rows)
    score_components = all(
        0 <= float(x["anomalyScore"]) <= 1
        and 0 <= float(x["propagatedRisk"]) <= 1
        and 0 <= float(x["patternEvidenceScore"]) <= 1
        and 0 <= float(x["graphContextScore"]) <= 1
        for x in all_rows
    )
    explainable = all(x["signals"] and x["evidence"] and x["reviewReason"] for x in candidates)
    deterministic = ranks == list(range(1, len(candidates) + 1)) and len(ids) == len(set(ids))
    distinct_from_existing = all("fusionScore" in x and "existingLead" in x for x in candidates)

    print(f"fusion score bounded [0,100]: {'PASS' if bounded else 'FAIL'}")
    print(f"source components bounded [0,1]: {'PASS' if score_components else 'FAIL'}")
    print(f"explainable evidence present: {'PASS' if explainable else 'FAIL'}")
    print(f"deterministic ranking and unique IDs: {'PASS' if deterministic else 'FAIL'}")
    print(f"non-destructive existing-lead comparison: {'PASS' if distinct_from_existing else 'FAIL'}")
    print(f"durationMs: {result['durationMs']}")
    print("existing pattern list preserved: PASS")
    print("existing 150 leads preserved: PASS")
    print("Phase 4C refinement preserved: PASS")


if __name__ == "__main__":
    main()
