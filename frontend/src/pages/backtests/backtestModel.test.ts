import metricsPy from '../../../../app/backtest/metrics.py?raw';
import presetsPy from '../../../../app/backtest/presets.py?raw';
import reportPy from '../../../../app/backtest/report.py?raw';

import { createI18n } from '@/i18n';

import {
  buildRequest,
  defaultPeriod,
  drawdownPoints,
  equityPoints,
  historyShortfall,
  LIMITATION_KEYS,
  METRICS,
  PRESETS,
  type RunForm,
  symbolsWithHistory,
} from './backtestModel';

const DAY = 86_400_000;
const NOW = Date.parse('2026-10-05T08:00:00Z');
const LIMITS = { maxSymbols: 5, maxDays: 366 };
const form = (over: Partial<RunForm> = {}): RunForm => ({
  preset: 'standard',
  symbols: ['EURUSD'],
  start: '2026-07-01',
  end: '2026-09-30',
  strategies: [],
  riskPercent: '',
  seed: '',
  ...over,
});

describe('parity with the backtester', () => {
  it('lists every Metrics field once', () => {
    const body = metricsPy.slice(metricsPy.indexOf('class Metrics:'), metricsPy.indexOf('def to_dict'));
    const fields = [...body.matchAll(/^ {4}([a-z_]+): /gm)].map((m) => m[1]);
    expect(fields.length).toBeGreaterThan(20);
    expect(METRICS.map(([k]) => k).sort()).toEqual([...fields].sort());
  });

  it('knows every preset', () => {
    const literal = /PresetName = Literal\[([^\]]+)\]/.exec(presetsPy)?.[1] ?? '';
    expect([...PRESETS]).toEqual([...literal.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]));
  });

  it('shows the documented limitations, in English word for word', () => {
    const block = reportPy.slice(reportPy.indexOf('LIMITATIONS = ('), reportPy.indexOf('TRADE_COLUMNS'));
    const texts = [...block.matchAll(/^ {4}"(.+)",\r?$/gm)].map((m) => m[1]);
    const en = createI18n('en');
    expect(LIMITATION_KEYS.map((k) => en.t(`backtests.limitations.${k}`))).toEqual(texts);
  });
});

describe('curves', () => {
  it('turns the stored equity into points and the drawdown from the running peak', () => {
    const points = equityPoints([
      ['2026-09-01T00:00:00+00:00', 100, 100],
      ['2026-09-01T00:00:00+00:00', 100, 110], // same second: the later value wins
      ['2026-09-01T00:15:00+00:00', 100, 99],
      ['2026-09-01T00:30:00+00:00', 100, 121],
    ]);
    expect(points.map((p) => p.value)).toEqual([110, 99, 121]);
    expect(drawdownPoints(points).map((p) => Math.round(p.value * 100) / 100)).toEqual([0, -10, 0]);
  });
});

describe('new run', () => {
  const history = {
    items: [
      {
        server: 'S',
        symbol: 'GBPUSD',
        timeframe: 'M15',
        first: '2026-01-01T00:00:00+00:00',
        last: '2026-10-05T07:45:00+00:00',
        bars: 9,
      },
      {
        server: 'S',
        symbol: 'EURUSD',
        timeframe: 'H1',
        first: '2026-01-01T00:00:00+00:00',
        last: '2026-10-05T07:00:00+00:00',
        bars: 9,
      },
      {
        server: 'S',
        symbol: 'EURUSD',
        timeframe: 'M15',
        first: '2026-08-01T00:00:00+00:00',
        last: '2026-10-05T07:45:00+00:00',
        bars: 9,
      },
    ],
  };

  it('offers the symbols with M15 history and defaults to the last 90 ended days', () => {
    const available = symbolsWithHistory(history);
    expect(available.map((s) => s.symbol)).toEqual(['EURUSD', 'GBPUSD']);
    expect(defaultPeriod(available, NOW)).toEqual({ start: '2026-07-07', end: '2026-10-04' });
    expect(defaultPeriod(available.slice(0, 1), NOW, 90)).toEqual({ start: '2026-08-01', end: '2026-10-04' });
  });

  it('builds the request body: whole UTC days, optional fields only when set', () => {
    expect(buildRequest(form(), NOW, LIMITS)).toEqual({
      body: {
        preset: 'standard',
        symbols: ['EURUSD'],
        start: '2026-07-01T00:00:00.000Z',
        end: '2026-10-01T00:00:00.000Z',
      },
    });
    const full = buildRequest(form({ strategies: ['a'], riskPercent: '0.25', seed: '7' }), NOW, LIMITS);
    expect(full).toMatchObject({ body: { strategies: ['a'], risk_percent: 0.25, seed: 7 } });
  });

  it.each([
    [{ symbols: [] }, 'symbols'],
    [{ symbols: ['A', 'B', 'C', 'D', 'E', 'F'] }, 'tooManySymbols'],
    [{ start: '2026-10-01', end: '2026-09-01' }, 'period'],
    [{ start: '2025-01-01', end: '2026-09-30' }, 'tooLong'],
    [{ end: '2026-10-05' }, 'notEnded'],
    [{ riskPercent: '-1' }, 'risk'],
    [{ seed: '1.5' }, 'seed'],
  ] as const)('refuses %o: %s', (over, problem) => {
    expect(buildRequest(form(over as Partial<RunForm>), NOW, LIMITS)).toEqual({ problem });
  });

  it('accepts a period of exactly the maximum length', () => {
    const start = '2025-09-30';
    const end = new Date(Date.parse(`${start}T00:00:00Z`) + 365 * DAY).toISOString().slice(0, 10);
    expect(buildRequest(form({ start, end }), NOW, LIMITS)).toHaveProperty('body');
  });
});

describe('history shortfall', () => {
  const eur = {
    symbol: 'EURUSD',
    server: 'FBS-Demo',
    first: '2026-09-27T23:30:00+00:00',
    last: '2026-10-05T08:30:00+00:00',
  };
  const gold = { ...eur, symbol: 'XAUUSD', first: '2025-10-05T22:00:00+00:00' };
  const form = (start: string, symbols = ['EURUSD', 'XAUUSD']): RunForm => ({
    preset: 'standard',
    symbols,
    start,
    end: '2026-10-04',
    strategies: [],
    riskPercent: '',
    seed: '',
  });

  it('names the selected symbols whose history starts after the requested start', () => {
    expect(historyShortfall(form('2026-09-25'), [eur, gold])).toEqual([eur]);
    expect(historyShortfall(form('2026-09-25', ['XAUUSD']), [eur, gold])).toEqual([]);
    expect(historyShortfall(form('2026-09-27'), [eur, gold])).toEqual([]); // within a day
    expect(historyShortfall(form(''), [eur, gold])).toEqual([]);
  });
});
