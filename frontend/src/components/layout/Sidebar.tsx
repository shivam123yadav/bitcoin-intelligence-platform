import {
  LayoutDashboard,
  Database,
  Cpu,
  Target,
  UserSearch,
  Share2,
  GitBranch,
  Layers,
  FolderKanban,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import type { PageId } from '@/types';
import { useBackendStatus } from '@/hooks/useBackendStatus';

interface SidebarProps {
  active: PageId;
  onNavigate: (page: PageId) => void;
}

const navGroups: { label: string; items: { id: PageId; label: string; icon: React.ReactNode }[] }[] = [
  {
    label: 'Overview',
    items: [
      { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={16} /> },
    ],
  },
  {
    label: 'Data',
    items: [
      { id: 'dataset', label: 'Dataset', icon: <Database size={16} /> },
      { id: 'analysis', label: 'Analysis', icon: <Cpu size={16} /> },
    ],
  },
  {
    label: 'Investigation',
    items: [
      { id: 'leads', label: 'Investigative Leads', icon: <Target size={16} /> },
      { id: 'entity', label: 'Entity Investigation', icon: <UserSearch size={16} /> },
      { id: 'graph', label: 'Graph Investigation', icon: <Share2 size={16} /> },
      { id: 'transaction-flow', label: 'Transaction Flow', icon: <GitBranch size={16} /> },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { id: 'clusters', label: 'Clusters', icon: <Layers size={16} /> },
      { id: 'cases', label: 'Cases & Reports', icon: <FolderKanban size={16} /> },
      { id: 'settings', label: 'Settings', icon: <Settings size={16} /> },
    ],
  },
];

export function Sidebar({ active, onNavigate }: SidebarProps) {
  // Local backend connectivity only — this says nothing about internet access.
  const { connectivity } = useBackendStatus();
  const backendConnected = connectivity === 'connected';
  const backendOffline = connectivity === 'offline';

  return (
    <aside className="w-56 bg-ink-900 border-r border-ink-700 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-ink-700">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-gradient-to-br from-signal-500 to-intel-500 flex items-center justify-center shadow-glow-signal">
            <ShieldCheck size={18} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-ink-100 tracking-tight leading-none">Bitcoin Intelligence</div>
            <div className="text-2xs text-ink-400 mt-0.5">Transaction Monitoring</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto scrollbar-thin py-3 px-2 space-y-4">
        {navGroups.map((group) => (
          <div key={group.label}>
            <div className="px-3 mb-1.5 text-2xs font-semibold text-ink-400 uppercase tracking-wider">
              {group.label}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`nav-item w-full text-left ${active === item.id ? 'nav-item-active' : ''}`}
                >
                  <span className={active === item.id ? 'text-signal-400' : 'text-ink-400'}>
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Local backend connectivity */}
      <div className="px-3 py-3 border-t border-ink-700">
        <div className="flex items-center gap-2 px-2 py-2 rounded-md bg-ink-800 border border-ink-700">
          <div className={`w-2 h-2 rounded-full animate-pulse-soft ${backendConnected ? 'bg-ok-500' : backendOffline ? 'bg-critical-500' : 'bg-ink-500'}`} />
          <div className="flex-1">
            <div className="text-2xs font-semibold text-ink-200">
              {backendConnected ? 'Connected' : backendOffline ? 'Offline' : 'Checking'}
            </div>
            <div className="text-2xs text-ink-400">
              {backendConnected
                ? 'Local backend reachable'
                : backendOffline
                  ? 'Local backend unreachable'
                  : 'Probing local backend'}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
