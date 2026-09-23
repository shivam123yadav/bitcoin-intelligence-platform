from fastapi import APIRouter, Query, HTTPException
from app.services.analysis import analysis_service

router=APIRouter(prefix='/api/v1/leads')

def _filter(leads, priority=None, type=None, q=None, cluster=None, min_score=None, max_score=None):
    out=leads
    if priority: out=[x for x in out if x['priority']==priority]
    if type: out=[x for x in out if x['type']==type]
    if cluster: out=[x for x in out if x.get('clusterId')==cluster]
    if min_score is not None: out=[x for x in out if x['priorityScore']>=min_score]
    if max_score is not None: out=[x for x in out if x['priorityScore']<=max_score]
    if q:
        q=q.lower(); out=[x for x in out if q in x['entityLabel'].lower() or q in x.get('clusterId','').lower() or any(q in s.lower() for s in x.get('signals',[]))]
    return out

@router.get('')
def get_leads(priority: str|None=None, type: str|None=None, q: str|None=None, cluster: str|None=None, min_score: float|None=Query(None,ge=0,le=100), max_score: float|None=Query(None,ge=0,le=100)):
    try: return _filter(analysis_service.get_state().leads,priority,type,q,cluster,min_score,max_score)
    except Exception as e: raise HTTPException(500,'Leads are unavailable') from e

@router.get('/{lead_id}')
def get_lead(lead_id:str):
    for lead in analysis_service.get_state().leads:
        if lead.get('leadId')==lead_id: return lead
    raise HTTPException(404,'Lead not found')
