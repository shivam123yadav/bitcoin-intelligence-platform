import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Filter, Search, Target, ShieldCheck, AlertTriangle } from 'lucide-react';
import { leadService } from '@/services';
import { PriorityBadge, ScoreBar } from '@/components/shared';
import { formatNumber, timeAgo } from '@/utils';
import type { InvestigativeLead, PageId, Priority } from '@/types';

interface Props { onNavigate: (page: PageId) => void; onOpenEntity: (id: string) => void; }

export function InvestigativeLeadsPage({ onNavigate, onOpenEntity }: Props) {
  const [leads, setLeads] = useState<InvestigativeLead[]>([]);
  const [query, setQuery] = useState(''); const [priority, setPriority] = useState<Priority | 'all'>('all');
  const [type, setType] = useState('all'); const [signal, setSignal] = useState('all'); const [sort, setSort] = useState('priority');
  const [summary, setSummary] = useState<{meanFinalPriorityScore:number;reviewQueue:number;existingLeadOverlap:number;newCandidatesOutsideExisting150:number}>();
  const [loadError, setLoadError] = useState<string | null>(null);
  useEffect(() => {
    leadService.getFinalLeads().then((result) => {
      setLeads(result.leads.map((lead) => ({
        rank: lead.rank, entityId: lead.entityId, entityLabel: lead.entityLabel, type: lead.type, priority: lead.priority,
        priorityScore: lead.finalPriorityScore, mlAnomaly: lead.signalBreakdown.anomalyScore.toFixed(3), clusterId: '—',
        signals: lead.validatedPatterns.map((p) => `${p.patternType} (${p.instanceCount})`), lastActivity: lead.temporalRange.lastSeen ?? '',
      })));
      setSummary(result.summary);
    }).catch((error) => setLoadError(error instanceof Error ? error.message : 'Unable to load Phase 5C leads.'));
  }, []);
  const filtered = useMemo(() => leads.filter((lead) =>
    (!query || `${lead.entityLabel} ${lead.entityId} ${lead.signals.join(' ')}`.toLowerCase().includes(query.toLowerCase())) &&
    (priority === 'all' || lead.priority === priority) && (type === 'all' || lead.type === type) &&
    (signal === 'all' || lead.signals.some((item) => item === signal))
  ).sort((a, b) => sort === 'recent' ? b.lastActivity.localeCompare(a.lastActivity) : b.priorityScore - a.priorityScore), [leads, query, priority, type, signal, sort]);
  const counts = { high: leads.filter((x) => x.priority === 'high').length, medium: leads.filter((x) => x.priority === 'medium').length, low: leads.filter((x) => x.priority === 'low').length };
  const signals = [...new Set(leads.flatMap((lead) => lead.signals))];
  return <div className="space-y-4 animate-fade-in">
    <div><div className="flex items-center gap-2"><h1 className="text-xl font-semibold text-ink-100">Investigative Leads</h1><span className="badge bg-intel-500/10 text-intel-300 border border-intel-500/20"><ShieldCheck size={11}/> Phase 5C</span></div><p className="text-sm text-ink-300 mt-0.5">Validated investigative priority queue with evidence-backed explanations.</p></div>
    <div className="grid grid-cols-4 gap-3">{[
      ['Final Leads', leads.length, 'text-signal-400'], ['High Priority', counts.high, 'text-critical-400'], ['Review Queue', summary?.reviewQueue ?? 0, 'text-warn-400'], ['New Candidates', summary?.newCandidatesOutsideExisting150 ?? 0, 'text-intel-400'],
    ].map(([label, value, color]) => <div key={label as string} className="panel p-4"><div className={`text-lg font-semibold ${color}`}>{formatNumber(value as number)}</div><div className="stat-label mt-1">{label}</div></div>)}</div>
    <div className="panel p-3 flex flex-wrap gap-2 items-center"><Search size={15} className="text-ink-400" /><input className="input flex-1 min-w-52" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search wallet, TXID, IP, or signal…" />
      <Filter size={15} className="text-ink-400" />
      <select className="input" value={priority} onChange={(e) => setPriority(e.target.value as Priority | 'all')}><option value="all">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
      <select className="input" value={type} onChange={(e) => setType(e.target.value)}><option value="all">All entities</option><option value="wallet">Wallet</option><option value="transaction">Transaction</option><option value="ip">IP</option><option value="cluster">Cluster</option></select>
      <select className="input" value={signal} onChange={(e) => setSignal(e.target.value)}><option value="all">All signals</option>{signals.map((s) => <option key={s}>{s}</option>)}</select>
      <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}><option value="priority">Priority score</option><option value="anomaly">Anomaly score</option><option value="recent">Recent activity</option></select>
    </div>
    {loadError && <div className="panel p-3 border-warn-500/30 flex items-center gap-2 text-xs text-warn-300"><AlertTriangle size={14}/> {loadError}</div>}
    <div className="panel overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b border-ink-700 text-ink-400">{['Rank','Entity','Type','Priority','Investigation Score','ML Anomaly Score','Patterns','Signals','Last Activity','Action'].map((x) => <th key={x} className="px-3 py-2.5 text-left font-medium">{x}</th>)}</tr></thead><tbody>{filtered.map((lead) => <tr key={lead.entityId} className="border-b border-ink-700/50 table-row-hover"><td className="px-3 py-3 font-mono text-ink-400">{lead.rank}</td><td className="px-3 py-3 font-medium text-ink-100">{lead.entityLabel}</td><td className="px-3 py-3 capitalize text-ink-300">{lead.type}</td><td className="px-3 py-3"><PriorityBadge priority={lead.priority} /></td><td className="px-3 py-3 w-28"><ScoreBar value={lead.priorityScore} max={100} color={lead.priority === 'high' ? 'critical' : lead.priority === 'medium' ? 'warn' : 'signal'} /></td><td className="px-3 py-3 font-mono text-ink-300">{lead.mlAnomaly}</td><td className="px-3 py-3 font-mono text-ink-400">Phase 5C</td><td className="px-3 py-3">{lead.signals.slice(0,2).map((s) => <span key={s} className="mr-1 text-2xs bg-ink-700 text-ink-300 px-1.5 py-0.5 rounded">{s}</span>)}</td><td className="px-3 py-3 text-ink-400">{timeAgo(lead.lastActivity)}</td><td className="px-3 py-3"><button className="btn-ghost" onClick={() => { onOpenEntity(lead.entityId); onNavigate('entity'); }}>Review <ArrowRight size={12} /></button></td></tr>)}</tbody></table>{!filtered.length && <div className="py-10 text-center text-sm text-ink-400">No local leads match these filters.</div>}</div>
  </div>;
}
