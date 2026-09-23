from fastapi import APIRouter, HTTPException
import duckdb
from app.services.analysis import analysis_service
from app.services.api_data import dataset_meta,dataset_stats,field_quality,preview,wallet_to_frontend,ip_to_frontend
from app.services.graph import GraphService, EntityNotFoundError
from app.services.paths import NORMALIZED_STORAGE_ROOT
from app.services.risk_propagation import risk_propagation_service
from app.services.entity_clustering import entity_clustering_service
from app.services.pattern_detection_v2 import pattern_detection_v2
from app.services.pattern_validation_v2 import pattern_validation_v2
from app.services.pattern_refinement_v2 import pattern_refinement_v2
from app.services.lead_explainability_v2 import lead_explainability_v2
from app.services.investigation_workspace import investigation_workspace

router=APIRouter(prefix='/api/v1')
graph=GraphService()

@router.get('/dataset/meta')
def meta(): return dataset_meta()
@router.get('/dataset/stats')
def stats(): return dataset_stats()
@router.get('/dataset/quality')
def quality(): return field_quality()
@router.get('/dataset/preview')
def dataset_preview(page:int=1,pageSize:int=10): return preview(page,pageSize)

@router.get('/entities/wallets')
def wallets(): return [wallet_to_frontend(x) for x in analysis_service.get_state().wallet_features.entity_id.tolist()]
@router.get('/entities/wallet/{id}')
def wallet(id:str):
 x=wallet_to_frontend(id)
 if x is None: raise HTTPException(404,'Wallet not found')
 return x
@router.get('/entities/ip/{id}')
def ip(id:str):
 x=ip_to_frontend(id)
 if x is None: raise HTTPException(404,'IP not found')
 return x
@router.get('/entities/ips')
def ips(): return [ip_to_frontend(x) for x in analysis_service.get_state().ip_features.entity_id.tolist()]
@router.get('/entities/{entity_id}/evidence')
def evidence(entity_id:str): return analysis_service.get_state().evidence.get(entity_id,[])
@router.get('/entities/{entity_id}/indicators')
def indicators(entity_id:str):
 s=analysis_service.get_state(); r=s.wallet_features[s.wallet_features.entity_id==entity_id]
 if r.empty:return []
 x=r.iloc[0]
 vals=[('Transaction velocity',min(float(x.transactions_per_day)/50,1)),('Network diversity',min(int(x.unique_ip_count)/5,1)),('Amount activity',min(float(x.total_volume)/100,1))]
 return [{'label':a,'value':round(v,3),'deviation':round(v,3),'status':'anomalous' if v>.7 else 'elevated' if v>.45 else 'normal'} for a,v in vals]
@router.get('/entities/{entity_id}/findings')
def findings(entity_id:str): return analysis_service.get_state().findings.get(entity_id,[])
@router.get('/entities/{entity_id}/timeline')
def timeline(entity_id:str): return analysis_service.get_state().timelines.get(entity_id,[])

@router.get('/entities/{entity_id}/propagated-risk')
def propagated_risk(entity_id: str):
    try:
        return risk_propagation_service.get(entity_id)
    except KeyError:
        raise HTTPException(404, 'Wallet not found')

@router.get('/patterns/phase4a')
def phase4a_patterns(force: bool = False):
    return pattern_detection_v2.get(force=force)

@router.get('/patterns/phase4a/{pattern_id}')
def phase4a_pattern(pattern_id: str):
    result = pattern_detection_v2.get()
    for pattern in result['patterns']:
        if pattern['id'] == pattern_id:
            return pattern
    raise HTTPException(404, 'Phase 4A pattern not found')

@router.get('/patterns/phase4b/validation')
def phase4b_validation(force: bool = False):
    return pattern_validation_v2.get(force=force)

@router.get('/patterns/phase4c/refinement')
def phase4c_refinement(force: bool = False):
    return pattern_refinement_v2.get(force=force)

@router.get('/patterns/phase4c/refinement/{pattern_id}')
def phase4c_pattern_refinement(pattern_id: str):
    result = pattern_refinement_v2.get()
    for item in result['patterns']:
        if item['patternId'] == pattern_id:
            return item
    raise HTTPException(404, 'Phase 4C refinement not found')

