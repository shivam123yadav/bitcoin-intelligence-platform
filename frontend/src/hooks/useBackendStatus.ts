import { useEffect, useState } from 'react';
import { analysisService, dashboardService, healthService } from '@/services';
import type { BackendConnectivity, BackendHealth } from '@/types';

/**
 * Shared local-backend status store.
 *
 * More than one component shows backend state (the header badge and the sidebar
 * footer, plus the header analysis pill), and they must never disagree. The
 * probe results therefore live in this module instead of inside each component.
 *
 * Exactly one poller exists no matter how many components subscribe, it starts
 * on the first subscriber, stops when the last one unsubscribes, and it only
 * asks for the cheap liveness endpoint on its interval — nothing is polled
 * aggressively. All failures are converted into an `offline` state here so a
 * dead backend can never reject into React and break rendering.
 */

/** Probe interval. One `GET /api/health` every 15 seconds. */
export const BACKEND_STATUS_REFRESH_MS = 15000;

export interface BackendStatusSnapshot {
  /** Reachability of the local backend process. */
  connectivity: BackendConnectivity;
  /** Last successful `GET /api/health` payload, null when offline. */
  health: BackendHealth | null;
  /** Lead count from `GET /api/v1/dashboard/stats`, null until it is known. */
  leads: number | null;
  /** Run status from `GET /api/v1/analysis/status`, null until it is known. */
  analysisStatus: string | null;
}

const initialSnapshot: BackendStatusSnapshot = {
  connectivity: 'checking',
  health: null,
  leads: null,
  analysisStatus: null,
};

let snapshot: BackendStatusSnapshot = initialSnapshot;
const listeners = new Set<(snapshot: BackendStatusSnapshot) => void>();
let pollTimer: number | null = null;
let probeInFlight = false;

/** Current status without subscribing (also used as the hook's initial state). */
export function readBackendStatus(): BackendStatusSnapshot {
  return snapshot;
}

/** Subscribe to status changes. Starts the shared poller on first subscriber. */
export function subscribeBackendStatus(
  listener: (snapshot: BackendStatusSnapshot) => void,
): () => void {
  listeners.add(listener);
  ensurePolling();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) stopPolling();
  };
}

function sameStatus(a: BackendStatusSnapshot, b: BackendStatusSnapshot): boolean {
  return (
    a.connectivity === b.connectivity &&
    a.leads === b.leads &&
    a.analysisStatus === b.analysisStatus &&
    a.health?.status === b.health?.status &&
    a.health?.service === b.health?.service &&
    a.health?.version === b.health?.version
  );
}

/** `GET /api/health`. Returns null instead of throwing when unreachable. */
async function fetchConnectivity(): Promise<BackendHealth | null> {
  try {
    return await healthService.getHealth();
  } catch {
    return null;
  }
}

/** `GET /api/v1/analysis/status`. Cheap: it reads the cached run state only. */
async function fetchAnalysisStatus(): Promise<string | null> {
  try {
    const status = await analysisService.getStatus();
    return typeof status?.status === 'string' ? status.status : null;
  } catch {
    return null;
  }
}

/**
 * Probe the backend once and update connectivity.
 *
 * Called on startup and on the refresh interval. Concurrent calls collapse into
 * the in-flight probe. Never throws.
 */
export async function refreshConnectivity(): Promise<BackendStatusSnapshot> {
  if (probeInFlight) return snapshot;
  probeInFlight = true;
  const wasConnected = snapshot.connectivity === 'connected';
  try {
    const health = await fetchConnectivity();
    if (!health) {
      // Unreachable, or answered with a non-OK / non-JSON response.
      publish({ connectivity: 'offline', health: null, analysisStatus: null });
      return snapshot;
    }
    publish({ connectivity: 'connected', health });
    await refreshAnalysisStatus();
    // The lead count is re-read when the backend (re)connects and whenever the
    // analysis run status changes, which is the only time leads can change.
    if (!wasConnected) await refreshLeadCount();
  } catch {
    publish({ connectivity: 'offline', health: null, analysisStatus: null });
  } finally {
    probeInFlight = false;
  }
  return snapshot;
}

/** Read the analysis run status; re-reads the lead count if it changed. */
export async function refreshAnalysisStatus(): Promise<void> {
  const previous = snapshot.analysisStatus;
  const current = await fetchAnalysisStatus();
  publish({ analysisStatus: current });
  if (current !== previous) await refreshLeadCount();
}

/** Read the real lead count. Failures degrade to "unknown" instead of throwing. */
export async function refreshLeadCount(): Promise<void> {
  try {
    const stats = await dashboardService.getStats();
    publish({ leads: typeof stats?.leads === 'number' ? stats.leads : null });
  } catch {
    publish({ leads: null });
  }
}

function ensurePolling(): void {
  if (pollTimer !== null) return;
  void refreshConnectivity();
  if (typeof window === 'undefined') return; // SSR / tests: no timers
  pollTimer = window.setInterval(() => {
    void refreshConnectivity();
  }, BACKEND_STATUS_REFRESH_MS);
}

function stopPolling(): void {
  if (pollTimer === null) return;
  if (typeof window !== 'undefined') window.clearInterval(pollTimer);
  pollTimer = null;
}

/**
 * Live local-backend status for status indicators. Never throws and never
 * rejects; an unreachable backend simply yields `connectivity: 'offline'`.
 */
export function useBackendStatus(): BackendStatusSnapshot {
  const [current, setCurrent] = useState<BackendStatusSnapshot>(readBackendStatus);
  useEffect(() => {
    setCurrent(readBackendStatus());
    return subscribeBackendStatus(setCurrent);
  }, []);
  return current;
}

/** Merge a patch in and notify subscribers only when something really changed. */
function publish(patch: Partial<BackendStatusSnapshot>): void {
  const next: BackendStatusSnapshot = { ...snapshot, ...patch };
  if (sameStatus(next, snapshot)) return;
  snapshot = next;
  listeners.forEach((listener) => listener(snapshot));
}
