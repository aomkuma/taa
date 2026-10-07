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
  /** Line width in pixels (1 when absent); S/R zones are wider the stronger they are. */
  width?: number;
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
  /** Symbol and timeframe: a new view starts zoomed to fit instead of keeping the previous chart's range. */
  view: string;
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
  /** Evidence items drawn (ids); the page picks the strongest supporting ones first (TAA-925). */
  evidence: ReadonlySet<string>;
  /** Also each drawn item's invalidation level (off by default: the signal's own SL is what counts). */
  invalidations: boolean;
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

/** The most zones drawn per role (support, resistance, other): the strongest, as the API sorts them. */
export const ZONES_PER_ROLE = 3;

export type ZoneStrength = 'strong' | 'medium' | 'weak';

/** Strength from the number of swing touches: ≥ 6 strong, 4–5 medium, fewer weak. */
export function zoneStrength(touches: number): ZoneStrength {
  return touches >= 6 ? 'strong' : touches >= 4 ? 'medium' : 'weak';
}

/** Colour shade, width and dash per strength: the stronger the zone, the bolder its line. */
const ZONE_STYLE: Record<ZoneStrength, { shade: 0 | 1 | 2; width: number; style: LineStyle }> = {
  strong: { shade: 0, width: 3, style: 'solid' },
  medium: { shade: 1, width: 2, style: 'dashed' },
  weak: { shade: 2, width: 1, style: 'dotted' },
};
export const ZONE_COLORS = {
  SUPPORT: ['#16a34a', '#4ade80', '#86efac'],
  RESISTANCE: ['#dc2626', '#f87171', '#fca5a5'],
  OTHER: ['#475569', '#64748b', '#94a3b8'],
} as const;

/**
 * One line per zone at its middle (a zone spans at most `sr_tolerance_atr` × ATR), only the strongest
 * {@link ZONES_PER_ROLE} of each role, styled by strength so the busy levels stand out.
 */
