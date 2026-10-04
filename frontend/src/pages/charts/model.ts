/**
 * Turns API data into what the chart draws (PLAN §A15 charts, §A29 evidence overlays). Pure, so it is tested
 * without a canvas; `chartAdapter.ts` hands the result to Lightweight Charts.
 *
 * Times are UTC epoch seconds of bar **open** times. Marks are snapped onto the shown bars:
 * - `close` stamps (decisions, evidence pivots: the close time of their bar) go to the bar that closed then
 * - `instant` stamps (fills, exits) go to the bar that contains them
 * A mark outside the shown bars is left out rather than drawn at the edge.
 */
import type { Candles, ChartMarker, Evidence, SignalSource, Zone } from './schemas';

export const INDICATORS = ['ema', 'bb', 'rsi', 'atr', 'adx'] as const;
export type Indicator = (typeof INDICATORS)[number];

/** EMA and Bollinger bands are drawn over the candles; these get a pane each, in this order. */
const PANE_INDICATORS = ['rsi', 'atr', 'adx'] as const;

const OVERLAY_SPECS: Record<Indicator, readonly string[]> = {
  ema: ['ema:20', 'ema:50'],
  bb: ['bb:20'],
  rsi: ['rsi:14'],
  atr: ['atr:14'],
  adx: ['adx:14'],
};

export type LineStyle = 'solid' | 'dashed' | 'dotted';

export interface Point {
  time: number;
  value: number;
}

export interface LineModel {
  id: string;
  pane: number;
  color: string;
  width: 1 | 2;
  style: LineStyle;
  points: Point[];
}

export interface MarkerModel {
  time: number;
  position: 'aboveBar' | 'belowBar' | 'atPriceMiddle';
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
  color: string;
  text: string;
  price?: number;
}

export interface PriceLineModel {
  price: number;
  color: string;
  title: string;
  style: LineStyle;
}

export interface ChartModel {
  candles: { time: number; open: number; high: number; low: number; close: number }[];
  lines: LineModel[];
  markers: MarkerModel[];
  priceLines: PriceLineModel[];
  /** Panes in use, including the price pane. */
  panes: number;
  /** Decimals of the price axis, from the quoted prices (EURUSD 5, XAUUSD 2–3, indices 0–2). */
  precision: number;
}

export interface OpenPosition {
  ticket: number;
  symbol: string;
  side: string;
  entry_price: number;
  sl: number | null;
  tp: number | null;
}

export interface ModelOptions {
  indicators: ReadonlySet<Indicator>;
  zones: boolean;
  /** Also rejected and held decisions (by default only accepted ones are marked). */
  allDecisions: boolean;
  /** Evidence families shown (theory toggles). */
  families: ReadonlySet<string>;
  timeframeSeconds: number;
}

export interface ModelInput {
  candles: Candles;
  positions: readonly OpenPosition[];
  signal: SignalSource['signal'] | null;
}

/** Labels the model needs in the user's language. */
export interface ModelText {
  decision: (code: string) => string;
  support: (touches: number) => string;
  resistance: (touches: number) => string;
  zone: (touches: number) => string;
  entry: (ticket: number, side: string) => string;
  stopLoss: (ticket: number | null) => string;
  takeProfit: (ticket: number | null) => string;
  signalEntry: string;
  target: string;
  invalidation: string;
}

export const COLORS = {
  up: '#16a34a',
  down: '#dc2626',
  neutral: '#64748b',
  entry: '#2563eb',
  ema20: '#2563eb',
  ema50: '#f59e0b',
  bb: '#94a3b8',
  rsi: '#7c3aed',
  atr: '#0891b2',
  adx: '#db2777',
} as const;

/** One colour per evidence family, readable on light and dark backgrounds. */
export const FAMILY_COLORS: Record<string, string> = {
  FIBONACCI: '#d97706',
  LEVELS: '#0d9488',
  TREND: '#2563eb',
  CHART_PATTERN: '#9333ea',
  CANDLESTICK: '#ea580c',
  MOMENTUM: '#7c3aed',
  VOLATILITY_VOLUME: '#0891b2',
  ICHIMOKU: '#65a30d',
  SMART_MONEY: '#be123c',
  HARMONIC: '#c026d3',
  ELLIOTT: '#4f46e5',
  SESSIONS: '#475569',
};

/** The `overlays=` query for the chosen indicators. */
export function overlaysQuery(indicators: ReadonlySet<Indicator>): string {
  return INDICATORS.filter((i) => indicators.has(i))
    .flatMap((i) => OVERLAY_SPECS[i])
    .join(',');
}

const seconds = (iso: string) => Math.floor(Date.parse(iso) / 1000);

const MAX_PRECISION = 6;

