import enumsPy from '../../../../app/core/enums.py?raw';

import { pyStrEnumValues } from '@/test/python';

import {
  buildChartModel,
  followRange,
  type ModelOptions,
  type ModelText,
  overlaysQuery,
  pricePrecision,
  signalEvidence,
  snapTime,
  ZONE_COLORS,
  ZONES_PER_ROLE,
  zoneStrength,
} from './model';
import { type Candles, type Evidence, TIMEFRAMES } from './schemas';

const T0 = Date.parse('2026-09-30T10:00:00Z') / 1000;
const M15 = 900;
const iso = (s: number) => new Date(s * 1000).toISOString().replace('.000Z', '+00:00');

function candles(overrides: Partial<Candles> = {}): Candles {
  const n = 6;
  return {
    server: 'FBS-Demo',
    symbol: 'EURUSD',
    timeframe: 'M15',
    bars: Array.from({ length: n }, (_, i) => [iso(T0 + i * M15), 1.1, 1.102, 1.098, 1.101, 10] as const).map(
      (b) => [...b] as Candles['bars'][number],
    ),
    overlays: {
      'ema:20': [null, 1.1, 1.1, 1.1, 1.1, 1.1],
      'ema:50': [null, null, 1.09, 1.09, 1.09, 1.09],
      'rsi:14': [50, 51, 52, 53, 54, 55],
      'adx:14': [20, 21, 22, 23, 24, 25],
    },
    markers: [],
    zones: [
      { low: 1.098, high: 1.099, touches: 4, role: 'SUPPORT' },
      { low: 1.108, high: 1.108, touches: 2, role: 'RESISTANCE' },
    ],
    ...overrides,
  };
}

const text: ModelText = {
  decision: (code) => `d:${code}`,
  support: (n) => `S${String(n)}`,
  resistance: (n) => `R${String(n)}`,
  zone: (n) => `Z${String(n)}`,
  entry: (ticket, side) => `#${String(ticket)} ${side}`,
  stopLoss: (ticket) => (ticket === null ? 'SL' : `SL #${String(ticket)}`),
  takeProfit: (ticket) => (ticket === null ? 'TP' : `TP #${String(ticket)}`),
  signalEntry: 'entry',
  target: 'target',
  invalidation: 'invalidation',
};

function options(overrides: Partial<ModelOptions> = {}): ModelOptions {
  return {
    indicators: new Set(['ema', 'rsi', 'adx']),
    zones: true,
    allDecisions: false,
    families: new Set(['HARMONIC', 'FIBONACCI']),
    timeframeSeconds: M15,
    ...overrides,
  };
}

function evidence(overrides: Partial<Evidence> = {}): Evidence {
  return {
    evidence_id: 'ev1',
    detector_id: 'harmonic.gartley',
    family: 'HARMONIC',
    name: 'Gartley',
    i18n_key: 'evidence.harmonic.gartley',
    timeframe: 'M15',
    direction: 'BULL',
    detected_at: iso(T0 + 5 * M15),
    quality: 0.8,
    // pivots stamped with their bar's close time
    key_levels: [
      { name: 'X', price: 1.095, at: iso(T0 + M15) },
      { name: 'A', price: 1.105, at: iso(T0 + 3 * M15) },
      { name: 'B', price: 1.099, at: iso(T0 + 4 * M15) },
      { name: 'prz_near', price: 1.097, at: null },
      { name: 'old', price: 1.09, at: iso(T0 - 10 * M15) }, // before the shown bars: left out
    ],
    invalidation: 1.093,
    targets: [1.104],
    ...overrides,
  };
}

const signal = (items: Evidence[]) => ({
  symbol: 'EURUSD',
  timeframe: 'M15',
  action: 'BUY',
  entry_price: 1.1,
  stop_loss: 1.095,
  take_profit: 1.11,
  evidence: items.map((e) => ({ item: { evidence: e }, relation: 'SUPPORTS' })),
});

describe('snapTime', () => {
  const times = [T0, T0 + M15, T0 + 2 * M15];

  it('puts a close stamp on the bar that closed then and an instant on the bar containing it', () => {
    expect(snapTime(times, T0 + M15, 'close', M15)).toBe(T0);
    expect(snapTime(times, T0 + M15 + 5, 'close', M15)).toBe(T0); // a decision made seconds after the close
    expect(snapTime(times, T0 + M15 + 300, 'instant', M15)).toBe(T0 + M15);
  });

  it('leaves out stamps outside the shown bars', () => {
    expect(snapTime(times, T0 - 1, 'instant', M15)).toBeNull();
    expect(snapTime(times, T0 + 3 * M15, 'instant', M15)).toBeNull();
    expect(snapTime([], T0, 'instant', M15)).toBeNull();
  });
});

