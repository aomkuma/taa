import preferencesPy from '../../../../app/advisory/preferences.py?raw';
import { pyStrEnumValues } from '@/test/python';

import {
  ALERT_METRICS,
  type AlertPreferences,
  DEFAULT_THRESHOLD,
  RISK_FULL_POLICIES,
  type Watchlist,
  WATCHLIST_KINDS,
} from './schemas';
import {
  addSymbols,
  alertProblems,
  globalThreshold,
  listProblems,
  listThreshold,
  parseSymbols,
  toggleDay,
  topSymbols,
  weekdayNames,
  windowValid,
} from './watchlistModel';

const list = (overrides: Partial<Watchlist> = {}): Watchlist => ({
  name: 'Majors',
  kind: 'CUSTOM',
  symbols: [],
  top_n: null,
  alerts: true,
  threshold: null,
  ...overrides,
});

const alerts = (overrides: Partial<AlertPreferences> = {}): AlertPreferences => ({
  metric: 'WIN_PROBABILITY',
  threshold: null,
  signal_lifetime_bars: 2,
  respect_market_sessions: true,
  timezone: 'Asia/Bangkok',
  windows: [],
  rate_limits: { max_alerts_per_hour: 6, symbol_cooldown_minutes: 30 },
  expiry_updates: true,
  when_risk_full: 'PAUSE',
  language: 'th',
  ...overrides,
});

describe('backend parity', () => {
  it.each([
    ['WatchlistKind', WATCHLIST_KINDS],
    ['AlertMetric', ALERT_METRICS],
    ['RiskFullPolicy', RISK_FULL_POLICIES],
  ])('%s', (name, values) => {
    expect([...values]).toEqual(pyStrEnumValues(preferencesPy, name));
  });

  it('default thresholds', () => {
    const line = /DEFAULT_THRESHOLDS = \{([^}]*)\}/.exec(preferencesPy)?.[1] ?? '';
    const backend: Record<string, number> = Object.fromEntries(
      [...line.matchAll(/AlertMetric\.([A-Z_]+): ([\d.]+)/g)].map((m) => [m[1] ?? '', Number(m[2])]),
    );
    expect(backend).toEqual(DEFAULT_THRESHOLD);
  });
});

describe('thresholds', () => {
  it('uses the list override, else the global x, else the metric default', () => {
    expect(globalThreshold(alerts())).toBe(55);
    expect(globalThreshold(alerts({ metric: 'SETUP_STRENGTH' }))).toBe(75);
    expect(globalThreshold(alerts({ threshold: 60 }))).toBe(60);
    expect(listThreshold(list({ threshold: 70 }), alerts({ threshold: 60 }))).toBe(70);
    expect(listThreshold(list(), alerts({ threshold: 60 }))).toBe(60);
  });
});

describe('symbols', () => {
  it('takes the first N ranks, 30 by default', () => {
    const items = [3, 1, 2].map((rank) => ({ symbol: `S${String(rank)}`, rank }));
    expect(topSymbols(items, 2)).toEqual(['S1', 'S2']);
    expect(topSymbols(items, null)).toEqual(['S1', 'S2', 'S3']);
  });

  it('parses typed names and keeps the invalid ones apart', () => {
    expect(parseSymbols(' EURUSD, XAUUSD.r  BTC/USD;#US30 ')).toEqual({
      valid: ['EURUSD', 'XAUUSD.r', '#US30'],
      invalid: ['BTC/USD'],
    });
    expect(addSymbols(['EURUSD'], ['GBPUSD', 'EURUSD'])).toEqual(['EURUSD', 'GBPUSD']);
  });
});

describe('list problems', () => {
  it('checks the name, its uniqueness (any case), top N and the threshold', () => {
    expect(listProblems(list(), ['Favourites'])).toEqual([]);
    expect(listProblems(list({ name: '  ' }), [])).toEqual(['name']);
    expect(listProblems(list({ name: 'x'.repeat(41) }), [])).toEqual(['name']);
    expect(listProblems(list({ name: 'favourites' }), ['Favourites'])).toEqual(['nameTaken']);
    expect(listProblems(list({ kind: 'AUTO_TOP_N', top_n: 61 }), [])).toEqual(['topN']);
    expect(listProblems(list({ kind: 'AUTO_TOP_N', top_n: Number.NaN }), [])).toEqual(['topN']);
    expect(listProblems(list({ threshold: 101 }), [])).toEqual(['threshold']);
    expect(
      listProblems(list({ symbols: Array.from({ length: 201 }, (_, i) => `S${String(i)}`) }), []),
    ).toEqual(['tooMany']);
  });
});

describe('alert problems', () => {
  it('accepts the defaults and rejects out-of-range values', () => {
    expect(alertProblems(alerts())).toEqual([]);
    expect(
      alertProblems(
        alerts({
          threshold: -1,
          signal_lifetime_bars: 21,
          windows: [{ days: [], start: '08:00', end: '09:00' }],
          rate_limits: { max_alerts_per_hour: 0, symbol_cooldown_minutes: 1.5 },
        }),
      ),
    ).toEqual(['threshold', 'lifetime', 'windows', 'perHour', 'cooldown']);
  });

  it('validates windows', () => {
    expect(windowValid({ days: [0], start: '22:00', end: '02:00' })).toBe(true);
    expect(windowValid({ days: [0], start: '24:00', end: '02:00' })).toBe(false);
    expect(windowValid({ days: [0], start: '', end: '02:00' })).toBe(false);
    expect(toggleDay([0, 4], 2)).toEqual([0, 2, 4]);
    expect(toggleDay([0, 2, 4], 2)).toEqual([0, 4]);
  });

  it('names weekdays from Monday', () => {
    expect(weekdayNames('en-GB')).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']);
  });
});
