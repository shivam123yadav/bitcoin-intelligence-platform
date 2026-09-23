import type { DatasetMeta, DatasetStats, DatasetFieldQuality, DatasetPreviewRow, DatasetCatalog, DatasetRecord, AnalysisStage, AnalysisResult, AnalysisStatus, InvestigativeLead, Phase5CLead, Phase5CResponse, WalletEntity, IPObservation, Cluster, Evidence, BehavioralIndicator, ModelFinding, GraphNode, GraphEdge, TimelineEvent, FlowPattern, CaseRecord, Transaction, SystemComponent, ActivityTimelinePoint, DashboardStats, PriorityDistribution, GeoOverviewItem, RecentActivityItem, SearchResult, Priority, BackendHealth } from '@/types';
import { USE_MOCK, apiFetch, mockDelay, probeBackendHealth } from './config';
import { mockDatasetMeta,mockDatasetStats,mockDatasetFieldQuality,mockDatasetPreview,mockAnalysisStages,mockLeads,mockWallets,mockIPs,mockClusters,mockEvidence,mockBehavioralIndicators,mockModelFindings,mockGraphNodes,mockGraphEdges,mockTimeline,mockFlowPatterns,mockCases,mockTransactions,mockSystemComponents,mockActivityTimeline,mockSearchIndex,mockPriorityDistribution,mockGeoOverview,mockRecentActivity } from '@/mock-data';

const live = <T>(path:string, options?:RequestInit) => apiFetch<T>(path, options);

export const datasetService = {
 async getMeta():Promise<DatasetMeta>{ if(USE_MOCK)return mockDelay(mockDatasetMeta); return live('/dataset/meta'); },
 async getStats():Promise<DatasetStats>{ if(USE_MOCK)return mockDelay(mockDatasetStats); return live('/dataset/stats'); },
 async getFieldQuality():Promise<DatasetFieldQuality[]>{ if(USE_MOCK)return mockDelay(mockDatasetFieldQuality); return live('/dataset/quality'); },
 async getPreview(page=1,pageSize=10):Promise<{rows:DatasetPreviewRow[];total:number;page:number;pageSize:number}>{ if(USE_MOCK){const start=(page-1)*pageSize;return mockDelay({rows:mockDatasetPreview.slice(start,start+pageSize),total:mockDatasetPreview.length,page,pageSize});} return live(`/dataset/preview?page=${page}&pageSize=${pageSize}`); },
 async getCatalog():Promise<DatasetCatalog>{ if(USE_MOCK)return mockDelay({activeDatasetId:'synthetic_traffic_v1.0.0',datasets:[{id:'synthetic_traffic_v1.0.0',filename:mockDatasetMeta.filename,format:'csv',status:'analyzed',analysisStatus:'completed',records:mockDatasetMeta.records,uploadedAt:mockDatasetMeta.uploadedAt,source:'bundled'}]}); return live('/dataset/catalog'); },
 async upload(file:File):Promise<{dataset:DatasetRecord;message:string}>{ if(USE_MOCK)return mockDelay({dataset:{id:`mock-${Date.now()}`,filename:file.name,format:file.name.split('.').pop()?.toLowerCase() as any,status:'stored',analysisStatus:'not_run',records:0,uploadedAt:new Date().toISOString(),source:'upload'},message:'Dataset stored'}); return live(`/dataset/upload?filename=${encodeURIComponent(file.name)}`,{method:'POST',body:file}); },
 async select(datasetId:string):Promise<{dataset:DatasetRecord;message:string}>{ if(USE_MOCK)return mockDelay({dataset:{} as DatasetRecord,message:'Dataset selected'}); return live(`/dataset/select/${encodeURIComponent(datasetId)}`,{method:'POST'}); },
};

export const analysisService = {
 async getStages():Promise<AnalysisStage[]>{ if(USE_MOCK)return mockDelay(mockAnalysisStages); return live('/analysis/stages'); },
 async getResult():Promise<AnalysisResult>{ if(USE_MOCK)return mockDelay({stages:mockAnalysisStages,recordsProcessed:48521,entitiesAnalyzed:12482,transactionsAnalyzed:48521,durationMs:53400,leadsGenerated:127,completedAt:'2024-11-30T22:41:00Z'}); return live('/analysis/result'); },
 async runAnalysis():Promise<AnalysisStage[]>{ if(USE_MOCK)return mockDelay(mockAnalysisStages,800); return live('/analysis/run',{method:'POST'}); },
 async getStatus():Promise<AnalysisStatus>{ if(USE_MOCK)return mockDelay({status:'completed',run_id:'mock-run',progress:100}); return live('/analysis/status'); },
};

