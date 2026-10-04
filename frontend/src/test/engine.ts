/** Engine fixtures for page tests: heartbeat and status payloads, an owner's API, the app with a fake stream. */
import { type Handler, json, makeSession, mockApi } from '@/test/api';
import { fakeEventSources } from '@/test/eventSource';
import { renderApp } from '@/test/render';

export const iso = (ms: number) => new Date(ms).toISOString().replace('Z', '+00:00');

export function heartbeat(overrides: Record<string, unknown> = {}) {
  const now = Date.now();
  return {
    at: iso(now - 1_000),
    received_at: iso(now),
    run_id: 'r1',
    mode: 'PAPER',
    state: 'running',
    connected: true,
    clock_verified: true,
    kill_switch: false,
    open_positions: 0,
    cycles: 3,
    market_open: true,
    market_change_at: null,
    ...overrides,
  };
}

export function status(engineId: string, overrides: Record<string, unknown> = {}) {
  return {
    engine: { engine_id: engineId, label: `${engineId} pc`, status: 'ACTIVE', last_seen_at: null },
    run: { run_id: 'r1', mode: 'PAPER', status: 'RUNNING', started_at: iso(Date.now() - 60_000) },
    last_received_at: null,
    kill_switch: { active: false, last: null },
    open_breakers: 0,
    open_positions: 0,
    audit: null,
    heartbeat: heartbeat(),
    ...overrides,
  };
}

export const engine = (engine_id: string, status_ = 'ACTIVE') => ({
  engine_id,
  label: `${engine_id} pc`,
  status: status_,
  last_seen_at: null,
});

export function owner(extra: Record<string, Handler> = {}) {
  return mockApi({
    'GET /auth/session': () => json(makeSession()),
    'GET /me/feed': () => json({ engine_id: 'e1', own: true }),
    'GET /engines': () => json({ items: [engine('e1')] }),
    'GET /engines/e1/status': () => json(status('e1')),
    ...extra,
  });
}

export function renderShell(path = '/', language: 'th' | 'en' = 'en') {
  const sources = fakeEventSources();
  const result = renderApp(path, language, { createEventSource: sources.factory });
  return { ...result, sources };
}
