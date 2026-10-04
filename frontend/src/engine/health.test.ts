import { engineHealth, OFFLINE_AFTER_MS } from './health';
import type { Heartbeat } from './schemas';

const RECEIVED = Date.parse('2026-09-30T10:00:00Z');

const beat = (overrides: Partial<Heartbeat> = {}): Heartbeat => ({
  at: '2026-09-30T09:59:59+00:00',
  received_at: '2026-09-30T10:00:00+00:00',
  mode: 'PAPER',
  state: 'running',
  connected: true,
  clock_verified: true,
  kill_switch: false,
  market_open: true,
  market_change_at: null,
  ...overrides,
});

describe('engineHealth', () => {
  it('is unknown without a heartbeat', () => {
    expect(engineHealth(null, RECEIVED)).toBe('unknown');
  });

  it('is online while heartbeats are recent', () => {
    expect(engineHealth(beat(), RECEIVED + OFFLINE_AFTER_MS - 1)).toBe('online');
  });

  it('goes silent after 60 s without a heartbeat, like the watchdog', () => {
    expect(engineHealth(beat(), RECEIVED + OFFLINE_AFTER_MS)).toBe('silent');
  });

  it('reports a deliberate stop and a lost terminal connection', () => {
    expect(engineHealth(beat({ state: 'stopped' }), RECEIVED)).toBe('stopped');
    expect(engineHealth(beat({ connected: false }), RECEIVED)).toBe('disconnected');
  });
});
