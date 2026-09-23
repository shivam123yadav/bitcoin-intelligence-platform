from fastapi import APIRouter

from app.services.analysis import analysis_service
from app.services.api_data import dataset_stats
from app.services.entity_clustering import entity_clustering_service
from app.services.lead_explainability_v2 import lead_explainability_v2

from collections import Counter


router = APIRouter(prefix='/api/v1/dashboard')


@router.get('/stats')
def stats():
    s = analysis_service.get_state()

    # Use persisted Phase 3 graph-aware clustering artifact
    graph_clusters = entity_clustering_service.get()

    # Use persisted Phase 5C final lead artifact
    final_leads = lead_explainability_v2.get()

    return {
        'transactions': s.summary['transactionsAnalyzed'],
        'wallets': s.summary['entitiesAnalyzed'] - len(s.ip_features),
        'ips': len(s.ip_features),
        'clusters': len(graph_clusters.get('clusters', [])),
        'leads': len(final_leads.get('leads', [])),
    }


@router.get('/priority-distribution')
def priority():
    final_leads = lead_explainability_v2.get()

    leads = final_leads.get('leads', [])

    c = Counter(
        x.get('priority', 'low')
        for x in leads
    )

    return {
        'high': c.get('high', 0),
        'medium': c.get('medium', 0),
        'low': c.get('low', 0),
    }


@router.get('/top-leads')
def top(limit: int = 5):
    final_leads = lead_explainability_v2.get()

    leads = final_leads.get('leads', [])

    return leads[:max(1, min(limit, 50))]


@router.get('/geo')
def geo():
    s = analysis_service.get_state()

    c = Counter(
        country
        for vals in s.wallet_features.countries
        for country in vals
    )

    return [
        {
            'country': k,
            'code': k,
            'transactions': v,
            'wallets': v,
            'ips': 0,
            'risk': (
                'high'
                if v > 1000
                else 'medium'
                if v > 300
                else 'low'
            ),
        }
        for k, v in c.most_common(15)
    ]


@router.get('/timeline')
def timeline():
    s = analysis_service.get_state()

    buckets = (
        analysis_service
        .load_observations(s.dataset_version)
        .assign(
            day=lambda x: x.timestamp_dt.dt.strftime('%Y-%m-%d')
        )
        .groupby('day')
        .size()
    )

    return [
        {
            'label': k,
            'transactions': int(v),
            'anomalies': 0,
        }
        for k, v in buckets.items()
    ]


@router.get('/recent-activity')
def recent():
    final_leads = lead_explainability_v2.get()

    leads = final_leads.get('leads', [])

    return [
        {
            'id': x.get('leadId'),
            'action': (
                x.get('signals', [])[0]
                if x.get('signals')
                else 'Observed activity'
            ),
            'entity': x.get('entityId'),
            'time': x.get('lastActivity'),
            'type': 'lead',
        }
        for x in leads[:12]
    ]


@router.get('/system')
def system():
    s = analysis_service.get_state()

    graph_clusters = entity_clustering_service.get()
    final_leads = lead_explainability_v2.get()

    cluster_count = len(
        graph_clusters.get('clusters', [])
    )

    lead_count = len(
        final_leads.get('leads', [])
    )

    return [
        {
            'name': 'Dataset ingestion',
            'status': 'operational',
            'detail': f"{s.summary['recordsProcessed']:,} records loaded",
            'version': s.dataset_version,
        },
        {
            'name': 'Correlation engine',
            'status': 'operational',
            'detail': 'IP, transaction and wallet relationships built',
            'version': '1.0.0',
        },
        {
            'name': 'Anomaly detection',
            'status': 'operational',
            'detail': 'Isolation Forest completed',
            'version': '1.0.0',
        },
        {
            'name': 'Clustering',
            'status': 'operational',
            'detail': f"{cluster_count} clusters",
            'version': '1.0.0',
        },
        {
            'name': 'Pattern detection',
            'status': 'operational',
            'detail': f"{lead_count} investigative leads",
            'version': '1.0.0',
        },
    ]