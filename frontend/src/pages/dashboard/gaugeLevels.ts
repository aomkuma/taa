/** How close a value is to its limit: `ok` below half, `warn` from half, `danger` from 80 %, `breached` at it. */
export type GaugeLevel = 'ok' | 'warn' | 'danger' | 'breached' | 'unknown';

export function gaugeLevel(used: number | null, limit: number): GaugeLevel {
  if (used === null || !Number.isFinite(used) || limit <= 0) return 'unknown';
  const ratio = used / limit;
  if (ratio >= 1) return 'breached';
  if (ratio >= 0.8) return 'danger';
  if (ratio >= 0.5) return 'warn';
  return 'ok';
}

/** The share of the limit used, clamped to 0–100 for drawing. */
export function gaugeFill(used: number | null, limit: number): number {
  if (used === null || !Number.isFinite(used) || limit <= 0) return 0;
  return Math.min(100, Math.max(0, (100 * used) / limit));
}

/** A loss as a positive amount (a gain uses none of a loss limit). */
export function lossUsed(pnlPercent: number | null): number | null {
  return pnlPercent === null ? null : Math.max(0, -pnlPercent);
}