/** The most decimals any of the first bars' prices carries (prices are quoted at the symbol's digits). */
export function pricePrecision(bars: Candles['bars']): number {
  let best = 0;
  for (const [, ...prices] of bars.slice(0, 100)) {
    for (const price of prices.slice(0, 4)) {
      for (let d = best; d < MAX_PRECISION; d++) {
        const scaled = price * 10 ** d;
        if (Math.abs(scaled - Math.round(scaled)) < 1e-6 * Math.max(1, Math.abs(scaled))) break;
        best = d + 1;
      }
    }
  }
  return best;
}

/** The bar a stamp belongs to (see the module docs), or null outside the shown bars. */
export function snapTime(
  times: readonly number[],
  at: number,
  mode: 'close' | 'instant',
  timeframeSeconds: number,
): number | null {
  const first = times[0];
  const last = times.at(-1);
  if (first === undefined || last === undefined) return null;
  const t = mode === 'close' ? at - timeframeSeconds : at;
  if (t < first || t >= last + timeframeSeconds) return null;
  let lo = 0;
  let hi = times.length - 1;
  while (lo < hi) {
    // the last bar opened at or before t
    const mid = Math.ceil((lo + hi) / 2);
    if ((times[mid] ?? Infinity) <= t) lo = mid;
    else hi = mid - 1;
  }
  return times[lo] ?? null;
}

/** Strictly increasing times (Lightweight Charts requires it); the later value wins on a tie. */
function ascending(points: Point[]): Point[] {
  const byTime = new Map<number, number>();
  for (const p of [...points].sort((a, b) => a.time - b.time)) byTime.set(p.time, p.value);
  return [...byTime].map(([time, value]) => ({ time, value }));
}

function overlayLine(
  candles: Candles,
  times: readonly number[],
  name: string,
  id: string,
  pane: number,
  color: string,
  style: LineStyle = 'solid',
): LineModel | null {
  const values = candles.overlays[name];
  if (!values) return null;
  const points: Point[] = [];
  values.forEach((value, i) => {
    const time = times[i];
    if (value !== null && Number.isFinite(value) && time !== undefined) points.push({ time, value });
  });
  return { id, pane, color, width: 1, style, points };
}

function indicatorLines(candles: Candles, times: readonly number[], indicators: ReadonlySet<Indicator>) {
  const lines: (LineModel | null)[] = [];
  if (indicators.has('ema')) {
    lines.push(overlayLine(candles, times, 'ema:20', 'ema:20', 0, COLORS.ema20));
    lines.push(overlayLine(candles, times, 'ema:50', 'ema:50', 0, COLORS.ema50));
  }
  if (indicators.has('bb')) {
    for (const band of ['upper', 'mid', 'lower']) {
      const style = band === 'mid' ? 'dotted' : 'solid';
      lines.push(overlayLine(candles, times, `bb:20:${band}`, `bb:20:${band}`, 0, COLORS.bb, style));
    }
  }
  let pane = 0;
  for (const indicator of PANE_INDICATORS) {
    if (!indicators.has(indicator)) continue;
    pane += 1;
    lines.push(overlayLine(candles, times, `${indicator}:14`, `${indicator}:14`, pane, COLORS[indicator]));
  }
  return { lines: lines.filter((l): l is LineModel => l !== null && l.points.length > 0), panes: pane + 1 };
}

function tradeMarkers(
  markers: readonly ChartMarker[],
  times: readonly number[],
  options: ModelOptions,
  text: ModelText,
): MarkerModel[] {
  const out: MarkerModel[] = [];
  for (const m of markers) {
    const mode = m.kind === 'decision' ? 'close' : 'instant';
    const time = snapTime(times, seconds(m.at), mode, options.timeframeSeconds);
    if (time === null) continue;
    if (m.kind === 'decision') {
      if (m.decision !== 'ACCEPT') {
        if (options.allDecisions) {
          out.push({
            time,
            position: 'aboveBar',
            shape: 'circle',
            color: COLORS.neutral,
            text: text.decision(m.decision),
          });
        }
        continue;
      }
      const buy = m.action === 'BUY';
      out.push({
        time,
        position: buy ? 'belowBar' : 'aboveBar',
        shape: buy ? 'arrowUp' : 'arrowDown',
        color: buy ? COLORS.up : COLORS.down,
        text: m.action,
      });
    } else if (m.kind === 'entry') {
      const buy = m.side === 'BUY';
      out.push({
        time,
        position: buy ? 'belowBar' : 'aboveBar',
        shape: buy ? 'arrowUp' : 'arrowDown',
        color: COLORS.entry,
        text: `#${String(m.ticket)}`,
      });
    } else {
      out.push({
        time,
        position: m.side === 'BUY' ? 'aboveBar' : 'belowBar',
        shape: 'square',
        color: COLORS.neutral,
        text: [`#${String(m.ticket)}`, m.reason].filter(Boolean).join(' '),
      });
    }
  }
  return out;
}

