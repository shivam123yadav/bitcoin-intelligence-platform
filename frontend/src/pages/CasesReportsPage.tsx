import { useEffect, useState } from 'react';
import { Download, Plus } from 'lucide-react';
import { caseService, leadService } from '@/services';
import { PriorityBadge, StatusBadge } from '@/components/shared';
import { formatDate } from '@/utils';
import type { CaseRecord } from '@/types';

export function CasesReportsPage() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [selected, setSelected] = useState<CaseRecord>();
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const refresh = async () => {
    const items = await caseService.getCases();
    setCases(items);
    setSelected((current) => items.find((x) => x.id === current?.id) ?? items[0]);
  };

  useEffect(() => { refresh().catch(() => setMessage('Unable to load cases.')); }, []);

  const createCase = async () => {
    setBusy(true); setMessage('');
    try {
      const leads = await leadService.getFinalLeads();
      const lead = leads.leads[0];
      if (!lead) { setMessage('No investigative lead is available to create a case.'); return; }
      const created = await caseService.createCase({
        primaryEntity: lead.entityId,
        primaryEntityLabel: lead.entityLabel,
        priority: lead.priority,
        priorityScore: lead.finalPriorityScore,
        status: 'open',
        analyst: 'Analyst-01',
        summary: `Analyst-created case from investigative lead ${lead.leadId}. ${lead.explanation}`,
        evidenceIds: [],
        patternIds: lead.validatedPatternInstances.map((p) => p.patternId).slice(0, 20),
        relatedEntities: [lead.entityId, ...(lead.supportingEntities.wallets ?? []).slice(0, 9)],
        modelFindings: [],
      });
      await refresh();
      setSelected(created);
      setMessage(`Created ${created.id}.`);
    } catch { setMessage('Case creation failed.'); }
    finally { setBusy(false); }
  };

  const addEvidence = async () => {
    if (!selected) { setMessage('Create or select a case first.'); return; }
    setBusy(true); setMessage('');
    try {
      const evidenceId = `EV-LOCAL-${Date.now()}`;
      const updated = await caseService.addEvidence(selected.id, evidenceId);
      await refresh(); setSelected(updated); setMessage(`Added ${evidenceId}.`);
    } catch { setMessage('Evidence update failed.'); }
    finally { setBusy(false); }
  };

  const saveNote = async () => {
    if (!selected || !note.trim()) return;
    setBusy(true); setMessage('');
    try {
      const updated = await caseService.addNote(selected.id, note.trim());
      setNote(''); await refresh(); setSelected(updated); setMessage('Analyst note saved.');
    } catch { setMessage('Note could not be saved.'); }
    finally { setBusy(false); }
  };

  const open = cases.filter((item) => item.status !== 'closed').length;
  const caseStatus = (status: CaseRecord['status']) => status.replace(/_/g, ' ');
  return <div className="space-y-4 animate-fade-in">
    <div className="flex justify-between"><div><h1 className="text-xl font-semibold text-ink-100">Cases & Reports</h1><p className="text-sm text-ink-300 mt-0.5">Local analyst case workspace based on investigative leads and observed evidence.</p></div><div className="flex gap-2"><button className="btn-secondary" disabled={busy || !selected} onClick={addEvidence}>Add Evidence</button><button className="btn-secondary" onClick={() => window.print()}><Download size={14} /> Export Report</button><button className="btn-primary" disabled={busy} onClick={createCase}><Plus size={14} /> Create Case</button></div></div>
    {message && <div className="panel px-3 py-2 text-xs text-ink-300">{message}</div>}
    <div className="grid grid-cols-4 gap-3">{[['Open cases', open], ['Closed cases', cases.length - open], ['Draft reports', cases.filter((item) => item.status === 'pending_approval').length], ['Recent reports', cases.filter((item) => item.status === 'closed').length]].map(([label, value]) => <div className="panel p-4" key={label as string}><div className="text-lg font-semibold text-signal-400">{value}</div><div className="stat-label mt-1">{label}</div></div>)}</div>
    <div className="grid grid-cols-12 gap-4"><div className="panel col-span-8 overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b border-ink-700 text-ink-400">{['Case ID', 'Title / primary entity', 'Priority', 'Entities', 'Created', 'Updated', 'Status'].map((label) => <th key={label} className="px-3 py-2.5 text-left">{label}</th>)}</tr></thead><tbody>{cases.map((item) => <tr key={item.id} onClick={() => setSelected(item)} className={`cursor-pointer border-b border-ink-700/50 table-row-hover ${selected?.id === item.id ? 'bg-signal-500/10' : ''}`}><td className="px-3 py-3 font-mono text-signal-400">{item.id}</td><td className="px-3 py-3 text-ink-100">{item.primaryEntityLabel}</td><td className="px-3 py-3"><PriorityBadge priority={item.priority} /></td><td className="px-3 py-3 text-ink-300">{item.relatedEntities.length}</td><td className="px-3 py-3 text-ink-400">{formatDate(item.created)}</td><td className="px-3 py-3 text-ink-400">{formatDate(item.updated)}</td><td className="px-3 py-3"><StatusBadge status={caseStatus(item.status)} variant={item.status === 'closed' ? 'ok' : item.status === 'under_review' ? 'intel' : 'warn'} /></td></tr>)}</tbody></table>{cases.length===0&&<div className="p-8 text-center text-sm text-ink-400">No analyst cases yet. Create one from the current investigative lead queue.</div>}</div>
      <aside className="panel col-span-4"><div className="panel-header"><div className="panel-title">Case detail</div></div>{selected ? <div className="p-4 space-y-4"><div><div className="font-mono text-sm text-ink-100">{selected.id}</div><p className="text-xs text-ink-300 mt-1">{selected.summary}</p></div><div><div className="text-2xs uppercase text-ink-400 mb-1">Linked entities</div>{selected.relatedEntities.map((id) => <div key={id} className="font-mono text-xs text-signal-400 py-0.5">{id}</div>)}</div><div><div className="text-2xs uppercase text-ink-400 mb-1">Evidence</div>{selected.evidenceIds.map((id) => <div key={id} className="text-xs text-ink-300 py-0.5">{id}</div>)}</div><textarea className="input h-20 w-full" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Analyst notes…" /><button className="btn-secondary w-full" disabled={busy || !note.trim()} onClick={saveNote}>Save Note</button>{selected.notes?.length ? <div><div className="text-2xs uppercase text-ink-400 mb-1">Saved notes</div>{selected.notes.slice().reverse().map((n,i)=><div key={`${n.created}-${i}`} className="text-xs text-ink-300 border-b border-ink-700/50 py-2">{n.text}</div>)}</div> : null}<div className="text-2xs text-ink-400">Timeline: created {formatDate(selected.created)} · updated {formatDate(selected.updated)}</div></div> : <div className="p-6 text-sm text-ink-400">Select a case or create one from the lead queue.</div>}</aside>
    </div>
  </div>;
}
