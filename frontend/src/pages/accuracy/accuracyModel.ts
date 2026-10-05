/** Pure helpers of the signal accuracy page (TAA-919). */
import type { Point } from '@/pages/backtests/backtestModel';

import type { CurvePoint, ReliabilityBin, Summary, TheoryScore } from './schemas';

/** Breakdown dimensions in display order (`DIMENSIONS` of app/advisory/stats.py, plus `watchlist`). */
export const DIMENSIONS = [
  'symbol',
  'strategy',
  'asset_class',
  'session',
  'side',
  'timeframe',
  'watchlist',
  'alerted',
  'followed',
] as const;
export type Dimension = (typeof DIMENSIONS)[number];

/** z of a two-sided 90% interval, as the backend's `wilson_interval`. */
const Z90 = 1.6448536269514722;

/** The 90% Wilson interval of *wins* in *n* (fractions 0..1); null without trades. */
export function wilson(wins: number, n: number, z: number = Z90): [number, number] | null {
  if (n <= 0) return null;
  const p = wins / n;
  const z2 = z * z;
  const centre = (p + z2 / (2 * n)) / (1 + z2 / n);
  const half = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / (1 + z2 / n);
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

export interface CalibrationPoint {
  /** Mean predicted and observed win rate, percent. */
  predicted: number;
  observed: number;
  /** 90% interval of the observed rate, percent. */
  low: number;
  high: number;
  n: number;
}

/** Reliability bins with outcomes, as points with the observed rate's interval. */
export function calibrationPoints(bins: readonly ReliabilityBin[]): CalibrationPoint[] {
  return bins.flatMap((bin) => {
    if (bin.n <= 0 || bin.mean_predicted === null || bin.observed === null) return [];
    const interval = wilson(Math.round(bin.observed * bin.n), bin.n);
    if (interval === null) return [];
    return [
      {
        predicted: 100 * bin.mean_predicted,
        observed: 100 * bin.observed,
        low: 100 * interval[0],
        high: 100 * interval[1],
        n: bin.n,
      },
    ];
  });
}

/** Lower edge of a strength bucket name (`<50`, `50-65`, `80+`) for ordering. */
function bucketStart(name: string): number {
  if (name.startsWith('<')) return -1;
  const start = Number.parseFloat(name);
  return Number.isFinite(start) ? start : Number.POSITIVE_INFINITY;
}

/** Strength buckets, weakest first. */
export function bucketRows(groups: Readonly<Record<string, Summary>> | undefined): [string, Summary][] {
  return Object.entries(groups ?? {}).sort(([a], [b]) => bucketStart(a) - bucketStart(b));
}

/** A breakdown's groups, most trades first (then by name). */
export function breakdownRows(groups: Readonly<Record<string, Summary>> | undefined): [string, Summary][] {
  return Object.entries(groups ?? {}).sort(([a, x], [b, y]) => y.n - x.n || a.localeCompare(b));
}

/** One value of the follow-all curve over time, one point per second at most (the chart needs that). */
export function curveSeries(curve: readonly CurvePoint[], value: (p: CurvePoint) => number): Point[] {
  const out: Point[] = [];
  for (const point of curve) {
    const time = Math.floor(Date.parse(point.at) / 1000);
    const last = out.at(-1);
    if (last && last.time >= time) last.value = value(point);
    else out.push({ time, value: value(point) });
  }
  return out;
}

/** `ev:FAMILY:detector` → its family and detector; a family row is the family alone. */
export function theoryParts(score: Pick<TheoryScore, 'theory' | 'level'>): {
  family: string;
  detector: string | null;
} {
  if (score.level === 'family') return { family: score.theory, detector: null };
  const [, family = '', ...rest] = score.theory.split(':');
  return { family, detector: rest.join(':') || null };
}

export interface ScoreGroup {
  /** Asset class and timeframe. */
  assetClass: string;
  timeframe: string;
  rows: TheoryScore[];
}

/** Scoreboard rows of one *level*, grouped by (asset class, timeframe); each group most trades first. */
export function scoreGroups(items: readonly TheoryScore[], level: TheoryScore['level']): ScoreGroup[] {
  const groups = new Map<string, ScoreGroup>();
  for (const item of items) {
    if (item.level !== level) continue;
    const [assetClass = '', timeframe = ''] = item.group;
    const key = `${assetClass}|${timeframe}`;
    const group = groups.get(key) ?? { assetClass, timeframe, rows: [] };
    group.rows.push(item);
    groups.set(key, group);
  }
  for (const group of groups.values()) {
    group.rows.sort((a, b) => b.n - a.n || a.theory.localeCompare(b.theory));
  }
  return [...groups.values()].sort((a, b) =>
    `${a.assetClass}|${a.timeframe}`.localeCompare(`${b.assetClass}|${b.timeframe}`),
  );
}
