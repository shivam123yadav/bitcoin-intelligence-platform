import { useEffect, useState } from 'react';
import {
  CheckCircle2,
  Loader2,
  AlertTriangle,
  XCircle,
  Clock,
  ArrowRight,
  Play,
  Cpu,
  Database,
  Network,
  Brain,
  Target,
  FileText,
  Share2,
} from 'lucide-react';
import { analysisService } from '@/services';
import { formatNumber, formatDuration } from '@/utils';
import type { AnalysisStage, AnalysisStageStatus, PageId } from '@/types';

interface AnalysisPageProps {
  onNavigate: (page: PageId) => void;
}

export function AnalysisPage({ onNavigate }: AnalysisPageProps) {
  const [stages, setStages] = useState<AnalysisStage[]>([]);
  const [result, setResult] = useState<{ recordsProcessed: number; entitiesAnalyzed: number; transactionsAnalyzed: number; durationMs: number; leadsGenerated: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [s, r] = await Promise.all([
          analysisService.getStages(),
          analysisService.getResult(),
        ]);
        setStages(s);
        setResult(r);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load analysis state');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleRunAnalysis() {
    if (running) return;
    setRunning(true);
    setError(null);
    // Mark stages as processing while the real backend run executes so the
    // existing progress UI is shown instead of fake simulated progress.
    setStages((prev) => prev.map((s) => ({ ...s, status: 'processing' as AnalysisStageStatus, progress: 50 })));
    try {
      const freshStages = await analysisService.runAnalysis();
      setStages(freshStages);
      // Refresh the completed result/summary from the backend after the run.
      const freshResult = await analysisService.getResult();
      setResult(freshResult);
      // Re-fetch canonical stage state as well so status/detail stay in sync.
      try {
        const canonicalStages = await analysisService.getStages();
        if (canonicalStages && canonicalStages.length) setStages(canonicalStages);
      } catch {
        // Non-fatal: runAnalysis result above is already displayed.
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis run failed');
      // Restore the last known stage state so the page does not stay stuck
      // in a fake "processing" state.
      try {
        const [s, r] = await Promise.all([
          analysisService.getStages(),
          analysisService.getResult(),
        ]);
        setStages(s);
        setResult(r);
      } catch {
        // Keep the processing->pending fallback if refresh also fails.
        setStages((prev) => prev.map((s) => (s.status === 'processing' ? { ...s, status: 'pending' as AnalysisStageStatus, progress: 0 } : s)));
      }
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-6 h-6 border-2 border-signal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const completedCount = stages.filter((s) => s.status === 'completed').length;
  const allCompleted = completedCount === stages.length;

  const stageIcons = [
    <Database size={16} />, <CheckCircle2 size={16} />, <FileText size={16} />, <Network size={16} />,
    <Cpu size={16} />, <Share2 size={16} />, <Brain size={16} />, <Target size={16} />,
    <Network size={16} />, <AlertTriangle size={16} />, <Target size={16} />, <FileText size={16} />,
  ];

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink-100 tracking-tight">AI Analysis Pipeline</h1>
          <p className="text-sm text-ink-300 mt-0.5">End-to-end transaction intelligence processing</p>
        </div>
        <button onClick={handleRunAnalysis} disabled={running} className="btn-primary">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Running…' : 'Re-run Analysis'}
        </button>
      </div>

      {error && (
        <div className="panel border-critical-500/30 bg-critical-500/10 p-4 flex items-center gap-3" role="alert">
          <XCircle size={16} className="text-critical-400 shrink-0" />
          <div>
            <div className="text-sm text-ink-100 font-medium">Analysis request failed</div>
            <div className="text-xs text-ink-300 mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* Pipeline flow visualization */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">Pipeline Stages</div>
            <div className="panel-subtitle">{completedCount} of {stages.length} stages completed</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-32 h-1.5 bg-ink-700 rounded-full overflow-hidden">
              <div className="h-full bg-ok-500 rounded-full transition-all duration-500" style={{ width: `${(completedCount / stages.length) * 100}%` }} />
            </div>
            <span className="text-2xs text-ink-300 tabular-nums">{Math.round((completedCount / stages.length) * 100)}%</span>
          </div>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-6 gap-3">
            {stages.map((stage, i) => (
              <div key={stage.id} className="relative">
                <StageCard stage={stage} icon={stageIcons[i]} />
                {i < stages.length - 1 && i % 6 !== 5 && (
                  <div className="hidden lg:block absolute top-1/2 -right-2.5 -translate-y-1/2 z-10">
                    <ArrowRight size={14} className="text-ink-500" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Completed result */}
      {allCompleted && result && (
        <div className="panel animate-slide-up">
          <div className="panel-header">
            <div>
              <div className="panel-title flex items-center gap-2">
                <CheckCircle2 size={16} className="text-ok-400" />
                Analysis Completed
              </div>
              <div className="panel-subtitle">{formatNumber(result.leadsGenerated)} investigative leads generated</div>
            </div>
          </div>
          <div className="grid grid-cols-4 gap-px bg-ink-700">
            <ResultStat icon={<Database size={16} />} label="Records Processed" value={formatNumber(result.recordsProcessed)} />
            <ResultStat icon={<Cpu size={16} />} label="Entities Analyzed" value={formatNumber(result.entitiesAnalyzed)} />
            <ResultStat icon={<Network size={16} />} label="Transactions Analyzed" value={formatNumber(result.transactionsAnalyzed)} />
            <ResultStat icon={<Clock size={16} />} label="Analysis Duration" value={formatDuration(result.durationMs)} />
          </div>
          <div className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-ok-500/10 border border-ok-500/30 flex items-center justify-center">
                <Target size={18} className="text-ok-400" />
              </div>
              <div>
                <div className="text-sm text-ink-100 font-medium">{formatNumber(result.leadsGenerated)} investigative leads ready for review</div>
                <div className="text-xs text-ink-400 mt-0.5">All 12 pipeline stages completed successfully</div>
              </div>
            </div>
            <button onClick={() => onNavigate('leads')} className="btn-primary">
              View Investigative Leads <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Stage details */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">Stage Details</div>
            <div className="panel-subtitle">Per-stage execution metrics</div>
          </div>
        </div>
        <div className="divide-y divide-ink-700">
          {stages.map((stage, i) => (
            <div key={stage.id} className="flex items-center gap-4 px-4 py-3 hover:bg-ink-700/30 transition-colors">
              <div className="w-7 h-7 rounded-md bg-ink-800 border border-ink-700 flex items-center justify-center text-ink-400 text-xs font-mono">
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-ink-100 font-medium">{stage.name}</span>
                  <StageStatusBadge status={stage.status} />
                </div>
                <div className="text-xs text-ink-400 mt-0.5">{stage.description}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-ink-200 font-mono">{stage.detail}</div>
                {stage.durationMs && (
                  <div className="text-2xs text-ink-400 font-mono mt-0.5">{formatDuration(stage.durationMs)}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StageCard({ stage, icon }: { stage: AnalysisStage; icon: React.ReactNode }) {
  const statusConfig = {
    completed: { color: 'text-ok-400', bg: 'bg-ok-500/10 border-ok-500/30', icon: <CheckCircle2 size={14} className="text-ok-400" /> },
    processing: { color: 'text-signal-400', bg: 'bg-signal-500/10 border-signal-500/30', icon: <Loader2 size={14} className="text-signal-400 animate-spin" /> },
    pending: { color: 'text-ink-400', bg: 'bg-ink-800 border-ink-700', icon: <Clock size={14} className="text-ink-400" /> },
    warning: { color: 'text-warn-400', bg: 'bg-warn-500/10 border-warn-500/30', icon: <AlertTriangle size={14} className="text-warn-400" /> },
    failed: { color: 'text-critical-400', bg: 'bg-critical-500/10 border-critical-500/30', icon: <XCircle size={14} className="text-critical-400" /> },
  };
  const cfg = statusConfig[stage.status];

  return (
    <div className={`rounded-lg border p-3 transition-all ${cfg.bg}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-ink-300">{icon}</span>
        {cfg.icon}
      </div>
      <div className="text-xs font-medium text-ink-100 leading-tight">{stage.name}</div>
      <div className="text-2xs text-ink-400 mt-1 leading-tight line-clamp-2">{stage.description}</div>
      {stage.status === 'completed' && stage.detail && (
        <div className="text-2xs text-ink-300 mt-2 font-mono truncate">{stage.detail}</div>
      )}
      {stage.status === 'processing' && (
        <div className="w-full h-1 bg-ink-700 rounded-full overflow-hidden mt-2">
          <div className="h-full bg-signal-500 rounded-full animate-pulse-soft" style={{ width: `${stage.progress || 50}%` }} />
        </div>
      )}
    </div>
  );
}

function StageStatusBadge({ status }: { status: AnalysisStageStatus }) {
  const config = {
    completed: { label: 'Completed', cls: 'badge-ok' },
    processing: { label: 'Processing', cls: 'badge-intel' },
    pending: { label: 'Pending', cls: 'badge-neutral' },
    warning: { label: 'Warning', cls: 'badge-medium' },
    failed: { label: 'Failed', cls: 'badge-high' },
  };
  const cfg = config[status];
  return <span className={cfg.cls}>{cfg.label}</span>;
}

function ResultStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-ink-850 p-4">
      <div className="text-ink-400 mb-2">{icon}</div>
      <div className="text-lg font-semibold text-ink-100 tabular-nums">{value}</div>
      <div className="text-2xs text-ink-400 mt-0.5">{label}</div>
    </div>
  );
}