const phase5cToLead = (lead: Phase5CLead): InvestigativeLead => ({
  rank: lead.rank,
  entityId: lead.entityId,
  entityLabel: lead.entityLabel,
  type: lead.type,
  priority: lead.priority,
  priorityScore: lead.finalPriorityScore,
  mlAnomaly: lead.signalBreakdown.anomalyScore.toFixed(3),
  clusterId: '—',
  signals: lead.validatedPatterns.map((p) => `${p.patternType} (${p.instanceCount})`),
  lastActivity: lead.temporalRange.lastSeen ?? '',
});

export const leadService = {
 async getLeads(filters?:{priority?:Priority|'all';type?:string;query?:string}):Promise<InvestigativeLead[]>{
  if(USE_MOCK){let result=[...mockLeads];if(filters?.priority&&filters.priority!=='all')result=result.filter(l=>l.priority===filters.priority);if(filters?.type&&filters.type!=='all')result=result.filter(l=>l.type===filters.type);if(filters?.query){const q=filters.query.toLowerCase();result=result.filter(l=>l.entityLabel.toLowerCase().includes(q)||l.clusterId.toLowerCase().includes(q)||l.signals.some(s=>s.toLowerCase().includes(q)));}return mockDelay(result);}
  const raw=await live<Phase5CResponse>('/leads/phase5c/final');
  let result=raw.leads.map(phase5cToLead);
  if(filters?.priority&&filters.priority!=='all')result=result.filter(l=>l.priority===filters.priority);
  if(filters?.type&&filters.type!=='all')result=result.filter(l=>l.type===filters.type);
  if(filters?.query){const q=filters.query.toLowerCase();result=result.filter(l=>`${l.entityLabel} ${l.entityId} ${l.signals.join(' ')}`.toLowerCase().includes(q));}
  return result;
 },
 async getFinalLeads():Promise<Phase5CResponse>{
  if(USE_MOCK){
    const leads=mockLeads.map((l, i) => ({
      leadId:`MOCK-${i+1}`, entityId:l.entityId, entityLabel:l.entityLabel, type:l.type, rank:l.rank, priority:l.priority, finalPriorityScore:l.priorityScore,
      scoreSemantics:'Mock investigative priority score.', analyticalConfidenceIndicator:{label:'moderate',sourceConfidence:0.7,evidenceCompleteness:1,confidenceEvidenceGap:0.3,semantics:'Mock indicator.'},
      signalBreakdown:{fusionScore:l.priorityScore/100,anomalyScore:0,propagatedRisk:0,patternEvidenceScore:0,graphContextScore:0,networkDiversityScore:0,evidenceCompleteness:1,independentSignalGroups:0,topKStability:1},
      validatedPatterns:[],validatedPatternInstances:[],supportingEntities:{wallets:[l.entityId],transactions:[],ips:[]},supportingTransactions:[],networkObservations:{ips:[],countries:[],asns:[],observationCount:0,transactionCount:0},graphContext:{neighborCount:0,neighbors:[],relationships:[],depth:1},temporalRange:{firstSeen:null,lastSeen:l.lastActivity},evidenceProvenance:[],warnings:[],reviewClassification:'review',existingLead:true,explanation:'Mock lead.'
    })) as Phase5CLead[];
    return mockDelay({datasetVersion:'mock',method:'Phase 5C mock',destructive:false,scoreSemantics:'Mock score.',rankingMethod:{},semantics:{},summary:{finalLeads:leads.length,highPriority:leads.filter(x=>x.priority==='high').length,mediumPriority:leads.filter(x=>x.priority==='medium').length,lowPriority:leads.filter(x=>x.priority==='low').length,existingLeadOverlap:leads.length,newCandidatesOutsideExisting150:0,reviewQueue:0,meanFinalPriorityScore:0,meanEvidenceCompleteness:1,meanIndependentSignalGroups:0,meanTopKStability:1},dependenceAudit:{},rankingStability:{},leads,durationMs:0});
  }
  return live('/leads/phase5c/final');
 },
 async getFinalLead(entityId:string):Promise<Phase5CLead>{
  return live(`/leads/phase5c/final/${encodeURIComponent(entityId)}`);
 },
};

