from fastapi import APIRouter, HTTPException
from app.services.investigation_workspace import investigation_workspace

router = APIRouter(prefix='/api/v1/clusters')


@router.get('')
def clusters():
    return investigation_workspace.clusters()


@router.get('/{cluster_id}')
def cluster(cluster_id: str):
    for item in investigation_workspace.clusters():
        if item['id'] == cluster_id:
            return item
    raise HTTPException(404, 'Cluster not found')