function zoneLines(zones: readonly Zone[], text: ModelText): PriceLineModel[] {
  return zones.flatMap((z) => {
    const color = z.role === 'SUPPORT' ? COLORS.up : z.role === 'RESISTANCE' ? COLORS.down : COLORS.neutral;
    const title =
      z.role === 'SUPPORT'
        ? text.support(z.touches)
        : z.role === 'RESISTANCE'
          ? text.resistance(z.touches)
          : text.zone(z.touches);
    return [
      { price: z.high, color, title, style: 'dotted' as const },
      ...(z.low !== z.high ? [{ price: z.low, color, title: '', style: 'dotted' as const }] : []),
    ];
  });
}

function positionLines(
  positions: readonly OpenPosition[],
  symbol: string,
  text: ModelText,
): PriceLineModel[] {
  return positions
    .filter((p) => p.symbol === symbol)
    .flatMap((p) => [
      {
        price: p.entry_price,
        color: COLORS.entry,
        title: text.entry(p.ticket, p.side),
        style: 'solid' as const,
      },
      ...(p.sl === null
        ? []
        : [{ price: p.sl, color: COLORS.down, title: text.stopLoss(p.ticket), style: 'dashed' as const }]),
      ...(p.tp === null
        ? []
        : [{ price: p.tp, color: COLORS.up, title: text.takeProfit(p.ticket), style: 'dashed' as const }]),
    ]);
}

/** The evidence items of a signal, newest detection first per id (a signal may list one item per timeframe). */
export function signalEvidence(signal: SignalSource['signal'] | null): Evidence[] {
  if (signal === null) return [];
  const byId = new Map<string, Evidence>();
  for (const e of signal.evidence) byId.set(e.item.evidence.evidence_id, e.item.evidence);
  return [...byId.values()];
}

function evidenceDrawing(
  items: readonly Evidence[],
  times: readonly number[],
  options: ModelOptions,
  text: ModelText,
): { lines: LineModel[]; markers: MarkerModel[]; priceLines: PriceLineModel[] } {
  const lines: LineModel[] = [];
  const markers: MarkerModel[] = [];
  const priceLines: PriceLineModel[] = [];
  for (const ev of items) {
    if (!options.families.has(ev.family)) continue;
    const color = FAMILY_COLORS[ev.family] ?? COLORS.neutral;
    const points: Point[] = [];
    for (const level of ev.key_levels) {
      if (level.at === null) {
        // fib levels, necklines, zone and PRZ edges: horizontal lines
        priceLines.push({ price: level.price, color, title: `${ev.name}: ${level.name}`, style: 'dashed' });
        continue;
      }
      const time = snapTime(times, seconds(level.at), 'close', options.timeframeSeconds);
      if (time === null) continue;
      // pattern points (XABCD, waves, swings): joined in time order, each labelled
      points.push({ time, value: level.price });
      markers.push({
        time,
        position: 'atPriceMiddle',
        shape: 'circle',
        color,
        text: level.name,
        price: level.price,
      });
    }
    if (points.length >= 2) {
      lines.push({
        id: `evidence:${ev.evidence_id}`,
        pane: 0,
        color,
        width: 2,
        style: 'solid',
        points: ascending(points),
      });
    }
    for (const target of ev.targets) {
      priceLines.push({ price: target, color, title: `${ev.name}: ${text.target}`, style: 'dotted' });
    }
    if (ev.invalidation !== null) {
      priceLines.push({
        price: ev.invalidation,
        color: COLORS.down,
        title: `${ev.name}: ${text.invalidation}`,
        style: 'dotted',
      });
    }
  }
  return { lines, markers, priceLines };
}

function signalLines(signal: SignalSource['signal'] | null, text: ModelText): PriceLineModel[] {
  if (signal === null) return [];
  const out: PriceLineModel[] = [];
  if (signal.entry_price != null)
    out.push({ price: signal.entry_price, color: COLORS.entry, title: text.signalEntry, style: 'solid' });
  if (signal.stop_loss != null)
    out.push({ price: signal.stop_loss, color: COLORS.down, title: text.stopLoss(null), style: 'dashed' });
  if (signal.take_profit != null)
    out.push({ price: signal.take_profit, color: COLORS.up, title: text.takeProfit(null), style: 'dashed' });
  return out;
}

export function buildChartModel(input: ModelInput, options: ModelOptions, text: ModelText): ChartModel {
  const { candles } = input;
  const bars = candles.bars.map(([at, open, high, low, close]) => ({
    time: seconds(at),
    open,
    high,
    low,
    close,
  }));
  const times = bars.map((b) => b.time);
  const { lines, panes } = indicatorLines(candles, times, options.indicators);
  const evidence = evidenceDrawing(signalEvidence(input.signal), times, options, text);
  const markers = [...tradeMarkers(candles.markers, times, options, text), ...evidence.markers].sort(
    (a, b) => a.time - b.time,
  );
  return {
    candles: bars,
    lines: [...lines, ...evidence.lines],
    markers,
    priceLines: [
      ...(options.zones ? zoneLines(candles.zones ?? [], text) : []),
      ...positionLines(input.positions, candles.symbol, text),
      ...signalLines(input.signal, text),
      ...evidence.priceLines,
    ],
    panes,
    precision: pricePrecision(candles.bars),
  };
}
