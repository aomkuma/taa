import type { Point } from '@/pages/backtests/backtestModel';

import type { Report } from './schemas';

/** The cumulative-R curve and its drawdown as chart points (seconds). */
export function curvePoints(report: Report): { result: Point[]; drawdown: Point[] } {
  const seen = new Set<number>();
  const result: Point[] = [];
  const drawdown: Point[] = [];
  for (const p of report.curve) {
    let time = Math.floor(Date.parse(p.time) / 1000);
    while (seen.has(time)) time += 1; // the chart needs strictly increasing times
    seen.add(time);
    result.push({ time, value: p.r });
    drawdown.push({ time, value: p.drawdown_r });
  }
  return { result, drawdown };
}

/** The share of the tallest bin, for the R histogram's bar heights. */
export function histogramShares(report: Report): number[] {
  const max = Math.max(1, ...report.r_histogram.map((b) => b.count));
  return report.r_histogram.map((b) => b.count / max);
}

/** The period a "Backtest this change" job tests: the last *days* days ending at today's 00:00 UTC (ended). */
export function backtestPeriod(now: Date, days: number): { start: string; end: string } {
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const start = new Date(end.getTime() - Math.min(days, 366) * 86_400_000);
  return { start: start.toISOString(), end: end.toISOString() };
}
