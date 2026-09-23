from collections import Counter

from fastapi import APIRouter

from app.services.analysis import analysis_service
from app.services.entity_clustering import entity_clustering_service
from app.services.lead_explainability_v2 import lead_explainability_v2


router = APIRouter(prefix="/api/v1/dashboard")


# Frozen production dataset / completed analysis summary.
# The detailed analysis results are served from persisted artifacts.
PRODUCTION_SUMMARY = {
    "transactions": 46977,
    "wallets": 10713,
    "ips": 3800,
    "records": 48000,
    "dataset_version": "1.0.0",
}


@router.get("/stats")
def stats():
    """
    Dashboard summary.

    Important:
    Do not use analysis_service.get_state() here because the completed
    runtime analysis state is not deployed to Render. The production
    dashboard uses the persisted Phase 3 and Phase 5C artifacts.
    """
    graph_clusters = entity_clustering_service.get()
    final_leads = lead_explainability_v2.get()

    return {
        "transactions": PRODUCTION_SUMMARY["transactions"],
        "wallets": PRODUCTION_SUMMARY["wallets"],
        "ips": PRODUCTION_SUMMARY["ips"],
        "clusters": len(graph_clusters.get("clusters", [])),
        "leads": len(final_leads.get("leads", [])),
    }


@router.get("/priority-distribution")
def priority():
    final_leads = lead_explainability_v2.get()

    leads = final_leads.get("leads", [])

    c = Counter(
        x.get("priority", "low")
        for x in leads
    )

    return {
        "high": c.get("high", 0),
        "medium": c.get("medium", 0),
        "low": c.get("low", 0),
    }


@router.get("/top-leads")
def top(limit: int = 5):
    final_leads = lead_explainability_v2.get()

    leads = final_leads.get("leads", [])

    return leads[:max(1, min(limit, 50))]


@router.get("/geo")
def geo():
    """
    Geographic summary.

    The original implementation depended on the in-memory analysis state.
    Render does not have that runtime state, so return a safe empty result
    rather than causing a 500 error.
    """
    return []


@router.get("/timeline")
def timeline():
    """
    Timeline summary.

    The original implementation depended on analysis_service.get_state()
    and therefore could fail on a fresh Render instance.
    """
    return []


@router.get("/recent-activity")
def recent():
    final_leads = lead_explainability_v2.get()

    leads = final_leads.get("leads", [])

    return [
        {
            "id": x.get("leadId"),
            "action": (
                x.get("signals", [])[0]
                if x.get("signals")
                else "Observed activity"
            ),
            "entity": x.get("entityId"),
            "time": x.get("lastActivity"),
            "type": "lead",
        }
        for x in leads[:12]
    ]


@router.get("/system")
def system():
    """
    System status based on deployed/persisted artifacts.

    Does not depend on analysis_service.get_state().
    """
    graph_clusters = entity_clustering_service.get()
    final_leads = lead_explainability_v2.get()

    cluster_count = len(
        graph_clusters.get("clusters", [])
    )

    lead_count = len(
        final_leads.get("leads", [])
    )

    return [
        {
            "name": "Dataset ingestion",
            "status": "operational",
            "detail": (
                f"{PRODUCTION_SUMMARY['records']:,} records loaded"
            ),
            "version": PRODUCTION_SUMMARY["dataset_version"],
        },
        {
            "name": "Correlation engine",
            "status": "operational",
            "detail": (
                "IP, transaction and wallet relationships built"
            ),
            "version": "1.0.0",
        },
        {
            "name": "Anomaly detection",
            "status": "operational",
            "detail": "Isolation Forest completed",
            "version": "1.0.0",
        },
        {
            "name": "Clustering",
            "status": "operational",
            "detail": f"{cluster_count} clusters",
            "version": "1.0.0",
        },
        {
            "name": "Pattern detection",
            "status": "operational",
            "detail": f"{lead_count} investigative leads",
            "version": "1.0.0",
        },
    ]