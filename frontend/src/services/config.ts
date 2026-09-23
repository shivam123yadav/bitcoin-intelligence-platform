import type { BackendHealth } from '@/types';

// Centralized API base URL — swap this when the FastAPI backend is ready.
// All services read from here so no component hardcodes an endpoint.
export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1';

// Liveness probe of the local backend. FastAPI serves it outside the /v1
// namespace as `GET /api/health`, so the version segment is stripped from the
// base URL ('/api/v1' -> '/api/health'). An absolute base such as
// 'http://127.0.0.1:8000/api/v1' keeps working for the same reason.
export const HEALTH_PATH = `${API_BASE_URL.replace(/\/v\d+$/, '')}/health`;

// Toggle: when true, services return mock data. When the FastAPI backend
// is connected, set VITE_USE_MOCK=false in .env to switch to live fetches.
export const USE_MOCK =
  (import.meta.env.VITE_USE_MOCK as string | undefined) === 'true';

// Small helper for future live calls. Not used while USE_MOCK is true,
// but kept here so the swap is a one-line change per service.
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (options?.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

// Simulate async latency so loading states are exercisable.
export function mockDelay<T>(data: T, ms = 300): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

/**
 * Probe the local backend liveness endpoint (`GET /api/health`).
 *
 * Resolves to `null` — it never throws — when the backend process is not
 * reachable, answers with a non-OK status (the Vite proxy replies 500 when the
 * FastAPI target is down) or returns a non-JSON body. Status indicators can
 * therefore treat `null` as "offline" without any error handling of their own.
 */
export async function probeBackendHealth(timeoutMs = 4000): Promise<BackendHealth | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(HEALTH_PATH, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
      cache: 'no-store',
    });
    if (!res.ok) return null;
    const payload = (await res.json()) as BackendHealth | null;
    return payload && payload.status === 'ok' ? payload : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
