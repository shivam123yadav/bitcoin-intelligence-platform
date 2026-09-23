import { useState, useEffect, useRef } from 'react';
import { Search, Bell, Wifi, WifiOff, FileText, User, ChevronDown, X } from 'lucide-react';
import { searchService, datasetService } from '@/services';
import { useBackendStatus } from '@/hooks/useBackendStatus';
import { formatNumber } from '@/utils';
import type { PageId, SearchResult } from '@/types';
import { PriorityBadge } from '@/components/shared';

interface HeaderProps {
  onNavigate: (route: PageId) => void;
  onSearchResult: (result: SearchResult) => void;
}

export function Header({ onNavigate, onSearchResult }: HeaderProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const [datasetName, setDatasetName] = useState('');

  // Live local-backend status. Every status label below is derived from these
  // values — never from hardcoded text — and the probe never throws, so an
  // unreachable backend degrades to the offline state instead of an error.
  const { connectivity, leads, analysisStatus } = useBackendStatus();
  const backendConnected = connectivity === 'connected';
  const backendOffline = connectivity === 'offline';

  const ConnectivityIcon = backendOffline ? WifiOff : Wifi;
  const connectivityLabel = backendConnected ? 'Connected' : backendOffline ? 'Offline' : 'Checking';
  const connectivityTone = backendConnected
    ? 'bg-ok-500/10 border-ok-500/30 text-ok-400'
    : backendOffline
      ? 'bg-critical-500/10 border-critical-500/30 text-critical-400'
      : 'bg-ink-800 border-ink-700 text-ink-400';

  const analysisDot = !backendConnected
    ? 'bg-ink-500'
    : analysisStatus === 'completed'
      ? 'bg-ok-500'
      : analysisStatus === 'not_run'
        ? 'bg-warn-500'
        : 'bg-ink-500';
  const analysisLabel = !backendConnected
    ? (backendOffline ? 'Analysis Unavailable' : 'Checking Analysis')
    : analysisStatus === 'completed'
      ? 'Analysis Complete'
      : analysisStatus === 'not_run'
        ? 'Analysis Not Run'
        : 'Analysis Status Unknown';
  const leadCountLabel =
    backendConnected && leads !== null ? `${formatNumber(leads)} leads` : '— leads';

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setShowResults(false);
      return;
    }
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const r = await searchService.search(query);
        setResults(r);
        setShowResults(true);
      } catch {
        // Backend unreachable: a failed search must never break the header.
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowResults(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Dataset filename from the existing dataset metadata service
  // (GET /api/v1/dataset/meta) instead of a hardcoded string. Any failure
  // degrades to the '—' placeholder so the header can never break rendering.
  useEffect(() => {
    let active = true;
    datasetService
      .getMeta()
      .then((meta) => {
        if (active) setDatasetName(meta.filename);
      })
      .catch(() => {
        // Backend unreachable or invalid payload: keep the placeholder.
      });
    return () => {
      active = false;
    };
  }, []);

  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    (acc[r.type] = acc[r.type] || []).push(r);
    return acc;
  }, {});

  const typeLabels: Record<string, string> = {
    wallet: 'Wallets',
    transaction: 'Transactions',
    ip: 'IP Addresses',
    cluster: 'Clusters',
  };

  function handleResultClick(r: SearchResult) {
    onSearchResult(r);
    setQuery('');
    setShowResults(false);
  }

  return (
    <header className="h-14 bg-ink-900 border-b border-ink-700 flex items-center px-4 gap-4 sticky top-0 z-40">
      {/* Dataset indicator */}
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-ink-800 border border-ink-700">
        <FileText size={14} className="text-ink-400" />
        <div className="flex flex-col">
          <span className="text-2xs text-ink-400 leading-none">Current Dataset</span>
          <span className="text-xs text-ink-100 font-medium leading-none mt-0.5">{datasetName || '—'}</span>
        </div>
      </div>

      {/* Analysis status — live lead count from GET /api/v1/dashboard/stats */}
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-ink-800 border border-ink-700">
        <div className={`w-2 h-2 rounded-full ${analysisDot}`} />
        <span className="text-xs text-ink-200">{analysisLabel}</span>
        <span className="text-2xs text-ink-400">· {leadCountLabel}</span>
      </div>

      {/* Local backend connectivity — live probe of GET /api/health */}
      <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border ${connectivityTone}`}>
        <ConnectivityIcon size={14} />
        <span className="text-xs font-medium">{connectivityLabel}</span>
      </div>

      {/* Search */}
      <div ref={searchRef} className="flex-1 max-w-md relative">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => results.length > 0 && setShowResults(true)}
            placeholder="Search wallet, TXID, IP, cluster…"
            className="input w-full pl-9 pr-8 text-xs"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); setShowResults(false); }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-200"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Search results dropdown */}
        {showResults && (
          <div className="absolute top-full mt-2 left-0 right-0 bg-ink-850 border border-ink-600 rounded-lg shadow-panel-lg overflow-hidden animate-slide-up z-50">
            {loading && (
              <div className="px-4 py-3 text-xs text-ink-400 flex items-center gap-2">
                <div className="w-3 h-3 border-2 border-signal-500 border-t-transparent rounded-full animate-spin" />
                Searching…
              </div>
            )}
            {!loading && results.length === 0 && query.trim() && (
              <div className="px-4 py-6 text-center text-xs text-ink-400">
                No results for "{query}"
              </div>
            )}
            {!loading && results.length > 0 && (
              <div className="max-h-96 overflow-y-auto scrollbar-thin">
                {Object.entries(grouped).map(([type, items]) => (
                  <div key={type}>
                    <div className="px-3 py-1.5 bg-ink-800 text-2xs font-semibold text-ink-400 uppercase tracking-wider border-b border-ink-700">
                      {typeLabels[type] || type}
                    </div>
                    {items.map((r) => (
                      <button
                        key={r.id}
                        onClick={() => handleResultClick(r)}
                        className="w-full px-3 py-2 flex items-center justify-between hover:bg-ink-700/50 transition-colors text-left group"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="font-mono text-xs text-ink-100 group-hover:text-signal-400 transition-colors">
                            {r.label}
                          </span>
                          <span className="text-2xs text-ink-400 truncate">{r.description}</span>
                        </div>
                        {r.priority && <PriorityBadge priority={r.priority} />}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Notifications */}
      <div className="relative">
        <button
          onClick={() => setNotifOpen(!notifOpen)}
          className="btn-ghost relative"
        >
          <Bell size={16} />
          <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-critical-500" />
        </button>
        {notifOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setNotifOpen(false)} />
            <div className="absolute right-0 top-full mt-2 w-80 bg-ink-850 border border-ink-600 rounded-lg shadow-panel-lg overflow-hidden z-50 animate-slide-up">
              <div className="px-4 py-3 border-b border-ink-700 flex items-center justify-between">
                <span className="text-sm font-semibold text-ink-100">Notifications</span>
                <span className="badge-high">3 new</span>
              </div>
              <div className="divide-y divide-ink-700">
                {[
                  { title: 'New investigative lead', desc: backendConnected && leads !== null ? `${formatNumber(leads)} leads flagged for review` : 'Lead notifications unavailable', time: '5m ago', priority: 'high' as const },
                  { title: 'Pattern detected', desc: 'Peeling-chain candidate in cluster C-07', time: '18m ago', priority: 'medium' as const },
                  { title: 'Analysis complete', desc: backendConnected && leads !== null ? `${formatNumber(leads)} leads generated from the current analysis` : 'Lead count unavailable', time: '2m ago', priority: 'low' as const },
                ].map((n, i) => (
                  <div key={i} className="px-4 py-3 hover:bg-ink-700/40 cursor-pointer transition-colors">
                    <div className="flex items-start gap-2">
                      <PriorityBadge priority={n.priority} />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-ink-100">{n.title}</div>
                        <div className="text-2xs text-ink-400 mt-0.5">{n.desc}</div>
                        <div className="text-2xs text-ink-500 mt-1">{n.time}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Investigator profile */}
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-ink-800 border border-ink-700 hover:bg-ink-700 cursor-pointer transition-colors">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-signal-500 to-intel-500 flex items-center justify-center">
          <User size={14} className="text-white" />
        </div>
        <div className="flex flex-col">
          <span className="text-xs text-ink-100 font-medium leading-none">Analyst-01</span>
          <span className="text-2xs text-ink-400 leading-none mt-0.5">Senior Investigator</span>
        </div>
        <ChevronDown size={14} className="text-ink-400" />
      </div>
    </header>
  );
}
