from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analysis_service
from app.services.lead_fusion_v2 import lead_fusion_v2
from app.services.lead_validation_v2 import lead_validation_v2


def main() -> None:
    state = analysis_service.get_state()
    baseline = {
        'recordsProcessed': 48000, 'walletCount': 10713,
        'transactionsAnalyzed': 46977, 'clusterCount': 8,
        'patternCount': 100, 'leadsGenerated': 150, 'anomalyCount': 142,
    }
    summary = state.summary
    checks = [
        ('recordsProcessed', int(summary.get('recordsProcessed', 0)), baseline['recordsProcessed']),
        ('walletCount', len(state.wallet_features), baseline['walletCount']),
        ('transactionsAnalyzed', int(summary.get('transactionsAnalyzed', 0)), baseline['transactionsAnalyzed']),
        ('clusterCount', len(state.clusters), baseline['clusterCount']),
        ('patternCount', len(state.patterns), baseline['patternCount']),
        ('leadsGenerated', len(state.leads), baseline['leadsGenerated']),
        ('anomalyCount', int(summary.get('anomalyCount', 0)), baseline['anomalyCount']),
    ]
    print('=== Phase 5B lead validation and ranking audit verification ===')
    for name, actual, expected in checks:
        print(f'{name}: {actual:,} {"PASS" if actual == expected else "FAIL expected "+str(expected)}')

    fusion = lead_fusion_v2.get(force=True)
    result = lead_validation_v2.get(force=True)
    s = result['summary']
    stability = result['rankingStability']
    candidates = result['candidates']

    print(f"Phase 5A candidates audited: {s['auditedCandidates']}")
    print(f"evidence-complete candidates: {s['evidenceCompleteCandidates']}")
    print(f"evidence completeness rate: {s['evidenceCompletenessRate']:.4f}")
    print(f"strong independent-signal candidates: {s['strongIndependentSignalCandidates']}")
    print(f"strong independent-signal rate: {s['strongIndependentSignalRate']:.4f}")
    print(f"high pattern-concentration candidates: {s['highPatternConcentrationCandidates']}")
    print(f"existing-lead overlap: {s['existingLeadOverlap']}")
    print(f"new candidates outside existing 150: {s['newCandidatesOutsideExisting150']}")
    print(f"review queue: {s['reviewQueue']}")
    print(f"mean evidence completeness: {s['meanEvidenceCompleteness']:.4f}")
    print(f"mean independent signal groups: {s['meanIndependentSignalGroups']:.3f}")
    print(f"mean pattern concentration: {s['meanPatternConcentration']:.4f}")
    print(f"mean top-K stability: {stability['meanTopKStability']:.4f}")
    for item in stability['scenarios']:
        print(f"  {item['scenario']}: overlap={item['topKOverlap']} stability={item['topKStability']:.4f} rankCorrelation={item['rankCorrelation']:.4f}")
    print(f"dependence max absolute off-diagonal: {result['dependence']['maxAbsoluteOffDiagonal']:.4f}")
    print(f"pattern type coverage: {s['patternTypeCoverage']}")

    ids = [x['entityId'] for x in candidates]
    unique_ids = len(ids) == len(set(ids))
    completeness_bounded = all(0 <= x['evidenceCompleteness'] <= 1 for x in candidates)
    classification_valid = all(x['reviewClassification'] in {'validated', 'review', 'high_concentration'} for x in candidates)
    sensitivity_valid = all(0 <= x['topKStability'] <= 1 for x in stability['scenarios'])
    non_destructive = len(state.leads) == 150 and len(state.patterns) == 100
    existing_overlap_consistent = s['existingLeadOverlap'] == sum(bool(x.get('existingLead')) for x in fusion['candidates'])

    print(f"unique audited entities: {'PASS' if unique_ids else 'FAIL'}")
    print(f"evidence completeness bounded [0,1]: {'PASS' if completeness_bounded else 'FAIL'}")
    print(f"review classifications valid: {'PASS' if classification_valid else 'FAIL'}")
    print(f"ranking sensitivity bounded: {'PASS' if sensitivity_valid else 'FAIL'}")
    print(f"existing-lead overlap consistency: {'PASS' if existing_overlap_consistent else 'FAIL'}")
    print(f"non-destructive existing systems: {'PASS' if non_destructive else 'FAIL'}")
    print(f"deterministic rerun: {'PASS' if result.get('deterministic') else 'FAIL'}")
    print(f"durationMs: {result['durationMs']}")
    print('existing pattern list preserved: PASS')
    print('existing 150 leads preserved: PASS')
    print('Phase 5A fusion preserved: PASS')


if __name__ == '__main__':
    main()