const walletFromEntity = (r:any):WalletEntity|undefined => {
 if(!r)return undefined; if(r.address)return r as WalletEntity;
 const d=r.data??{}; const score=Number(d.anomalyScore??0); return {id:r.entity_id,address:d.address??r.entity_id,type:'wallet',priority:'low',priorityScore:0,investigationStatus:'requires_review',transactions:Number(d.transaction_count??0),connectedWallets:Number(r.neighbor_count??0),observedIps:Number(d.related_ip_count??0),countries:Number((d.countries??[]).length),clusterId:'',totalVolumeBtc:0,anomalyScore:score,mlAnomalyLabel:'',lastActivity:d.last_seen??'',firstSeen:d.first_seen??'',signals:[],countriesList:d.countries??[]};
};

export const entityService = {
 async getWallet(id:string):Promise<WalletEntity|undefined>{ if(USE_MOCK)return mockDelay(mockWallets.find(w=>w.id===id)); const r=await live<any>(`/entities/wallet/${encodeURIComponent(id)}`); return walletFromEntity(r); },
 async getWallets():Promise<WalletEntity[]>{ if(USE_MOCK)return mockDelay(mockWallets); return live('/entities/wallets'); },
 async getIP(id:string):Promise<IPObservation|undefined>{ if(USE_MOCK)return mockDelay(mockIPs.find(ip=>ip.id===id)); return live(`/entities/ip/${encodeURIComponent(id)}`); },
 async getIPs():Promise<IPObservation[]>{ if(USE_MOCK)return mockDelay(mockIPs); return live('/entities/ips'); },
 async getEvidence(entityId:string):Promise<Evidence[]>{ if(USE_MOCK)return mockDelay(mockEvidence[entityId]??[]); return live(`/entities/${encodeURIComponent(entityId)}/evidence`); },
 async getBehavioralIndicators(entityId:string):Promise<BehavioralIndicator[]>{ if(USE_MOCK)return mockDelay(mockBehavioralIndicators[entityId]??[]); return live(`/entities/${encodeURIComponent(entityId)}/indicators`); },
 async getModelFindings(entityId:string):Promise<ModelFinding[]>{ if(USE_MOCK)return mockDelay(mockModelFindings[entityId]??[]); return live(`/entities/${encodeURIComponent(entityId)}/findings`); },
 async getTimeline(entityId:string):Promise<TimelineEvent[]>{ if(USE_MOCK)return mockDelay(mockTimeline[entityId]??[]); return live(`/entities/${encodeURIComponent(entityId)}/timeline`); },
};

export const graphService = {
 async getGraph():Promise<{nodes:GraphNode[];edges:GraphEdge[]}>{ if(USE_MOCK)return mockDelay({nodes:mockGraphNodes,edges:mockGraphEdges}); return live('/graph'); },
 async getEntityGraph(entityId:string):Promise<{nodes:GraphNode[];edges:GraphEdge[]}>{ if(USE_MOCK){const connectedEdges=mockGraphEdges.filter(e=>e.source===entityId||e.target===entityId);const nodeIds=new Set<string>([entityId]);connectedEdges.forEach(e=>{nodeIds.add(e.source);nodeIds.add(e.target)});return mockDelay({nodes:mockGraphNodes.filter(n=>nodeIds.has(n.id)),edges:connectedEdges});} return live(`/graph/entity/${encodeURIComponent(entityId)}`); },
};

export const transactionService = {
 async getTransactions():Promise<Transaction[]>{ if(USE_MOCK)return mockDelay(mockTransactions); return live('/transactions'); },
 async getTransaction(id:string):Promise<Transaction|undefined>{ if(USE_MOCK)return mockDelay(mockTransactions.find(t=>t.id===id)); try{return await live(`/transactions/${encodeURIComponent(id)}`);}catch{return undefined;} },
 async getFlowPatterns():Promise<FlowPattern[]>{ if(USE_MOCK)return mockDelay(mockFlowPatterns); return live('/transactions/flow-patterns'); },
};

