import type { Priority } from '@/types';

interface PriorityBadgeProps {
  priority: Priority;
  score?: number;
}

export function PriorityBadge({ priority, score }: PriorityBadgeProps) {
  const cls =
    priority === 'high' ? 'badge-high' :
    priority === 'medium' ? 'badge-medium' :
    'badge-low';
  const label = priority.toUpperCase();
  return (
    <span className={cls}>
      {label}
      {score !== undefined && <span className="opacity-70 ml-1">{score}</span>}
    </span>
  );
}

interface StatusBadgeProps {
  status: string;
  variant?: 'ok' | 'warn' | 'critical' | 'intel' | 'ml' | 'neutral';
}

export function StatusBadge({ status, variant = 'neutral' }: StatusBadgeProps) {
  const cls =
    variant === 'ok' ? 'badge-ok' :
    variant === 'warn' ? 'badge-medium' :
    variant === 'critical' ? 'badge-high' :
    variant === 'intel' ? 'badge-intel' :
    variant === 'ml' ? 'badge-ml' :
    'badge-neutral';
  return <span className={cls}>{status}</span>;
}

interface ScoreBarProps {
  value: number; // 0-1 or 0-100
  max?: number;
  label?: string;
  color?: 'signal' | 'critical' | 'warn' | 'ok' | 'ml' | 'intel';
  showValue?: boolean;
  size?: 'sm' | 'md';
}

export function ScoreBar({ value, max = 1, label, color = 'signal', showValue = true, size = 'md' }: ScoreBarProps) {
  const rawPct = typeof value === 'number' && typeof max === 'number' && Number.isFinite(value) && Number.isFinite(max) && max !== 0 ? (value / max) * 100 : 0;
  const pct = Math.min(100, Math.max(0, rawPct));
  const colorClass =
    color === 'critical' ? 'bg-critical-500' :
    color === 'warn' ? 'bg-warn-500' :
    color === 'ok' ? 'bg-ok-500' :
    color === 'ml' ? 'bg-ml-500' :
    color === 'intel' ? 'bg-intel-500' :
    'bg-signal-500';
  const height = size === 'sm' ? 'h-1' : 'h-1.5';
  return (
    <div className="w-full">
      {label && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-2xs text-ink-300 font-medium">{label}</span>
          {showValue && (
            <span className="text-2xs text-ink-200 font-mono tabular-nums">
              {value <= 1 ? value.toFixed(2) : value.toFixed(0)}
            </span>
          )}
        </div>
      )}
      <div className={`w-full ${height} bg-ink-700 rounded-full overflow-hidden`}>
        <div
          className={`${height} ${colorClass} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  width?: number;
}

export function Sparkline({ data, color = '#3b82f6', height = 32, width = 120 }: SparklineProps) {
  if (data.length === 0) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data
    .map((d, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((d - min) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');
  const areaPoints = `0,${height} ${points} ${width},${height}`;
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polygon points={areaPoints} fill={color} opacity={0.1} />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface TooltipProps {
  content: string;
  children: React.ReactNode;
}

export function Tooltip({ content, children }: TooltipProps) {
  return (
    <span className="relative group inline-flex">
      {children}
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 text-2xs bg-ink-700 text-ink-100 rounded border border-ink-600 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-150 z-50 shadow-panel-lg">
        {content}
      </span>
    </span>
  );
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
}

export function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      {icon && <div className="text-ink-400 mb-3">{icon}</div>}
      <p className="text-sm font-medium text-ink-200">{title}</p>
      {description && <p className="text-xs text-ink-400 mt-1 max-w-xs">{description}</p>}
    </div>
  );
}

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = 'Loading…' }: LoadingStateProps) {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="flex items-center gap-3 text-ink-300">
        <div className="w-4 h-4 border-2 border-signal-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">{label}</span>
      </div>
    </div>
  );
}
