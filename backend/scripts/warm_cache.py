"""Precompute and persist the frozen SIH analysis artifacts.

Run once before deployment (and again only after an intentional dataset/version
change). Normal GET requests then read persisted artifacts instead of rerunning
expensive analytical stages. This is an explicit cache-generation operation.
"""
from __future__ import annotations

from app.services.analysis import analysis_service
from app.services.risk_propagation import risk_propagation_service
from app.services.entity_clustering import entity_clustering_service
from app.services.pattern_detection_v2 import pattern_detection_v2
from app.services.pattern_validation_v2 import pattern_validation_v2
from app.services.pattern_refinement_v2 import pattern_refinement_v2
from app.services.lead_fusion_v2 import lead_fusion_v2
from app.services.lead_validation_v2 import lead_validation_v2
from app.services.lead_explainability_v2 import lead_explainability_v2


def main() -> None:
    state = analysis_service.get_state()
    version = state.dataset_version
    print(f"Dataset version: {version}")
    print(f"Analysis run: {state.run_id}")

    steps = [
        ("Phase 2A risk propagation", lambda: risk_propagation_service.all(version)),
        ("Phase 3 graph-aware clustering", lambda: entity_clustering_service.get(version)),
        ("Phase 4A pattern detection", lambda: pattern_detection_v2.get()),
        ("Phase 4B pattern validation", lambda: pattern_validation_v2.get()),
        ("Phase 4C pattern refinement", lambda: pattern_refinement_v2.get()),
        ("Phase 5A lead fusion", lambda: lead_fusion_v2.get()),
        ("Phase 5B lead validation", lambda: lead_validation_v2.get()),
        ("Phase 5C final explainability", lambda: lead_explainability_v2.get()),
    ]

    for label, action in steps:
        print(f"[START] {label}")
        result = action()
        if isinstance(result, dict):
            summary = result.get("summary", {})
            print(f"[OK]    {label} :: {summary}")
        else:
            print(f"[OK]    {label}")

    print("\nAll analytical artifacts are warm and persisted under backend/data/artifacts/.")
    print("Normal dashboard requests should now read cached artifacts and not rerun the pipeline.")


if __name__ == "__main__":
    main()
