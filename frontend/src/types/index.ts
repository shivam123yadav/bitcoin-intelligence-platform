// Centralized domain types for the Bitcoin Intelligence platform.
// These mirror the shape the future FastAPI backend will return.

export type Priority = 'high' | 'medium' | 'low';

export type EntityType = 'wallet' | 'transaction' | 'ip' | 'cluster';

export type LeadType = 'wallet' | 'transaction' | 'cluster' | 'ip';

export type AnalysisStageStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'warning'
  | 'failed';

export type DatasetFormat = 'csv' | 'json' | 'xml';

export type ScriptType =
  | 'P2PKH'
  | 'P2SH'
  | 'P2WPKH'
  | 'P2WSH'
  | 'P2TR'
  | 'MultiSig'
  | 'OP_RETURN';

export type InvestigationStatus =
  | 'requires_review'
  | 'under_investigation'
  | 'flagged'
  | 'cleared';

export type CaseStatus =
  | 'open'
  | 'under_review'
  | 'pending_approval'
  | 'closed';

export type EvidenceSeverity = 'high' | 'medium' | 'low';

export type EvidenceKind =
  | 'flagged_review'
  | 'anomalous_behavior'
  | 'observed_association'
  | 'potential_pattern';

// ---------- Dataset ----------

export interface DatasetFieldQuality {
  field: string;
  coverage: number; // percentage 0-100
  invalid: number; // count
  status: 'good' | 'warning' | 'critical';
}

export interface DatasetMeta {
  filename: string;
  format: DatasetFormat;
  fileSizeBytes: number;
  records: number;
  timeRangeStart: string;
  timeRangeEnd: string;
  validationStatus: 'valid' | 'warning' | 'invalid';
  uploadedAt: string;
}

export interface DatasetRecord {
  id: string;
  filename: string;
  format: DatasetFormat;
  status: 'analyzed' | 'stored';
  analysisStatus: 'completed' | 'not_run';
  records: number;
  validRecords?: number;
  invalidRecords?: number;
  uniqueTxids?: number;
  wallets?: number;
  ips?: number;
  countries?: number;
  asns?: number;
  timeRangeStart?: string;
  timeRangeEnd?: string;
  fileSizeBytes?: number;
  sha256?: string;
  uploadedAt: string;
  source: 'bundled' | 'upload';
}

export interface DatasetCatalog {
  activeDatasetId: string;
  datasets: DatasetRecord[];
}

export interface DatasetStats {
  transactions: number;
  wallets: number;
  ips: number;
  countries: number;
  asns: number;
  validRecords: number;
  invalidRecords: number;
  duplicates: number;
}

export interface DatasetPreviewRow {
  id: number;
  timestamp: string;
  src_ip: string;
  dst_ip: string;
  src_port: number;
  dst_port: number;
  txid: string;
  input_addresses: string[];
  output_addresses: string[];
  input_amounts: number[];
  output_amounts: number[];
  fee: number;
  script_type: ScriptType;
}

// ---------- Transactions ----------

export interface Transaction {
  id: string; // TX-XXXX
  txid: string; // full tx hash (mock)
  timestamp: string;
  amount: number; // BTC
  fee: number;
  scriptType: ScriptType;
  inputAddresses: string[];
  outputAddresses: string[];
  srcIp: string;
  dstIp: string;
  srcPort: number;
  dstPort: number;
  anomalyScore: number; // 0-1
  relatedWallets: string[]; // wallet entity IDs
}

// ---------- Wallets / Entities ----------

export interface WalletEntity {
  id: string; // Wallet-XXXX
  address: string; // btc-style address (mock)
  type: 'wallet';
  priority: Priority;
  priorityScore: number; // 0-100
  investigationStatus: InvestigationStatus;
  transactions: number;
  connectedWallets: number;
  observedIps: number;
  countries: number;
  clusterId: string;
  totalVolumeBtc: number;
  anomalyScore: number; // 0-1
  mlAnomalyLabel: string;
  lastActivity: string;
  firstSeen: string;
  signals: string[];
  countriesList: string[];
}

// ---------- IP Observations ----------

export interface IPObservation {
  id: string; // IP-XXXX
  ip: string;
  asn: string;
  country: string;
  countryCode: string;
  city: string;
  observations: number;
  relatedWallets: number;
  relatedTransactions: number;
  firstSeen: string;
  lastSeen: string;
  riskLevel: Priority;
}

