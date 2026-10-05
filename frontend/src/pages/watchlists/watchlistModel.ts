/** Pure helpers of the watchlists page and the alert settings (TAA-918). */
import {
  type AlertPreferences,
  DEFAULT_THRESHOLD,
  DEFAULT_TOP_N,
  LIMITS,
  SYMBOL_PATTERN,
  type UserWindow,
  type Watchlist,
} from './schemas';

/** The global x: the user's threshold, else the metric's default. */
export function globalThreshold(alerts: Pick<AlertPreferences, 'metric' | 'threshold'>): number {
  return alerts.threshold ?? DEFAULT_THRESHOLD[alerts.metric];
}

/** The x that applies to *list*: its own override, else the global one. */
export function listThreshold(list: Watchlist, alerts: Pick<AlertPreferences, 'metric' | 'threshold'>) {
  return list.threshold ?? globalThreshold(alerts);
}

/** The symbols an AUTO_TOP_N list takes now: the first N ranks of the latest ranking (as the alerter does). */
export function topSymbols(items: readonly { symbol: string; rank: number }[], n: number | null): string[] {
  return [...items]
    .sort((a, b) => a.rank - b.rank)
    .slice(0, n ?? DEFAULT_TOP_N)
    .map((item) => item.symbol);
}

/** Symbols typed into the add box (comma or space separated); `invalid` holds names the backend rejects. */
export function parseSymbols(text: string): { valid: string[]; invalid: string[] } {
  const names = text.split(/[\s,;]+/).filter((name) => name !== '');
  return {
    valid: names.filter((name) => SYMBOL_PATTERN.test(name)),
    invalid: names.filter((name) => !SYMBOL_PATTERN.test(name)),
  };
}

/** *symbols* followed by *added*, without duplicates, order kept (the backend de-duplicates the same way). */
export function addSymbols(symbols: readonly string[], added: readonly string[]): string[] {
  return [...new Set([...symbols, ...added])];
}

export type ListProblem = 'name' | 'nameTaken' | 'topN' | 'threshold' | 'tooMany';

/** What keeps *list* from being saved; *others* are the names of the user's other lists. */
export function listProblems(list: Watchlist, others: readonly string[]): ListProblem[] {
  const problems: ListProblem[] = [];
  const name = list.name.trim();
  if (name === '' || name.length > LIMITS.listName) problems.push('name');
  else if (others.some((other) => other.toLowerCase() === name.toLowerCase())) problems.push('nameTaken');
  if (list.kind === 'AUTO_TOP_N' && !inRange(list.top_n ?? DEFAULT_TOP_N, LIMITS.topN)) problems.push('topN');
  if (list.threshold !== null && !inRange(list.threshold, [0, 100], false)) problems.push('threshold');
  if (list.symbols.length > LIMITS.listSymbols) problems.push('tooMany');
  return problems;
}

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

export function windowValid(window: UserWindow): boolean {
  return window.days.length > 0 && HHMM.test(window.start) && HHMM.test(window.end);
}

export type AlertProblem = 'threshold' | 'lifetime' | 'windows' | 'perHour' | 'cooldown';

export function alertProblems(alerts: AlertPreferences): AlertProblem[] {
  const problems: AlertProblem[] = [];
  if (alerts.threshold !== null && !inRange(alerts.threshold, [0, 100], false)) problems.push('threshold');
  if (!inRange(alerts.signal_lifetime_bars, LIMITS.lifetimeBars)) problems.push('lifetime');
  if (alerts.windows.length > LIMITS.windows || !alerts.windows.every(windowValid)) problems.push('windows');
  if (!inRange(alerts.rate_limits.max_alerts_per_hour, LIMITS.alertsPerHour)) problems.push('perHour');
  if (!inRange(alerts.rate_limits.symbol_cooldown_minutes, LIMITS.cooldownMinutes)) problems.push('cooldown');
  return problems;
}

/** A new window: every day, 08:00–22:00. */
export const newWindow = (): UserWindow => ({ days: [0, 1, 2, 3, 4, 5, 6], start: '08:00', end: '22:00' });

/** Toggles weekday *day* (Monday = 0) in *days*, kept sorted. */
export function toggleDay(days: readonly number[], day: number): number[] {
  return days.includes(day) ? days.filter((d) => d !== day) : [...days, day].sort((a, b) => a - b);
}

/** Short weekday names for Monday..Sunday in *locale*. */
export function weekdayNames(locale: string): string[] {
  const format = new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' });
  // 2026-09-28 is a Monday
  return Array.from({ length: 7 }, (_, i) => format.format(Date.UTC(2026, 8, 28 + i)));
}

function inRange(value: number, [min, max]: readonly [number, number], integer = true): boolean {
  return Number.isFinite(value) && value >= min && value <= max && (!integer || Number.isInteger(value));
}
