from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analysis_service
from app.services.lead_fusion_v2 import lead_fusion_v2
from app.services.lead_validation_v2 import lead_validation_v2
from app.services.lead_explainability_v2 import lead_explainability_v2

def main():
    state = analysis_service.get_state()
    baseline = {
        "recordsProcessed": 48000, "walletCount": 10713,
        "transactionsAnalyzed": 46977, "clusterCount": 8,
        "patternCount": 100, "leadsGenerated": 150, "anomalyCount": 142,
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
    print("=== Phase 5C final investigative lead ranking and explainability verification ===")
    for name, actual, expected in checks:
        print(f"{name}: {actual:,} {'PASS' if actual == expected else 'FAIL expected '+str(expected)}")

    fusion = lead_fusion_v2.get(force=True)
    validation = lead_validation_v2.get(force=True)
    result = lead_explainability_v2.get(force=True)
    leads = result["leads"]
    s = result["summary"]

    print(f"Phase 5A candidates: {len(fusion['candidates'])}")
    print(f"Phase 5B audited candidates: {len(validation['candidates'])}")
    print(f"Phase 5C final leads: {len(leads)}")
    print(f"mean final priority score: {s['meanFinalPriorityScore']:.2f}")
    print(f"mean evidence completeness: {s['meanEvidenceCompleteness']:.4f}")
    print(f"mean effective signal groups: {s['meanIndependentSignalGroups']:.3f}")
    print(f"mean top-K stability: {s['meanTopKStability']:.4f}")
    print(f"existing-lead overlap: {s['existingLeadOverlap']}")
    print(f"new candidates outside existing 150: {s['newCandidatesOutsideExisting150']}")
    print(f"review queue: {s['reviewQueue']}")
    print(f"dependence max absolute off-diagonal: {result['dependenceAudit'].get('maxAbsoluteOffDiagonal',0):.4f}")

    ids=[x["entityId"] for x in leads]
    ranks=[x["rank"] for x in leads]
    unique_ids=len(ids)==len(set(ids)) and len(ids)==150
    rank_valid=ranks==list(range(1,len(leads)+1))
    score_bounded=all(0<=x["finalPriorityScore"]<=100 for x in leads)
    provenance=all(x["evidenceProvenance"] for x in leads)
    patterns=all("validatedPatterns" in x for x in leads)
    supporting=all("supportingEntities" in x and "supportingTransactions" in x for x in leads)
    network=all("networkObservations" in x for x in leads)
    graph=all("graphContext" in x for x in leads)
    temporal=all("temporalRange" in x for x in leads)
    warnings=all("warnings" in x for x in leads)
    explanations=all(isinstance(x["explanation"],str) and x["explanation"] for x in leads)
    review=all(x["reviewClassification"] in {"validated","review","high_concentration"} for x in leads)
    confidence=all(x["analyticalConfidenceIndicator"]["label"] in {"high","moderate","limited"} for x in leads)
    non_destructive=len(state.leads)==150 and len(state.patterns)==100
    # Run twice from cache-independent force path and compare deterministic core fields.
    second=lead_explainability_v2.get(force=True)
    det=[(x["entityId"],x["finalPriorityScore"],x["rank"]) for x in leads] == [(x["entityId"],x["finalPriorityScore"],x["rank"]) for x in second["leads"]]

    print(f"unique final leads: {'PASS' if unique_ids else 'FAIL'}")
    print(f"rank sequence: {'PASS' if rank_valid else 'FAIL'}")
    print(f"priority bounded [0,100]: {'PASS' if score_bounded else 'FAIL'}")
    print(f"evidence provenance present: {'PASS' if provenance else 'FAIL'}")
    print(f"validated patterns present: {'PASS' if patterns else 'FAIL'}")
    print(f"supporting wallets/transactions: {'PASS' if supporting else 'FAIL'}")
    print(f"network observations present: {'PASS' if network else 'FAIL'}")
    print(f"graph context present: {'PASS' if graph else 'FAIL'}")
    print(f"temporal range present: {'PASS' if temporal else 'FAIL'}")
    print(f"dependence/review warnings present: {'PASS' if warnings else 'FAIL'}")
    print(f"human-readable explanations: {'PASS' if explanations else 'FAIL'}")
    print(f"review classifications valid: {'PASS' if review else 'FAIL'}")
    print(f"confidence indicators valid: {'PASS' if confidence else 'FAIL'}")
    print(f"non-destructive existing systems: {'PASS' if non_destructive else 'FAIL'}")
    print(f"deterministic rerun: {'PASS' if det else 'FAIL'}")
    print(f"durationMs: {result['durationMs']}")
    if leads:
        sample=leads[0]
        print("sample top lead:")
        print("  rank:",sample["rank"],"entity:",sample["entityId"],"score:",sample["finalPriorityScore"])
        print("  classification:",sample["reviewClassification"])
        print("  patterns:",[(p["patternType"], p["instanceCount"]) for p in sample["validatedPatterns"]])
        print("  pattern instances preserved:",len(sample.get("validatedPatternInstances", [])))
        print("  transactions:",len(sample["supportingTransactions"]))
        print("  ips:",len(sample["supportingEntities"]["ips"]))
        print("  neighbors:",sample["graphContext"]["neighborCount"])

if __name__=="__main__":
    main()