// ---------- Clusters ----------

export interface Cluster {
  id: string; // C-XX
  name: string;
  walletCount: number;
  ipCount: number;
  countries: number;
  countriesList: string[];
  totalVolumeBtc: number;
  avgAnomalyScore: number;
  behavioralTags: string[];
  memberWalletIds: string[];
  associatedIpIds: string[];
  associatedTxIds: string[];
  created: string;
}

// ---------- Evidence ----------

export interface Evidence {
  id: string;
  kind: EvidenceKind;
  severity: EvidenceSeverity;
  title: string;
  description: string;
  metric: string;
}

// ---------- Behavioral indicators ----------

export interface BehavioralIndicator {
  label: string;
  value: number; // 0-1 normalized
  deviation: number; // 0-1 how far from baseline
  status: 'normal' | 'elevated' | 'anomalous';
}

// ---------- Model findings ----------

export interface ModelFinding {
  model: string;
  metric: string;
  value: number;
  label: string;
  description: string;
}

// ---------- Graph ----------

export type GraphNodeShape = 'circle' | 'square' | 'diamond' | 'boundary';

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  shape: GraphNodeShape;
  priority?: Priority;
  priorityScore?: number;
  clusterId?: string;
  anomalyScore?: number;
  x: number;
  y: number;
  connections?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  amount?: number;
  timestamp?: string;
  kind: 'wallet-tx' | 'tx-wallet' | 'ip-tx' | 'wallet-wallet' | 'member';
}

// ---------- Timeline ----------

export interface TimelineEvent {
  id: string;
  timestamp: string;
  txId: string;
  amount: number;
  direction: 'in' | 'out';
  relatedEntity: string;
  relatedEntityType: EntityType;
  fee: number;
}

// ---------- Investigative Leads ----------

export interface InvestigativeLead {
  rank: number;
  entityId: string;
  entityLabel: string;
  type: LeadType;
  priority: Priority;
  priorityScore: number;
  mlAnomaly: string;
  clusterId: string;
  signals: string[];
  lastActivity: string;
}

export interface Phase5CPatternSummary {
  patternType: string;
  instanceCount: number;
  patternIds: string[];
  meanPriorityScore: number;
  meanConfidenceScore: number;
  meanEvidenceSupportScore: number;
  supportingWalletCount: number;
  supportingTransactionCount: number;
  supportingIpEvidence: boolean;
  temporalConsistent: boolean;
}

export interface Phase5CLead {
  leadId: string;
  entityId: string;
  entityLabel: string;
  type: LeadType;
  rank: number;
  priority: Priority;
  finalPriorityScore: number;
  scoreSemantics: string;
  analyticalConfidenceIndicator: {
    label: string;
    sourceConfidence: number;
    evidenceCompleteness: number;
    confidenceEvidenceGap: number;
    semantics: string;
  };
  signalBreakdown: {
    fusionScore: number;
    anomalyScore: number;
    propagatedRisk: number;
    patternEvidenceScore: number;
    graphContextScore: number;
    networkDiversityScore: number;
    evidenceCompleteness: number;
    independentSignalGroups: number;
    topKStability: number;
  };
  validatedPatterns: Phase5CPatternSummary[];
  validatedPatternInstances: Array<{
    patternId: string;
    patternType: string;
    priorityScore: number;
    confidenceScore: number;
    evidenceSupportScore: number;
    confidenceEvidenceGap: number;
    overlapGroup?: string | null;
    supportingWalletCount: number;
    supportingTransactionCount: number;
    supportingIpEvidence: boolean;
    temporalConsistent: boolean;
    validationNotes: string[];
  }>;
  supportingEntities: { wallets: string[]; transactions: string[]; ips: string[] };
  supportingTransactions: Array<Record<string, unknown>>;
  networkObservations: { ips: string[]; countries: string[]; asns: string[]; observationCount: number; transactionCount: number };
  graphContext: { neighborCount: number; neighbors: Array<Record<string, unknown>>; relationships: Array<Record<string, unknown>>; depth: number };
  temporalRange: { firstSeen: string | null; lastSeen: string | null };
  evidenceProvenance: Array<{ stage: string; source: string; items: string[] }>;
  warnings: string[];
  reviewClassification: 'validated' | 'review' | 'high_concentration';
  existingLead: boolean;
  explanation: string;
}