function zoneLines(zones: readonly Zone[], text: ModelText): PriceLineModel[] {
  const kept: Record<string, number> = {};
  return zones.flatMap((z) => {
    const role = z.role === 'SUPPORT' || z.role === 'RESISTANCE' ? z.role : 'OTHER';
    kept[role] = (kept[role] ?? 0) + 1;
    if ((kept[role] ?? 0) > ZONES_PER_ROLE) return [];
    const look = ZONE_STYLE[zoneStrength(z.touches)];
    const title =
      role === 'SUPPORT'
        ? text.support(z.touches)
        : role === 'RESISTANCE'
          ? text.resistance(z.touches)
          : text.zone(z.touches);
    return [
      {
        price: (z.low + z.high) / 2,
        color: ZONE_COLORS[role][look.shade],
        title,
        style: look.style,
        width: look.width,
      },
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
  return relatedEvidence(signal).map((e) => e.evidence);
}

export type Relation = 'SUPPORTS' | 'CONFLICTS' | 'NEUTRAL';
export const RELATIONS: readonly Relation[] = ['SUPPORTS', 'CONFLICTS', 'NEUTRAL'];

export interface RelatedEvidence {
  evidence: Evidence;
  /** How the item relates to the signal's direction (`Relation` in app/evidence/confluence.py). */
  relation: Relation;
}

/** Each evidence item once with its relation to the signal, best quality first. */
export function relatedEvidence(signal: SignalSource['signal'] | null): RelatedEvidence[] {
  if (signal === null) return [];
  const byId = new Map<string, RelatedEvidence>();
  for (const e of signal.evidence) {
    const relation = (RELATIONS as readonly string[]).includes(e.relation)
      ? (e.relation as Relation)
      : 'NEUTRAL';
    byId.set(e.item.evidence.evidence_id, { evidence: e.item.evidence, relation });
  }
  return [...byId.values()].sort((a, b) => b.evidence.quality - a.evidence.quality);
}

/** How many supporting items a signal opens with: enough to see why, few enough to read (TAA-925). */
export const FOCUS_EVIDENCE = 3;

/** The items drawn when a signal opens: its {@link FOCUS_EVIDENCE} best supporting ones. */
export function focusEvidence(items: readonly RelatedEvidence[]): Set<string> {
  return new Set(
    items
      .filter((e) => e.relation === 'SUPPORTS')
      .slice(0, FOCUS_EVIDENCE)
      .map((e) => e.evidence.evidence_id),
  );
}

/** Evidence lines this close (a share of the shown price range, about a pixel) are drawn as one. */
export const MERGE_SHARE = 0.003;

/**
 * One line for evidence levels at (nearly) the same price, e.g. a channel seen on two timeframes: the first
 * line's look, the distinct titles joined (more than two become "first (+n)").
 */
export function mergeLines(lines: readonly PriceLineModel[], tolerance: number): PriceLineModel[] {
  const groups: { line: PriceLineModel; titles: string[] }[] = [];
  for (const line of [...lines].sort((a, b) => a.price - b.price)) {
    const last = groups.at(-1);
    if (last && Math.abs(line.price - last.line.price) <= tolerance) {
      if (!last.titles.includes(line.title)) last.titles.push(line.title);
    } else {
      groups.push({ line, titles: [line.title] });
    }
  }
  return groups.map(({ line, titles }) => ({
    ...line,
    title: titles.length <= 2 ? titles.join(' · ') : `${titles[0] ?? ''} (+${String(titles.length - 1)})`,
  }));
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
    if (!options.evidence.has(ev.evidence_id)) continue;
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
    if (options.invalidations && ev.invalidation !== null) {
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
  const highs = candles.bars.map((b) => b[2]);
  const lows = candles.bars.map((b) => b[3]);
  const range = highs.length ? Math.max(...highs) - Math.min(...lows) : 0;
  const markers = [...tradeMarkers(candles.markers, times, options, text), ...evidence.markers].sort(
    (a, b) => a.time - b.time,
  );
  // the forming bar goes last; indicators and marks stay on the closed bars
  const live = candles.forming;
  const shown =
    live && (times.length === 0 || seconds(live[0]) > (times.at(-1) ?? 0))
      ? [...bars, { time: seconds(live[0]), open: live[1], high: live[2], low: live[3], close: live[4] }]
      : bars;
  return {
    candles: shown,
    lines: [...lines, ...evidence.lines],
    markers,
    priceLines: [
      ...(options.zones ? zoneLines(candles.zones ?? [], text) : []),
      ...positionLines(input.positions, candles.symbol, text),
      ...signalLines(input.signal, text),
      ...mergeLines(evidence.priceLines, range * MERGE_SHARE),
    ],
    panes,
    precision: pricePrecision(candles.bars),
    view: `${candles.symbol}/${candles.timeframe}`,
  };
}

/**
 * The visible range after the data was replaced (bar open times before and after), so a refresh never undoes
 * the owner's zoom or scroll (TAA-925):
 * - A view that showed the newest bar keeps showing it with the same width and the same space after it (the
 *   owner's "chart shift"), even when the number of bars changed (the forming bar comes and goes; a refetch
 *   can return fewer bars than the live view had). At least one bar stays in view.
 * - A view scrolled back into history stays on the same bars: logical indexes move when the bar window slides,
 *   so the view is anchored on the time of its right edge.
 */
export function followRange(
  range: { from: number; to: number },
  before: readonly number[],
  after: readonly number[],
): { from: number; to: number } {
  const oldLast = before.length - 1;
  if (oldLast < 0) return range;
  const width = range.to - range.from;
  if (range.to >= oldLast - 0.5) {
    const gap = Math.min(range.to - oldLast, Math.max(width - 1, 0));
    const to = after.length - 1 + gap;
    return { from: to - width, to };
  }
  const anchor = Math.min(Math.max(Math.round(range.to), 0), oldLast);
  const time = before[anchor];
  const moved = time === undefined ? -1 : after.indexOf(time);
  if (moved < 0) return range;
  const shift = moved - anchor;
  return { from: range.from + shift, to: range.to + shift };
}
