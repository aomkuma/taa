/** Pure helpers of the backtests page (TAA-910): metric formats, curves and the new-run request. */
import type { History, Metrics, RunDetail } from './schemas';

/** `PresetName` (app/backtest/presets.py); a parity test reads the Literal. */
export const PRESETS = ['standard', 'conservative', 'high_costs'] as const;
/** `LIMITATIONS` (app/backtest/report.py), in order; the English texts must equal the backtester's. */
export const LIMITATION_KEYS = ['l0', 'l1', 'l2', 'l3', 'l4'] as const;

/** How a metric is shown: money in the account currency, percent units, R multiples, days, plain numbers. */
export type MetricFormat = 'money' | 'percent' | 'r' | 'days' | 'int' | 'ratio';

/** Every field of `Metrics` (app/backtest/metrics.py) in display order; a parity test reads the dataclass. */
export const METRICS: readonly (readonly [keyof Metrics, MetricFormat])[] = [
  ['net_profit', 'money'],
  ['trades', 'int'],
  ['wins', 'int'],
  ['losses', 'int'],
  ['win_rate', 'percent'],
  ['profit_factor', 'ratio'],
  ['expectancy_money', 'money'],
  ['expectancy_r', 'r'],
  ['avg_win_r', 'r'],
  ['avg_loss_r', 'r'],
  ['max_drawdown', 'money'],
  ['max_drawdown_percent', 'percent'],
  ['longest_drawdown_days', 'days'],
  ['cagr_percent', 'percent'],
  ['calmar', 'ratio'],
  ['sharpe', 'ratio'],
  ['sortino', 'ratio'],
  ['exposure_percent', 'percent'],
  ['gross_profit', 'money'],
  ['gross_loss', 'money'],
  ['commission', 'money'],
  ['swap', 'money'],
  ['avg_mae_r', 'r'],
  ['avg_mfe_r', 'r'],
  ['initial_equity', 'money'],
  ['final_equity', 'money'],
];

/** The headline figures of a run (the tiles and the list columns). */
export const HEADLINE: readonly (keyof Metrics)[] = [
  'net_profit',
  'trades',
  'win_rate',
  'profit_factor',
  'expectancy_r',
  'max_drawdown_percent',
];

export const formatOf = (key: string): MetricFormat => METRICS.find(([k]) => k === key)?.[1] ?? 'ratio';

export interface Point {
  time: number;
  value: number;
}

const seconds = (iso: string) => Math.floor(Date.parse(iso) / 1000);

/** Equity over time, one point per second at most (the chart needs strictly increasing times). */
export function equityPoints(equity: RunDetail['equity']): Point[] {
  const out: Point[] = [];
  for (const [at, , value] of equity) {
    const time = seconds(at);
    const last = out.at(-1);
    if (last && last.time >= time) last.value = value;
    else out.push({ time, value });
  }
  return out;
}

/** Drawdown in percent of the running equity peak (≤ 0), as `equity_frame` computes it. */
export function drawdownPoints(points: readonly Point[]): Point[] {
  let peak = -Infinity;
  return points.map(({ time, value }) => {
    peak = Math.max(peak, value);
    return { time, value: peak > 0 ? (100 * (value - peak)) / peak : 0 };
  });
}

// --- new run ------------------------------------------------------------------------------------------

export interface RunForm {
  preset: string;
  symbols: string[];
  /** `YYYY-MM-DD`, UTC days: the period runs from the start day's 00:00 to the end day's 24:00 (UTC). */
  start: string;
  end: string;
  /** Empty: every strategy enabled in config.yaml. */
  strategies: string[];
  riskPercent: string;
  seed: string;
}

export interface SymbolHistory {
  symbol: string;
  server: string;
  first: string;
  last: string;
}

/** Symbols with M15 history (the entry timeframe the backtester needs), with their range. */
export function symbolsWithHistory(history: History): SymbolHistory[] {
  return history.items
    .filter((i) => i.timeframe === 'M15')
    .map((i) => ({ symbol: i.symbol, server: i.server, first: i.first, last: i.last }))
    .sort((a, b) => a.symbol.localeCompare(b.symbol));
}

const day = (ms: number) => new Date(ms).toISOString().slice(0, 10);
const DAY_MS = 86_400_000;

/** Defaults: the last *days* of the newest uploaded history, ending yesterday at the latest (UTC). */
export function defaultPeriod(
  available: readonly SymbolHistory[],
  now: number,
  days = 90,
): { start: string; end: string } {
  const lastBar = Math.max(...available.map((s) => Date.parse(s.last)), -Infinity);
  const end = Math.min(Number.isFinite(lastBar) ? lastBar : now, now - DAY_MS);
  const firstBar = Math.min(...available.map((s) => Date.parse(s.first)), Infinity);
  const start = Math.max(end - (days - 1) * DAY_MS, Number.isFinite(firstBar) ? firstBar : -Infinity);
  return { start: day(start), end: day(end) };
}

export type FormProblem = 'symbols' | 'tooManySymbols' | 'period' | 'tooLong' | 'notEnded' | 'risk' | 'seed';

/** The `BacktestRequest` body, or the first problem the server would refuse it for. */
export function buildRequest(
  form: RunForm,
  now: number,
  limits: { maxSymbols: number; maxDays: number },
): { body: Record<string, unknown> } | { problem: FormProblem } {
  if (form.symbols.length === 0) return { problem: 'symbols' };
  if (form.symbols.length > limits.maxSymbols) return { problem: 'tooManySymbols' };
  const start = Date.parse(`${form.start}T00:00:00Z`);
  const end = Date.parse(`${form.end}T00:00:00Z`) + DAY_MS;
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return { problem: 'period' };
  if (end - start > limits.maxDays * DAY_MS) return { problem: 'tooLong' };
  if (end > now) return { problem: 'notEnded' };
  const body: Record<string, unknown> = {
    preset: form.preset,
    symbols: form.symbols,
    start: new Date(start).toISOString(),
    end: new Date(end).toISOString(),
  };
  if (form.strategies.length > 0) body.strategies = form.strategies;
  if (form.riskPercent.trim() !== '') {
    const risk = Number(form.riskPercent);
    if (!Number.isFinite(risk) || risk <= 0) return { problem: 'risk' };
    body.risk_percent = risk;
  }
  if (form.seed.trim() !== '') {
    const seed = Number(form.seed);
    if (!Number.isInteger(seed) || seed < 0 || seed >= 2 ** 31) return { problem: 'seed' };
    body.seed = seed;
  }
  return { body };
}

/**
 * Selected symbols whose uploaded M15 history starts after the requested start: the run can test only the
 * bars that exist (after the warm-up), so a short history gives few or no signals.
 */
export function historyShortfall(form: RunForm, available: readonly SymbolHistory[]): SymbolHistory[] {
  const start = Date.parse(`${form.start}T00:00:00Z`);
  if (!Number.isFinite(start)) return [];
  return available.filter((s) => form.symbols.includes(s.symbol) && Date.parse(s.first) > start + DAY_MS);
}