export interface Phase5CResponse {
  datasetVersion: string;
  method: string;
  destructive: boolean;
  scoreSemantics: string;
  summary: {
    finalLeads: number;
    highPriority: number;
    mediumPriority: number;
    lowPriority: number;
    existingLeadOverlap: number;
    newCandidatesOutsideExisting150: number;
    reviewQueue: number;
    meanFinalPriorityScore: number;
    meanEvidenceCompleteness: number;
    meanIndependentSignalGroups: number;
    meanTopKStability: number;
  };
  dependenceAudit: Record<string, unknown>;
  rankingStability: Record<string, unknown>;
  leads: Phase5CLead[];
  durationMs: number;
}

// ---------- Transaction Flow ----------

export interface FlowStep {
  id: string;
  walletId: string;
  walletLabel: string;
  amount: number;
  txId: string;
  timestamp: string;
  fee: number;
  note?: string;
}

export interface FlowPattern {
  id: string;
  name: string;
  confidence: 'low' | 'medium' | 'high';
  description: string;
  observations: string[];
  steps: FlowStep[];
  kind: 'peeling' | 'mixing' | 'fan-out' | 'fan-in' | 'circular';
}

// ---------- Cases ----------

export interface CaseRecord {
  id: string; // INV-XXXX
  primaryEntity: string;
  primaryEntityLabel: string;
  priority: Priority;
  priorityScore: number;
  status: CaseStatus;
  created: string;
  updated: string;
  analyst: string;
  summary: string;
  evidenceIds: string[];
  patternIds: string[];
  relatedEntities: string[];
  modelFindings: ModelFinding[];
  notes?: Array<{ text: string; created: string }>;
}

// ---------- Analysis Pipeline ----------

export interface AnalysisStage {
  id: number;
  name: string;
  status: AnalysisStageStatus;
  description: string;
  detail?: string;
  progress?: number; // 0-100
  durationMs?: number;
}

export interface AnalysisResult {
  stages: AnalysisStage[];
  recordsProcessed: number;
  entitiesAnalyzed: number;
  transactionsAnalyzed: number;
  durationMs: number;
  leadsGenerated: number;
  completedAt: string;
}

// ---------- System readiness ----------

export interface SystemComponent {
  name: string;
  status: 'operational' | 'degraded' | 'offline';
  detail: string;
  version: string;
}

// ---------- Dashboard timeline ----------

export interface ActivityTimelinePoint {
  label: string;
  transactions: number;
  anomalies: number;
}

// ---------- Dashboard ----------

export interface DashboardStats {
  transactions: number;
  wallets: number;
  ips: number;
  clusters: number;
  leads: number;
}

export interface PriorityDistribution {
  high: number;
  medium: number;
  low: number;
}

export interface GeoOverviewItem {
  country: string;
  code: string;
  transactions: number;
  wallets: number;
  ips: number;
  risk: Priority;
}

export type RecentActivityType = 'analysis' | 'lead' | 'cluster' | 'pattern' | 'case' | 'graph';

export interface RecentActivityItem {
  id: string;
  action: string;
  entity: string;
  time: string;
  type: RecentActivityType;
}

// ---------- Global search ----------

export interface SearchResult {
  id: string;
  label: string;
  type: LeadType;
  priority?: Priority;
  description: string;
  route: string;
}

// ---------- Local backend status ----------

/** Payload of `GET /api/health` served by the local FastAPI backend. */
export interface BackendHealth {
  status: string;
  service: string;
  version: string;
}

/**
 * Connectivity of the *local* backend process as reported by the status
 * indicators. This is never about an external internet service.
 */
export type BackendConnectivity = 'checking' | 'connected' | 'offline';

/** Payload of `GET /api/v1/analysis/status`. */
export interface AnalysisStatus {
  status: string;
  run_id: string | null;
  progress: number;
}

// ---------- Navigation ----------

export type PageId =
  | 'overview'
  | 'dataset'
  | 'analysis'
  | 'leads'
  | 'entity'
  | 'graph'
  | 'transaction-flow'
  | 'clusters'
  | 'cases'
  | 'settings';
