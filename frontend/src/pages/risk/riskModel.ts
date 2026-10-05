/** Pure helpers of the risk & controls page (TAA-911): limits against current values, control availability. */
import type { AccountSnapshot } from '@/engine/schemas';
import { gaugeLevel, type GaugeLevel, lossUsed } from '@/components/gaugeLevels';

import type { EngineConfig, RiskLimits } from './schemas';

export type LimitUnit = 'percent' | 'count';

export interface MeasuredLimit {
  key: 'daily' | 'weekly' | 'drawdown' | 'heat' | 'losses' | 'positions';
  unit: LimitUnit;
  /** What is used now (a gain uses none of a loss limit); null when the engine could not measure it. */
  used: number | null;
  limit: number | null;
  level: GaugeLevel;
}

/**
 * The limits the engine measures every health step, from the newest heartbeat (account snapshot and open
 * positions) against the limits it reports; the open-position limit comes from the run's config.
 */
export function measuredLimits(
  account: AccountSnapshot | null | undefined,
  openPositions: number | null,
  risk: RiskLimits | undefined,
): MeasuredLimit[] {
  const limits = account?.limits;
  const row = (
    key: MeasuredLimit['key'],
    unit: LimitUnit,
    used: number | null,
    limit: number | null | undefined,
  ) => ({
    key,
    unit,
    used,
    limit: limit ?? null,
    level: limit ? gaugeLevel(used, limit) : ('unknown' as const),
  });
  return [
    row('daily', 'percent', lossUsed(account?.day_pnl_percent ?? null), limits?.daily_loss_percent),
    row('weekly', 'percent', lossUsed(account?.week_pnl_percent ?? null), limits?.weekly_loss_percent),
    row(
      'drawdown',
      'percent',
      account ? Math.abs(account.drawdown_percent ?? NaN) : null,
      limits?.drawdown_percent,
    ),
    row('heat', 'percent', account?.heat_percent ?? null, limits?.heat_percent),
    row('losses', 'count', account?.consecutive_losses ?? null, limits?.consecutive_losses),
    row('positions', 'count', openPositions, risk?.max_open_positions),
  ].map((r) => ({ ...r, used: r.used !== null && Number.isFinite(r.used) ? r.used : null }));
}

export type StaticUnit = 'percent' | 'count' | 'points' | 'ratio' | 'hours' | 'lots' | 'money';

/** The per-trade and exposure limits that are checked on each decision (read-only, from the run's config). */
export const STATIC_LIMITS = [
  ['max_risk_per_trade_percent', 'percent'],
  ['max_risk_money_per_trade', 'money'],
  ['max_total_open_risk_percent', 'percent'],
  ['max_positions_per_symbol', 'count'],
  ['max_same_direction_per_currency', 'count'],
  ['min_risk_reward', 'ratio'],
  ['max_spread_points', 'points'],
  ['max_spread_to_sl_ratio', 'ratio'],
  ['max_slippage_points', 'points'],
  ['max_lot', 'lots'],
  ['min_margin_level_percent', 'percent'],
  ['max_margin_utilization_percent', 'percent'],
  ['max_effective_leverage', 'ratio'],
  ['consecutive_loss_pause_hours', 'hours'],
] as const satisfies readonly (readonly [keyof RiskLimits, StaticUnit])[];

export interface Controls {
  /** FLATTEN_ALL works only with KILL_SWITCH_FLATTEN_ALLOWED=true on the engine. */
  flattenAllowed: boolean;
  /** POSITION_CLOSE and FLATTEN_ALL need CONTROL_TOTP_SECRET on the engine. */
  engineCode: boolean;
}

/** What the engine's run says about the remote controls; unknown (no config yet) counts as not available. */
export function controlsOf(config: EngineConfig | undefined): Controls {
  const env = config?.config.env;
  return {
    flattenAllowed: env?.KILL_SWITCH_FLATTEN_ALLOWED === true,
    engineCode: typeof env?.CONTROL_TOTP_SECRET === 'string' && env.CONTROL_TOTP_SECRET !== '',
  };
}

const BREAKER_ORDER: Record<string, number> = { OPEN: 0, HALF_OPEN: 1, CLOSED: 2 };

/** Breakers that block something first (open, then half-open), then by name. */
export function sortBreakers<T extends { state: string; name: string; scope_key: string }>(
  rows: readonly T[],
): T[] {
  return [...rows].sort(
    (a, b) =>
      (BREAKER_ORDER[a.state] ?? 3) - (BREAKER_ORDER[b.state] ?? 3) ||
      a.name.localeCompare(b.name) ||
      a.scope_key.localeCompare(b.scope_key),
  );
}
