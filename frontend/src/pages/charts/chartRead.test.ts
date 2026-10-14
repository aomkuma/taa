import chartReadPy from '../../../../app/indicators/chart_read.py?raw';
import priceActionPy from '../../../../app/indicators/price_action.py?raw';

import en from '@/i18n/locales/en/common.json';
import th from '@/i18n/locales/th/common.json';
import fixture from '@/test/fixtures/chart-read-xauusd-h1.json';
import samples from '@/test/fixtures/api-samples.json';
import { pyStrEnumValues } from '@/test/python';

import { buildChartModel, type ModelOptions, type ModelText, READ_COLORS, readDrawing } from './model';
import {
  type Candles,
  ChartReadSchema,
  LEVEL_ROLES,
  MarketMapSchema,
  READ_EVENTS,
  STRUCTURES,
  SWING_LABELS,
} from './schemas';

const sorted = (values: Iterable<string>) => [...new Set(values)].sort();
// a real read: XAUUSD H1 at 2026-10-02 18:00 UTC with its 300 bars (app/indicators/chart_read.py, FBS-Demo)
const READ = ChartReadSchema.parse(fixture.read);
const H1 = 3600;
const times = fixture.bars.map((b) => Math.floor(Date.parse(b[0] as string) / 1000));

const text: ModelText = {
  decision: (code) => code,
  support: (n) => `S${String(n)}`,
  resistance: (n) => `R${String(n)}`,
  zone: (n) => `Z${String(n)}`,
  entry: (ticket) => `#${String(ticket)}`,
  stopLoss: () => 'SL',
  takeProfit: () => 'TP',
  signalEntry: 'Signal',
  target: 'Target',
  invalidation: 'Invalidation',
  swingLabel: (label) => `<${label}>`,
  readLevel: (role, above, n) => `${role}${above ? '^' : 'v'}${String(n)}`,
  readInvalidation: (structure) => `ends:${structure}`,
};

describe('chart read: backend parity', () => {
  it('knows every structure, role, event and swing label of the backend', () => {
    expect(sorted(STRUCTURES)).toEqual(sorted(pyStrEnumValues(chartReadPy, 'Structure')));
    expect(sorted(LEVEL_ROLES)).toEqual(sorted(pyStrEnumValues(chartReadPy, 'LevelRole')));
    expect(sorted(READ_EVENTS)).toEqual(sorted(pyStrEnumValues(chartReadPy, 'EventKind')));
    expect(sorted(SWING_LABELS)).toEqual(sorted(pyStrEnumValues(priceActionPy, 'StructureLabel')));
    expect(sorted(pyStrEnumValues(chartReadPy, 'ScenarioKind'))).toEqual(['BREAK', 'REJECT']);
  });

  it('names each of them in both languages', () => {
    for (const catalog of [en, th]) {
      const read = catalog.charts.read;
      expect(sorted(Object.keys(read.structures))).toEqual(sorted(STRUCTURES));
      expect(sorted(Object.keys(read.event))).toEqual(sorted(READ_EVENTS));
      expect(sorted(Object.keys(read.label))).toEqual(sorted(SWING_LABELS));
      expect(sorted(Object.keys(read.scenario))).toEqual([
        'BREAK_down',
        'BREAK_up',
        'REJECT_down',
        'REJECT_up',
      ]);
      for (const role of ['SUPPORT', 'RESISTANCE', 'SPENT', 'flippedSupport', 'flippedResistance'])
        expect(read.level).toHaveProperty(role);
    }
  });

  it('parses the API sample of a map with a read', () => {
    const sample = (samples as Record<string, unknown>)[
      'engines/ENGINE/market-map?symbol=EURUSD&read_tf=M15'
    ];
    const parsed = MarketMapSchema.parse(sample);
    expect(parsed.read?.timeframe).toBe('M15');
  });
});

describe('chart read: drawing', () => {
  it('joins the confirmed swings and labels each one', () => {
    const { lines, markers } = readDrawing(READ, times, H1, text);
    const swings = lines.find((l) => l.id === 'read:swings');
    expect(swings?.points).toHaveLength(READ.pivots.length);
    expect(swings?.color).toBe(READ_COLORS.swing);
    const labelled = READ.pivots.filter((p) => p.label !== null).map((p) => `<${p.label ?? ''}>`);
    expect(markers.map((m) => m.text).filter((s) => s !== '')).toEqual(labelled);
    const high = READ.pivots.findIndex((p) => p.kind === 'HIGH');
    expect(markers[high]?.position).toBe('aboveBar');
  });

  it('draws each trendline from its pivots to the read bar', () => {
    const { lines } = readDrawing(READ, times, H1, text);
    const drawn = lines.filter((l) => l.id.startsWith('read:trendline'));
    expect(drawn).toHaveLength(READ.trendlines.length);
    const first = READ.trendlines[0];
    expect(drawn[0]?.points.at(-1)?.value).toBeCloseTo(first?.value ?? Number.NaN);
    expect(drawn[0]?.points.at(-1)?.time).toBe(times.at(-1));
  });

  it('colours the levels by role and marks the invalidation', () => {
    const { priceLines } = readDrawing(READ, times, H1, text);
    const levels = priceLines.filter((p) => p.title !== `ends:${READ.structure}`);
    expect(levels).toHaveLength(READ.levels.filter((l) => l.role !== 'SPENT').length);
    const flipped = READ.levels.find((l) => l.role === 'FLIPPED');
    const line = priceLines.find((p) => p.price === flipped?.price);
    expect(line?.color).toBe(READ_COLORS.FLIPPED);
    expect(line?.style).toBe('dashed');
    const invalidation = priceLines.find((p) => p.title === `ends:${READ.structure}`);
    expect(invalidation?.price).toBe(READ.invalidation);
  });

  it('draws nothing without a read, and only when the option is on', () => {
    expect(readDrawing(null, times, H1, text)).toEqual({ lines: [], markers: [], priceLines: [] });
    const candles = {
      server: 'FBS-Demo',
      symbol: 'XAUUSD',
      timeframe: 'H1',
      bars: fixture.bars as Candles['bars'],
      overlays: {},
      markers: [],
    } as Candles;
    const options: ModelOptions = {
      indicators: new Set(),
      zones: false,
      allDecisions: false,
      evidence: new Set(),
      invalidations: false,
      timeframeSeconds: H1,
    };
    const marketMap = { server: 'FBS-Demo', symbol: 'XAUUSD', at: READ.at, map: null, read: READ };
    const input = { candles, positions: [], signal: null, marketMap };
    const off = buildChartModel(input, options, text);
    const on = buildChartModel(input, { ...options, read: true }, text);
    expect(off.lines.some((l) => l.id.startsWith('read:'))).toBe(false);
    expect(on.lines.some((l) => l.id === 'read:swings')).toBe(true);
    expect(on.priceLines.length).toBeGreaterThan(off.priceLines.length);
  });
});