export const clusterService = {
 async getClusters():Promise<Cluster[]>{ if(USE_MOCK)return mockDelay(mockClusters); return live('/clusters'); },
 async getCluster(id:string):Promise<Cluster|undefined>{ if(USE_MOCK)return mockDelay(mockClusters.find(c=>c.id===id)); try{return await live(`/clusters/${encodeURIComponent(id)}`);}catch{return undefined;} },
};

export const caseService = {
 async getCases():Promise<CaseRecord[]>{ if(USE_MOCK)return mockDelay(mockCases); return live('/cases'); },
 async getCase(id:string):Promise<CaseRecord|undefined>{ if(USE_MOCK)return mockDelay(mockCases.find(c=>c.id===id)); try{return await live(`/cases/${encodeURIComponent(id)}`);}catch{return undefined;} },
 async createCase(payload:Partial<CaseRecord>):Promise<CaseRecord>{ if(USE_MOCK)return mockDelay({...mockCases[0], ...payload, id:payload.id??`MOCK-${Date.now()}`} as CaseRecord); return live('/cases',{method:'POST',body:JSON.stringify(payload)}); },
 async addNote(id:string,note:string):Promise<CaseRecord>{ if(USE_MOCK)return mockDelay(mockCases.find(c=>c.id===id)!); return live(`/cases/${encodeURIComponent(id)}/notes`,{method:'POST',body:JSON.stringify({note})}); },
 async addEvidence(id:string,evidenceId:string):Promise<CaseRecord>{ if(USE_MOCK)return mockDelay(mockCases.find(c=>c.id===id)!); return live(`/cases/${encodeURIComponent(id)}/evidence`,{method:'POST',body:JSON.stringify({evidenceId})}); },
};

export const dashboardService = {
 async getStats():Promise<DashboardStats>{ if(USE_MOCK)return mockDelay({transactions:48521,wallets:12482,ips:3821,clusters:147,leads:127}); return live('/dashboard/stats'); },
 async getTimeline():Promise<ActivityTimelinePoint[]>{ if(USE_MOCK)return mockDelay(mockActivityTimeline); return live('/dashboard/timeline'); },
 async getPriorityDistribution():Promise<PriorityDistribution>{ if(USE_MOCK)return mockDelay(mockPriorityDistribution); return live('/dashboard/priority-distribution'); },
 async getTopLeads(limit=5):Promise<InvestigativeLead[]>{ if(USE_MOCK)return mockDelay(mockLeads.slice(0,limit)); return live(`/dashboard/top-leads?limit=${limit}`); },
 async getGeoOverview():Promise<GeoOverviewItem[]>{ if(USE_MOCK)return mockDelay(mockGeoOverview); return live('/dashboard/geo'); },
 async getRecentActivity():Promise<RecentActivityItem[]>{ if(USE_MOCK)return mockDelay(mockRecentActivity); return live('/dashboard/recent-activity'); },
 async getSystemReadiness():Promise<SystemComponent[]>{ if(USE_MOCK)return mockDelay(mockSystemComponents); return live('/dashboard/system'); },
};

export const searchService = {
 async search(query:string):Promise<SearchResult[]>{ if(USE_MOCK){if(!query.trim())return mockDelay([]);const q=query.toLowerCase();return mockDelay(mockSearchIndex.filter(r=>r.label.toLowerCase().includes(q)||r.id.toLowerCase().includes(q)||r.description.toLowerCase().includes(q)));} const raw = await live<any[]>(`/search?q=${encodeURIComponent(query)}`); return (raw ?? []).map((r) => ({ id: r.id, label: r.label, type: r.type, priority: r.priority, description: r.description ?? '', route: r.route ?? (r.type === 'wallet' || r.type === 'ip' ? `entity:${r.id}` : r.type === 'transaction' ? `transaction-flow:${r.id}` : r.type === 'cluster' ? `clusters:${r.id}` : `overview:${r.id}`) })); },
};

export const healthService = {
  /**
   * Local backend liveness (`GET /api/health`). Resolves to `null` instead of
   * throwing when the backend process is unreachable, so the status indicators
   * can render an offline state without any error handling of their own.
   */
  async getHealth():Promise<BackendHealth|null>{ if(USE_MOCK)return mockDelay({status:'ok',service:'mock-backend',version:'0.0.0'}); return probeBackendHealth(); },
};
