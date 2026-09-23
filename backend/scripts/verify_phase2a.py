"""Verify Phase 2A graph risk propagation without changing the analysis pipeline."""
from __future__ import annotations

import statistics

from app.services.analysis import analysis_service
from app.services.risk_propagation import risk_propagation_service


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = (len(values) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    fraction = index - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def main() -> int:
    state = analysis_service.get_state()
    report = state.describe()
    expected = {
        "record_count": 48000,
        "wallet_count": 10713,
        "transaction_count": 46977,
        "cluster_count": 8,
        "pattern_count": 100,
        "lead_count": 150,
        "anomaly_count": 142,
    }
    print("=== Phase 2A verification ===")
    for key, value in expected.items():
        actual = report[key]
        print(f"{key}: {actual:,} {'PASS' if actual == value else 'FAIL (expected ' + format(value, ',') + ')'}")

    results = risk_propagation_service.all(state.dataset_version)
    values = [float(item["propagatedRisk"]) for item in results.values()]
    signals = [float(item["graphPropagatedSignal"]) for item in results.values()]
    print(f"wallet results: {len(results):,}")
    print(f"propagated risk mean: {statistics.mean(values):.6f}")
    print(f"propagated risk median: {statistics.median(values):.6f}")
    print(f"propagated risk p90: {percentile(values, .90):.6f}")
    print(f"propagated risk p95: {percentile(values, .95):.6f}")
    print(f"propagated risk p99: {percentile(values, .99):.6f}")
    print(f"propagated risk max: {max(values, default=0):.6f}")
    print(f"graph signal mean: {statistics.mean(signals):.6f}")
    for threshold in (.3, .5, .7):
        print(f"count > {threshold:.1f}: {sum(value > threshold for value in values):,}")

    lead_ids = {str(lead["entityId"]) for lead in state.leads}
    outside = [item for item in results.values() if item["entityId"] not in lead_ids]
    outside.sort(key=lambda item: (-float(item["propagatedRisk"]), item["entityId"]))
    print("high propagated-risk wallets outside top 150:")
    for item in outside[:20]:
        if float(item["propagatedRisk"]) < 0.5:
            break
        contributor = item["contributors"][0] if item["contributors"] else {}
        print(
            f"  {item['entityId']} risk={item['propagatedRisk']:.4f} "
            f"base={item['baseAnomalyScore']:.4f} "
            f"contributor={contributor.get('sourceEntityId', 'none')} "
            f"hop={contributor.get('hop', '-') } "
            f"relationship={contributor.get('relationship', 'none')}"
        )

    # Determinism check: the cached second call must be byte-for-byte equivalent
    # at the Python object level.
    second = risk_propagation_service.all(state.dataset_version)
    deterministic = results == second
    bounded = all(0.0 <= float(item["propagatedRisk"]) <= 1.0 for item in results.values())
    print(f"bounded [0,1]: {'PASS' if bounded else 'FAIL'}")
    print(f"deterministic: {'PASS' if deterministic else 'FAIL'}")
    return 0 if all(report[key] == value for key, value in expected.items()) and bounded and deterministic else 1


if __name__ == "__main__":
    raise SystemExit(main())
