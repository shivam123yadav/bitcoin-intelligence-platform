from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analysis_service
from app.services.entity_clustering import entity_clustering_service


state = analysis_service.get_state()
result = entity_clustering_service.get()
metrics = result["metrics"]
summary = state.summary

expected = {
    "recordsProcessed": 48000,
    "walletCount": 10713,
    "transactionsAnalyzed": 46977,
    "clusterCount": 8,
    "patternCount": 100,
    "leadsGenerated": 150,
    "anomalyCount": 142,
}
actual = {
    "recordsProcessed": int(summary.get("recordsProcessed", 0)),
    "walletCount": len(state.wallet_features),
    "transactionsAnalyzed": int(summary.get("transactionsAnalyzed", 0)),
    "clusterCount": len(state.clusters),
    "patternCount": len(state.patterns),
    "leadsGenerated": len(state.leads),
    "anomalyCount": int(summary.get("anomalyCount", 0)),
}

print("=== Phase 3 graph-aware clustering verification ===")
for key, expected_value in expected.items():
    status = "PASS" if actual[key] == expected_value else "FAIL"
    print(f"{key}: {actual[key]:,} {status}")
print(f"graph-aware wallets: {metrics['walletCount']:,}")
print(f"graph-aware clusters: {metrics['clusterCount']:,}")
print(f"graph-aware noise wallets: {metrics['noiseWalletCount']:,}")
print(f"graph-aware noise rate: {metrics['noiseRate']:.4f}")
print(f"largest graph-aware cluster: {metrics['largestClusterSize']:,}")
print(f"median graph-aware cluster size: {metrics['medianClusterSize']:.2f}")
print(f"silhouette: {metrics['silhouetteScore']}")
print(f"ARI vs existing clustering: {metrics['adjustedRandAgainstExisting']:.6f}")
print(f"common-input edges: {metrics['commonInputEdgeCount']:,}")
print(f"internal common-input edges: {metrics['internalCommonInputEdgeCount']:,}")
print(f"internal common-input edge rate: {metrics['internalCommonInputEdgeRate']:.4f}")
print(f"existing cluster_id preserved: {'PASS' if 'cluster_id' in state.wallet_features.columns else 'FAIL'}")
print(f"assignment count: {len(result['assignments']):,}")
rerun = entity_clustering_service.get(force=True)
print("deterministic rerun:", "PASS" if rerun["assignments"] == result["assignments"] else "FAIL")