@router.get('/patterns/phase4b/validation/{pattern_id}')
def phase4b_pattern_validation(pattern_id: str):
    result = pattern_validation_v2.get()
    for item in result['validations']:
        if item['patternId'] == pattern_id:
            return item
    raise HTTPException(404, 'Phase 4B validation not found')

@router.get('/clusters/graph-aware')
def graph_aware_clusters(force: bool = False):
    return entity_clustering_service.get(force=force)

@router.get('/clusters/graph-aware/{cluster_id}')
def graph_aware_cluster(cluster_id: str):
    for cluster in entity_clustering_service.clusters():
        if cluster['id'] == cluster_id:
            return cluster
    raise HTTPException(404, 'Graph-aware cluster not found')


@router.get('/leads/phase5c/final')
def phase5c_final(force: bool = False):
    return lead_explainability_v2.get(force=force)

@router.get('/leads/phase5c/final/{entity_id}')
def phase5c_final_entity(entity_id: str):
    result = lead_explainability_v2.get()
    lead = next((x for x in result['leads'] if x['entityId'] == entity_id), None)
    if lead is None:
        raise HTTPException(404, 'Phase 5C lead not found')
    return lead

@router.get('/graph')
def graph_all():
  g=graph.get_graph()
  MAX_NODES=5000; MAX_EDGES=10000
  # Deterministic edge-first sampling: iterate edges in a stable sorted order
  # and only keep an edge when both endpoints fit within the node budget.
  # This guarantees every returned edge references nodes present in the
  # returned node list (self-contained payload) while staying bounded.
  ordered=list(g.edges(keys=True,data=True))
  ordered.sort(key=lambda e:(str(e[0]),str(e[1]),str(e[2])))
  seen:set[str]=set(); node_ids:list[str]=[]; selected:list[tuple]=[]
  for u,v,k,a in ordered:
   if len(selected)>=MAX_EDGES: break
   fresh=[x for x in (u,v) if x not in seen]
   if len(seen)+len(fresh)>MAX_NODES: continue
   for x in fresh: seen.add(x); node_ids.append(x)
   selected.append((u,v,k,a))
  nodes=[]
  for n in node_ids:
   a=g.nodes[n]
   nodes.append({'id':n,'label':a.get('entity_id',n),'type':a.get('type'),'shape':'circle' if a.get('type')=='wallet' else 'square' if a.get('type')=='transaction' else 'diamond','x':0,'y':0,'connections':g.degree(n)})
  edges=[]
  for i,(u,v,k,a) in enumerate(selected):
   kind='wallet-wallet' if a.get('relationship')=='common_input_association' else 'ip-tx' if a.get('relationship')=='observed_transaction' else 'wallet-tx' if a.get('relationship_class')=='transaction_wallet' and a.get('wallet_role')=='input' else 'tx-wallet'
   edges.append({'id':f'E-{i}','source':u,'target':v,'label':a.get('relationship','observed'),'amount':a.get('amount'),'timestamp':a.get('timestamp'),'kind':kind})
  return {'nodes':nodes,'edges':edges}
@router.get('/graph/entity/{entity_id}')
def graph_entity(entity_id:str):
 # infer type from node id
 g=graph.get_graph();
 if entity_id in g: nid=entity_id
 else:
  matches=[n for n,a in g.nodes(data=True) if a.get('entity_id')==entity_id]
  if not matches: raise HTTPException(404,'Entity not found')
  nid=matches[0]
 a=g.nodes[nid]; typ=a.get('type'); data=graph.neighborhood(typ,entity_id,depth=1,limit=150)
 return {'nodes':[{'id':x['id'],'label':x.get('entity_id',x['id']),'type':x['type'],'shape':'circle' if x['type']=='wallet' else 'square' if x['type']=='transaction' else 'diamond','x':0,'y':0,'connections':g.degree(x['id'])} for x in data['nodes']], 'edges':[{'id':f"E-{i}",'source':x['source'],'target':x['target'],'label':x['relationship'],'amount':x.get('amount'),'timestamp':x.get('timestamp'),'kind':'wallet-wallet' if x['relationship']=='common_input_association' else 'ip-tx'} for i,x in enumerate(data['edges'])]}