describe('pricePrecision', () => {
  const bar = (...prices: number[]) =>
    ['2026-09-30T10:00:00+00:00', ...prices, 10] as Candles['bars'][number];

  it('takes the decimals the prices are quoted with', () => {
    expect(pricePrecision([bar(1.10234, 1.1025, 1.1, 1.10241)])).toBe(5);
    expect(pricePrecision([bar(2650.12, 2651.5, 2649, 2650.3)])).toBe(2);
    expect(pricePrecision([bar(18250, 18260, 18240, 18255)])).toBe(0);
    expect(pricePrecision([])).toBe(0);
  });
});

describe('overlaysQuery', () => {
  it('asks only for the chosen indicators', () => {
    expect(overlaysQuery(new Set(['rsi', 'ema']))).toBe('ema:20,ema:50,rsi:14');
    expect(overlaysQuery(new Set())).toBe('');
  });
});

describe('buildChartModel', () => {
  it('draws candles, price overlays and one pane per oscillator', () => {
    const model = buildChartModel({ candles: candles(), positions: [], signal: null }, options(), text);
    expect(model.candles).toHaveLength(6);
    expect(model.candles[0]).toEqual({ time: T0, open: 1.1, high: 1.102, low: 1.098, close: 1.101 });
    const panes = Object.fromEntries(model.lines.map((l) => [l.id, l.pane]));
    expect(panes).toEqual({ 'ema:20': 0, 'ema:50': 0, 'rsi:14': 1, 'adx:14': 2 });
    expect(model.panes).toBe(3);
    // warm-up values are gaps, not zeros
    expect(model.lines.find((l) => l.id === 'ema:50')?.points[0]).toEqual({
      time: T0 + 2 * M15,
      value: 1.09,
    });
  });

  it('ends with the forming bar, without indicator values for it', () => {
    const forming = [iso(T0 + 6 * M15), 1.101, 1.105, 1.1, 1.104, 3] as Candles['bars'][number];
    const model = buildChartModel(
      { candles: candles({ forming }), positions: [], signal: null },
      options(),
      text,
    );
    expect(model.candles).toHaveLength(7);
    expect(model.candles.at(-1)).toEqual({
      time: T0 + 6 * M15,
      open: 1.101,
      high: 1.105,
      low: 1.1,
      close: 1.104,
    });
    expect(Math.max(...(model.lines.find((l) => l.id === 'ema:20')?.points ?? []).map((p) => p.time))).toBe(
      T0 + 5 * M15,
    );
    // a forming bar that is not newer than the last closed one (a race with the next closed bar) is dropped
    const stale = [iso(T0 + 5 * M15), 1, 1, 1, 1, 1] as Candles['bars'][number];
    expect(
      buildChartModel({ candles: candles({ forming: stale }), positions: [], signal: null }, options(), text)
        .candles,
    ).toHaveLength(6);
  });

  it('marks accepted decisions and fills; rejected decisions only on request', () => {
    const c = candles({
      markers: [
        {
          kind: 'decision',
          at: iso(T0 + 2 * M15 + 3),
          decision: 'ACCEPT',
          action: 'BUY',
          strategy: 's',
          decision_id: 'd1',
          price: 1.1,
        },
        {
          kind: 'decision',
          at: iso(T0 + 3 * M15 + 3),
          decision: 'REJECT',
          action: 'SELL',
          strategy: 's',
          decision_id: 'd2',
          price: null,
        },
        {
          kind: 'entry',
          at: iso(T0 + 2 * M15 + 40),
          side: 'BUY',
          price: 1.1,
          ticket: 7,
          sl: 1.095,
          tp: 1.11,
        },
        {
          kind: 'exit',
          at: iso(T0 + 4 * M15 + 100),
          side: 'BUY',
          price: 1.105,
          ticket: 7,
          reason: 'TP',
          net: 5,
        },
      ],
    });
    const model = buildChartModel({ candles: c, positions: [], signal: null }, options(), text);
    expect(model.markers.map((m) => [m.time, m.shape, m.text])).toEqual([
      [T0 + M15, 'arrowUp', 'BUY'],
      [T0 + 2 * M15, 'arrowUp', '#7'],
      [T0 + 4 * M15, 'square', '#7 TP'],
    ]);
    const all = buildChartModel(
      { candles: c, positions: [], signal: null },
      options({ allDecisions: true }),
      text,
    );
    expect(all.markers.map((m) => m.text)).toContain('d:REJECT');
  });

  it('draws S/R zones, open positions with SL/TP and the signal plan as price lines', () => {
    const model = buildChartModel(
      {
        candles: candles(),
        positions: [
          { ticket: 7, symbol: 'EURUSD', side: 'BUY', entry_price: 1.1, sl: 1.095, tp: null },
          { ticket: 8, symbol: 'XAUUSD', side: 'SELL', entry_price: 2600, sl: 2610, tp: 2580 },
        ],
        signal: signal([]),
      },
      options(),
      text,
    );
    expect(model.priceLines.map((p) => [p.price, p.title])).toEqual([
      [1.0985, 'S4'], // one line per zone, at its middle
      [1.108, 'R2'],
      [1.1, '#7 BUY'],
      [1.095, 'SL #7'],
      [1.1, 'entry'],
      [1.095, 'SL'],
      [1.11, 'TP'],
    ]);
    const noZones = buildChartModel(
      { candles: candles(), positions: [], signal: null },
      options({ zones: false }),
      text,
    );
    expect(noZones.priceLines).toEqual([]);
  });

  it('keeps the strongest zones per role and draws them bolder the more touches they have', () => {
    const zones = [7, 6, 5, 4, 4].map((touches, i) => ({
      low: 1.11 + i / 1000,
      high: 1.1105 + i / 1000,
      touches,
      role: 'RESISTANCE' as const,
    }));
    const model = buildChartModel(
      {
        candles: candles({ zones: [...zones, { low: 1.09, high: 1.09, touches: 2, role: 'SUPPORT' }] }),
        positions: [],
        signal: null,
      },
      options(),
      text,
    );
    expect(model.priceLines.map((p) => [p.title, p.width, p.style, p.color])).toEqual([
      ['R7', 3, 'solid', ZONE_COLORS.RESISTANCE[0]],
      ['R6', 3, 'solid', ZONE_COLORS.RESISTANCE[0]],
      ['R5', 2, 'dashed', ZONE_COLORS.RESISTANCE[1]], // only ZONES_PER_ROLE resistances
      ['S2', 1, 'dotted', ZONE_COLORS.SUPPORT[2]],
    ]);
    expect(ZONES_PER_ROLE).toBe(3);
    expect([zoneStrength(6), zoneStrength(4), zoneStrength(3)]).toEqual(['strong', 'medium', 'weak']);
  });

  it('draws evidence: pattern points joined and labelled, untimed levels, targets and invalidation', () => {
    const model = buildChartModel(
      { candles: candles(), positions: [], signal: signal([evidence()]) },
      options(),
      text,
    );
    const line = model.lines.find((l) => l.id === 'evidence:ev1');
    expect(line?.points).toEqual([
      { time: T0, value: 1.095 },
      { time: T0 + 2 * M15, value: 1.105 },
      { time: T0 + 3 * M15, value: 1.099 },
    ]);
    expect(model.markers.filter((m) => m.position === 'atPriceMiddle').map((m) => m.text)).toEqual([
      'X',
      'A',
      'B',
    ]);
    expect(model.priceLines.map((p) => p.title)).toEqual(
      expect.arrayContaining(['Gartley: prz_near', 'Gartley: target', 'Gartley: invalidation']),
    );
  });

  it('hides evidence of families switched off', () => {
    const model = buildChartModel(
      { candles: candles(), positions: [], signal: signal([evidence()]) },
      options({ families: new Set(['FIBONACCI']) }),
      text,
    );
    expect(model.lines.some((l) => l.id.startsWith('evidence:'))).toBe(false);
    expect(model.priceLines.some((p) => p.title.startsWith('Gartley'))).toBe(false);
  });

  it('lists each evidence item once', () => {
    expect(signalEvidence(signal([evidence(), evidence({ quality: 0.9 })]))).toHaveLength(1);
    expect(signalEvidence(null)).toEqual([]);
  });
});

describe('timeframes', () => {
  it('match Timeframe in app/core/enums.py', () => {
    expect([...TIMEFRAMES]).toEqual(pyStrEnumValues(enumsPy, 'Timeframe'));
  });
});

describe('chart view across data updates', () => {
  it('follows the newest bar with the same width when the bar count changes', () => {
    // 300 bars, showing the last 100 with 2 bars of space; a refetch returns 280 bars (the live view had more)
    expect(followRange({ from: 201, to: 301 }, 300, 280)).toEqual({ from: 181, to: 281 });
    // a view scrolled far past the newest bar is pulled back to at most RIGHT_GAP_BARS of space
    expect(followRange({ from: 250, to: 450 }, 300, 300)).toEqual({ from: 102, to: 302 });
    // a view scrolled back into history stays put
    expect(followRange({ from: 10, to: 110 }, 300, 301)).toEqual({ from: 10, to: 110 });
  });
});
