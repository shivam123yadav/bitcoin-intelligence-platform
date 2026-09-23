import { useEffect, useState } from 'react';
import {
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  Wallet,
  Globe,
  Network,
  Target,
  Activity,
  CheckCircle2,
  Cpu,
  Database,
  Share2,
} from 'lucide-react';
import { dashboardService, leadService } from '@/services';
import { PriorityBadge, ScoreBar, Sparkline } from '@/components/shared';
import { formatNumber, timeAgo } from '@/utils';
import type {
  InvestigativeLead,
  ActivityTimelinePoint,
  SystemComponent,
  PageId,
  DashboardStats,
  PriorityDistribution,
  GeoOverviewItem,
  RecentActivityItem,
} from '@/types';

interface OverviewProps {
  onNavigate: (page: PageId) => void;
  onOpenEntity: (entityId: string) => void;
}

export function OverviewPage({ onNavigate, onOpenEntity }: OverviewProps) {
  const [stats, setStats] = useState<DashboardStats>({ transactions: 0, wallets: 0, ips: 0, clusters: 0, leads: 0 });
  const [timeline, setTimeline] = useState<ActivityTimelinePoint[]>([]);
  const [priorityDist, setPriorityDist] = useState<PriorityDistribution>({ high: 0, medium: 0, low: 0 });
  const [topLeads, setTopLeads] = useState<InvestigativeLead[]>([]);
  const [geoData, setGeoData] = useState<GeoOverviewItem[]>([]);
  const [recentActivity, setRecentActivity] = useState<RecentActivityItem[]>([]);
  const [system, setSystem] = useState<SystemComponent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const [s, t, p, l, g, r, sys] = await Promise.all([
        dashboardService.getStats(),
        dashboardService.getTimeline(),
        dashboardService.getPriorityDistribution(),
        leadService.getFinalLeads(),
        dashboardService.getGeoOverview(),
        dashboardService.getRecentActivity(),
        dashboardService.getSystemReadiness(),
      ]);
      setStats(s);
      setTimeline(t);
      setPriorityDist(p);
      setTopLeads(l.leads.slice(0, 5).map((lead) => ({
        rank: lead.rank, entityId: lead.entityId, entityLabel: lead.entityLabel, type: lead.type, priority: lead.priority,
        priorityScore: lead.finalPriorityScore, mlAnomaly: lead.signalBreakdown.anomalyScore.toFixed(3), clusterId: '—',
        signals: lead.validatedPatterns.map((p) => `${p.patternType} (${p.instanceCount})`), lastActivity: lead.temporalRange.lastSeen ?? '',
      })));
      setGeoData(g);
      setRecentActivity(r);
      setSystem(sys);
      setLoading(false);
    })();
  }, []);

  const statCards = [
    { label: 'Transactions', value: stats.transactions, icon: <Activity size={18} />, color: 'text-signal-400', sparkData: timeline.map((t) => t.transactions) },
    { label: 'Wallet Entities', value: stats.wallets, icon: <Wallet size={18} />, color: 'text-intel-400', sparkData: [12, 15, 18, 22, 28, 35, 42, 48, 55, 62, 71, 78, 89, 95, 100] },
    { label: 'IP Observations', value: stats.ips, icon: <Globe size={18} />, color: 'text-warn-400', sparkData: [10, 12, 14, 18, 22, 28, 31, 35, 38, 42, 45, 48, 52, 55, 58] },
    { label: 'Entity Clusters', value: stats.clusters, icon: <Network size={18} />, color: 'text-ml-400', sparkData: [5, 8, 12, 18, 25, 35, 48, 58, 68, 75, 82, 88, 92, 96, 100] },
    { label: 'Investigative Leads', value: stats.leads, icon: <Target size={18} />, color: 'text-critical-400', sparkData: [2, 5, 8, 12, 18, 25, 32, 40, 48, 55, 62, 70, 78, 85, 92] },
  ];

  const totalLeads = priorityDist.high + priorityDist.medium + priorityDist.low;
  const activityIcons: Record<string, React.ReactNode> = {
    analysis: <Cpu size={14} className="text-intel-400" />,
    lead: <Target size={14} className="text-critical-400" />,
    cluster: <Network size={14} className="text-ml-400" />,
    pattern: <AlertTriangle size={14} className="text-warn-400" />,
    case: <Database size={14} className="text-signal-400" />,
    graph: <Share2 size={14} className="text-intel-400" />,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-6 h-6 border-2 border-signal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-ink-100 tracking-tight">Investigation Overview</h1>
        <p className="text-sm text-ink-300 mt-0.5">Bitcoin transaction and network activity analysis</p>
      </div>

      {/* Top statistics */}
      <div className="grid grid-cols-5 gap-3">
        {statCards.map((card) => (
          <div key={card.label} className="panel p-4 hover:border-ink-600 transition-colors group">
            <div className="flex items-start justify-between mb-2">
              <div className={`${card.color}`}>{card.icon}</div>
              <div className="opacity-60 group-hover:opacity-100 transition-opacity">
                <Sparkline data={card.sparkData} width={60} height={20} color={
                  card.color.includes('signal') ? '#3b82f6' :
                  card.color.includes('intel') ? '#06b6d4' :
                  card.color.includes('warn') ? '#f5a623' :
                  card.color.includes('ml') ? '#8b5cf6' :
                  '#ef4444'
                } />
              </div>
            </div>
            <div className="stat-value">{formatNumber(card.value)}</div>
            <div className="stat-label mt-1">{card.label}</div>
          </div>
        ))}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Transaction Activity Timeline */}
        <div className="panel col-span-8">
          <div className="panel-header">
            <div>
              <div className="panel-title">Transaction Activity Timeline</div>
              <div className="panel-subtitle">Daily transaction volume and anomaly count</div>
            </div>
            <div className="flex items-center gap-4 text-2xs">
              <span className="flex items-center gap-1.5 text-ink-300">
                <span className="w-2.5 h-2.5 rounded-sm bg-signal-500" /> Transactions
              </span>
              <span className="flex items-center gap-1.5 text-ink-300">
                <span className="w-2.5 h-2.5 rounded-sm bg-critical-500" /> Anomalies
              </span>
            </div>
          </div>
          <div className="p-4">
            <ActivityChart data={timeline} />
          </div>
        </div>

        {/* Priority Distribution */}
        <div className="panel col-span-4">
          <div className="panel-header">
            <div>
              <div className="panel-title">Investigation Priority Distribution</div>
              <div className="panel-subtitle">Leads by priority level</div>
            </div>
          </div>
          <div className="p-4 space-y-4">
            <PriorityRow label="High Priority" count={priorityDist.high} total={totalLeads} color="critical" />
            <PriorityRow label="Medium Priority" count={priorityDist.medium} total={totalLeads} color="warn" />
            <PriorityRow label="Low Priority" count={priorityDist.low} total={totalLeads} color="signal" />
            <div className="divider" />
            <div className="flex items-center justify-between">
              <span className="text-xs text-ink-300">Total Leads</span>
              <span className="text-lg font-semibold text-ink-100 tabular-nums">{totalLeads}</span>
            </div>
          </div>
        </div>

        {/* Top Investigative Leads */}
        <div className="panel col-span-8">
          <div className="panel-header">
            <div>
              <div className="panel-title">Top Investigative Leads</div>
              <div className="panel-subtitle">Phase 5C validated investigative leads</div>
            </div>
            <button onClick={() => onNavigate('leads')} className="btn-ghost text-xs">
              View All <ArrowRight size={12} />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ink-700 text-ink-400">
                  <th className="px-4 py-2.5 text-left font-medium">Rank</th>
                  <th className="px-4 py-2.5 text-left font-medium">Entity</th>
                  <th className="px-4 py-2.5 text-left font-medium">Type</th>
                  <th className="px-4 py-2.5 text-left font-medium">Priority</th>
                  <th className="px-4 py-2.5 text-left font-medium">ML Anomaly</th>
                  <th className="px-4 py-2.5 text-left font-medium">Cluster</th>
                  <th className="px-4 py-2.5 text-left font-medium">Signals</th>
                  <th className="px-4 py-2.5 text-left font-medium">Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {topLeads.map((lead) => (
                  <tr
                    key={lead.rank}
                    onClick={() => onOpenEntity(lead.entityId)}
                    className="border-b border-ink-700/50 table-row-hover cursor-pointer"
                  >
                    <td className="px-4 py-2.5 font-mono text-ink-400">{lead.rank}</td>
                    <td className="px-4 py-2.5 font-mono text-ink-100 font-medium">{lead.entityLabel}</td>
                    <td className="px-4 py-2.5 capitalize text-ink-300">{lead.type}</td>
                    <td className="px-4 py-2.5"><PriorityBadge priority={lead.priority} score={lead.priorityScore} /></td>
                    <td className="px-4 py-2.5 text-ink-300 font-mono text-2xs">{lead.mlAnomaly}</td>
                    <td className="px-4 py-2.5 font-mono text-ink-300">{lead.clusterId}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {lead.signals.slice(0, 2).map((s) => (
                          <span key={s} className="text-2xs text-ink-400 bg-ink-700/60 px-1.5 py-0.5 rounded">{s}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-ink-400 text-2xs">{timeAgo(lead.lastActivity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Analysis Activity */}
        <div className="panel col-span-4">
          <div className="panel-header">
            <div>
              <div className="panel-title">Recent Analysis Activity</div>
              <div className="panel-subtitle">Latest system events</div>
            </div>
          </div>
          <div className="p-2 space-y-1 max-h-80 overflow-y-auto scrollbar-thin">
            {recentActivity.map((a) => (
              <div key={a.id} className="flex items-start gap-3 px-2 py-2 rounded-md hover:bg-ink-700/40 transition-colors">
                <div className="mt-0.5">{activityIcons[a.type]}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-ink-100 font-medium leading-tight">{a.action}</div>
                  <div className="text-2xs text-ink-400 mt-0.5 truncate">{a.entity}</div>
                  <div className="text-2xs text-ink-500 mt-0.5">{a.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Geographic Overview */}
        <div className="panel col-span-7">
          <div className="panel-header">
            <div>
              <div className="panel-title">Geographic / Network Overview</div>
              <div className="panel-subtitle">Transaction distribution by country</div>
            </div>
            <Globe size={14} className="text-ink-400" />
          </div>
          <div className="p-4 space-y-3">
            {geoData.map((geo) => (
              <div key={geo.code} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-md bg-ink-800 border border-ink-700 flex items-center justify-center text-xs font-mono text-ink-300">
                  {geo.code}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-ink-100 font-medium">{geo.country}</span>
                    <span className="text-2xs text-ink-400 tabular-nums">{formatNumber(geo.transactions)} tx · {formatNumber(geo.wallets)} wallets</span>
                  </div>
                  <ScoreBar
                    value={geo.transactions}
                    max={9000}
                    color={geo.risk === 'high' ? 'critical' : geo.risk === 'medium' ? 'warn' : 'ok'}
                    showValue={false}
                    size="sm"
                  />
                </div>
                <PriorityBadge priority={geo.risk} />
              </div>
            ))}
          </div>
        </div>

        {/* System Readiness */}
        <div className="panel col-span-5">
          <div className="panel-header">
            <div>
              <div className="panel-title">System Readiness</div>
              <div className="panel-subtitle">Offline analysis components</div>
            </div>
          </div>
          <div className="p-4 space-y-3">
            {system.map((comp) => (
              <div key={comp.name} className="flex items-center gap-3 py-2 px-3 rounded-md bg-ink-800 border border-ink-700">
                <CheckCircle2 size={16} className="text-ok-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-ink-100 font-medium">{comp.name}</div>
                  <div className="text-2xs text-ink-400 mt-0.5">{comp.detail}</div>
                </div>
                <span className="text-2xs text-ink-400 font-mono">{comp.version}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PriorityRow({ label, count, total, color }: { label: string; count: number; total: number; color: 'critical' | 'warn' | 'signal' }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-ink-200 font-medium">{label}</span>
        <span className="text-xs text-ink-100 font-mono tabular-nums">{count}</span>
      </div>
      <ScoreBar value={pct} max={100} color={color} showValue={false} size="sm" />
      <div className="text-2xs text-ink-400 mt-1">{pct.toFixed(0)}% of total</div>
    </div>
  );
}

function ActivityChart({ data }: { data: ActivityTimelinePoint[] }) {
  const chartHeight = 180;
  const chartWidth = 700;
  const safeNums = (vals: unknown[]): number[] => vals.filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
  const txVals = safeNums(data.map((d) => d.transactions));
  const anomVals = safeNums(data.map((d) => d.anomalies));
  const maxTx = txVals.length ? Math.max(...txVals) : 0;
  const maxAnom = anomVals.length ? Math.max(...anomVals) : 0;
  if (!data.length) return <div className="py-10 text-center text-sm text-ink-400">No timeline data available.</div>;
  const barWidth = chartWidth / data.length;

  return (
    <div className="w-full overflow-x-auto">
      <svg width="100%" height={chartHeight + 30} viewBox={`0 0 ${chartWidth} ${chartHeight + 30}`} preserveAspectRatio="none">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <line key={p} x1={0} y1={chartHeight * p} x2={chartWidth} y2={chartHeight * p} stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
        ))}
        {/* Bars */}
        {data.map((d, i) => {
          const txNum = typeof d.transactions === 'number' && Number.isFinite(d.transactions) ? d.transactions : 0;
          const anomNum = typeof d.anomalies === 'number' && Number.isFinite(d.anomalies) ? d.anomalies : 0;
          const txHeight = maxTx > 0 ? (Math.max(0, txNum) / maxTx) * chartHeight : 0;
          const anomHeight = maxAnom > 0 ? (Math.max(0, anomNum) / maxAnom) * (chartHeight * 0.4) : 0;
          const x = i * barWidth + barWidth * 0.15;
          const w = barWidth * 0.7;
          return (
            <g key={d.label}>
              <rect
                x={x}
                y={chartHeight - txHeight}
                width={w}
                height={txHeight}
                fill="#2b6cf0"
                opacity={0.7}
                rx={2}
                className="transition-opacity hover:opacity-100"
              />
              <rect
                x={x}
                y={chartHeight - anomHeight}
                width={w * 0.4}
                height={anomHeight}
                fill="#ef4444"
                rx={1}
              />
              <text x={x + w / 2} y={chartHeight + 16} textAnchor="middle" className="fill-ink-400" style={{ fontSize: '9px' }}>
                {d.label.replace('Nov ', '')}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