@router.get('/transactions')
def transactions():
 s=analysis_service.get_state(); g=graph.get_graph(); out=[]
 for n,a in g.nodes(data=True):
  if a.get('type')!='transaction':continue
  out.append({'id':a.get('txid',a.get('entity_id')),'txid':a.get('txid',a.get('entity_id')),'timestamp':a.get('first_seen'),'amount':float(sum(a.get('output_amounts',[]))),'fee':a.get('fee',0),'scriptType':a.get('script_type'),'inputAddresses':list(a.get('input_wallets',[])),'outputAddresses':list(a.get('output_wallets',[])),'srcIp':(a.get('src_ips') or [''])[0],'dstIp':(a.get('dst_ips') or [''])[0],'srcPort':(a.get('src_ports') or [0])[0],'dstPort':(a.get('dst_ports') or [0])[0],'anomalyScore':0,'relatedWallets':list(set(a.get('input_wallets',[]))|set(a.get('output_wallets',[])))})
  if len(out)>=500:break
 return out
@router.get('/transactions/flow-patterns')
def flow_patterns(): return investigation_workspace.flow_patterns()
@router.get('/search')
def search(q:str=''):
 if not q.strip(): return []
 q=q.lower(); s=analysis_service.get_state(); out=[]
 for x in s.leads:
  if q in x['entityId'].lower() or q in x['entityLabel'].lower() or q in x.get('clusterId','').lower(): out.append({'id':x['entityId'],'label':x['entityLabel'],'type':x['type'],'description':'Investigative lead'})
 for x in s.patterns[:50]:
  if q in x['id'].lower() or q in x['description'].lower(): out.append({'id':x['id'],'label':x['id'],'type':'transaction','description':x['description']})
 return out[:30]
@router.get('/cases')
def cases():
    return investigation_workspace.cases()

@router.get('/cases/{id}')
def case(id: str):
    item = investigation_workspace.case(id)
    if item is None:
        raise HTTPException(404, 'Case not found')
    return item

@router.post('/cases')
def create_case(payload: dict):
    return investigation_workspace.create_case(payload)

@router.post('/cases/{id}/notes')
def add_case_note(id: str, payload: dict):
    note = str(payload.get('note', '')).strip()
    if not note:
        raise HTTPException(400, 'Note is required')
    item = investigation_workspace.add_note(id, note)
    if item is None:
        raise HTTPException(404, 'Case not found')
    return item

@router.post('/cases/{id}/evidence')
def add_case_evidence(id: str, payload: dict):
    evidence_id = str(payload.get('evidenceId', '')).strip()
    if not evidence_id:
        raise HTTPException(400, 'evidenceId is required')
    item = investigation_workspace.add_evidence(id, evidence_id)
    if item is None:
        raise HTTPException(404, 'Case not found')
    return item

@router.get('/leads/phase5a/fusion')
def phase5a_lead_fusion(force: bool = False):
    from app.services.lead_fusion_v2 import lead_fusion_v2
    return lead_fusion_v2.get(force=force)

@router.get('/leads/phase5a/fusion/{entity_id}')
def phase5a_lead_fusion_entity(entity_id: str):
    from app.services.lead_fusion_v2 import lead_fusion_v2
    result = lead_fusion_v2.get()
    for item in result['candidates']:
        if item['entityId'] == entity_id:
            return item
    raise HTTPException(404, 'Phase 5A fusion lead not found in top candidates')

@router.get('/leads/phase5b/validation')
def phase5b_lead_validation(force: bool = False):
    from app.services.lead_validation_v2 import lead_validation_v2
    return lead_validation_v2.get(force=force)

@router.get('/leads/phase5b/validation/{entity_id}')
def phase5b_lead_validation_entity(entity_id: str):
    from app.services.lead_validation_v2 import lead_validation_v2
    result = lead_validation_v2.get()
    for item in result['candidates']:
        if item['entityId'] == entity_id:
            return item
    raise HTTPException(404, 'Phase 5B lead validation not found')
