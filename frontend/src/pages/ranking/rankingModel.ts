/** Pure helpers of the symbol ranking page (PLAN §A25, §A28): sorting, filters and the hints of a row. */
import type { ExplainParams } from '@/i18n/explain';

import type { RankingItem } from './schemas';

/** `Score` (app/advisory/scoring.py); the Overall score uses `OVERALL_SCORES`, the Now score all nine. */
export const SCORES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9'] as const;
export const OVERALL_SCORES: ReadonlySet<string> = new Set(['S1', 'S2', 'S3', 'S8', 'S9']);

/** Flags of `score_candidate` (neutral defaults and a closed market). */
export const FLAGS = [
  'unknown_volatility',
  'unknown_regime',
  'insufficient_history',
  'unknown_swap',
  'market_closed',
] as const;

export type SortKey = 'rank' | 'now' | 'overall' | 'symbol';
export type SortDirection = 'asc' | 'desc';

export interface Filters {
  assetClass: string | null;
  eligibleOnly: boolean;
  search: string;
}

/** Eligible for this user: the engine's gates for the owner, the user's own affordability on the feed. */
export function isEligible(item: RankingItem): boolean {
  return item.personal ? item.personal.eligible === true : item.eligible;
}

/** The equity the minimum lot needs ("needs equity ≥ $Z"), shown only when the minimum lot is not affordable. */
export function requiredEquity(item: RankingItem): { value: number; currency: string } | null {
  if (item.personal) {
    const value = item.personal.required_equity;
    return value != null && item.personal.currency ? { value, currency: item.personal.currency } : null;
  }
  const g2Failed = item.gates.some((g) => g.gate === 'G2_MIN_LOT' && g.status === 'FAIL');
  const value = item.metrics.required_equity;
  const currency = item.metrics.currency;
  return g2Failed && value != null && currency ? { value, currency } : null;
}

export function filterItems(items: readonly RankingItem[], filters: Filters): RankingItem[] {
  const needle = filters.search.trim().toUpperCase();
  return items.filter(
    (item) =>
      (filters.assetClass === null || item.asset_class === filters.assetClass) &&
      (!filters.eligibleOnly || isEligible(item)) &&
      (!needle || item.symbol.toUpperCase().includes(needle)),
  );
}

/**
 * Sorted copy; ties keep the server's order. `rank` is the server's order itself (eligible first, then open
 * markets, then the Now score; on the feed the user's own eligibility first).
 */
export function sortItems(
  items: readonly RankingItem[],
  key: SortKey,
  direction: SortDirection,
): RankingItem[] {
  const sign = direction === 'asc' ? 1 : -1;
  const order = new Map(items.map((item, index) => [item, index]));
  const position = (item: RankingItem) => order.get(item) ?? 0;
  const compare: Record<SortKey, (a: RankingItem, b: RankingItem) => number> = {
    rank: () => 0,
    now: (a, b) => a.now_score - b.now_score,
    overall: (a, b) => a.overall - b.overall,
    symbol: (a, b) => a.symbol.localeCompare(b.symbol),
  };
  return [...items].sort((a, b) => {
    const diff = key === 'rank' ? position(a) - position(b) : compare[key](a, b);
    return diff !== 0 ? diff * sign : position(a) - position(b);
  });
}

/** The first direction of a newly chosen column: scores high first, rank and names ascending. */
export function defaultDirection(key: SortKey): SortDirection {
  return key === 'now' || key === 'overall' ? 'desc' : 'asc';
}

/** The asset classes present, in the order of `order` (the backend enum), unknown ones last. */
export function presentClasses(items: readonly RankingItem[], order: readonly string[]): string[] {
  const present = new Set(items.map((i) => i.asset_class));
  const known = order.filter((c) => present.has(c));
  return [...known, ...[...present].filter((c) => !order.includes(c)).sort()];
}

/** Gate parameters for `explain()`: strings and finite numbers only. */
export function explainParams(params: Readonly<Record<string, unknown>>): ExplainParams {
  const out: Record<string, string | number> = {};
  for (const [name, value] of Object.entries(params)) {
    if (typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value))) out[name] = value;
  }
  return out;
}

/** The top *n* symbols this user can trade, in rank order (dashboard widget). */
export function topEligible(items: readonly RankingItem[], n: number): RankingItem[] {
  return items.filter(isEligible).slice(0, n);
}
