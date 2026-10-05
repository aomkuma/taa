/** Responses of the risk & controls page (TAA-803 read APIs, TAA-805 commands). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Num = z.number().nullable().optional();

/**
 * `GET /engines/{id}/config`: the effective configuration of the latest run (`Settings.summary()`, secrets masked
 * as `***`). The page reads the risk limits and the two switches the remote controls depend on.
 */
export const EngineConfigSchema = z.object({
  config_hash: z.string(),
  created_at: IsoDateTime,
  config: z.looseObject({
    env: z
      .looseObject({
        TRADING_MODE: z.string().optional(),
        KILL_SWITCH_FLATTEN_ALLOWED: z.boolean().optional(),
        /** "***" when set (masked), null when not: POSITION_CLOSE and FLATTEN_ALL need it on the engine. */
        CONTROL_TOTP_SECRET: z.string().nullable().optional(),
      })
      .optional(),
    config: z
      .looseObject({
        risk: z
          .object({
            max_risk_per_trade_percent: Num,
            max_risk_money_per_trade: Num,
            max_open_positions: Num,
            max_positions_per_symbol: Num,
            max_total_open_risk_percent: Num,
            max_daily_loss_percent: Num,
            max_weekly_loss_percent: Num,
            max_account_drawdown_percent: Num,
            max_consecutive_losses: Num,
            consecutive_loss_pause_hours: Num,
            max_spread_points: Num,
            max_spread_to_sl_ratio: Num,
            max_slippage_points: Num,
            min_risk_reward: Num,
            max_lot: Num,
            min_margin_level_percent: Num,
            max_margin_utilization_percent: Num,
            max_effective_leverage: Num,
            max_same_direction_per_currency: Num,
          })
          .optional(),
      })
      .optional(),
  }),
});
export type EngineConfig = z.infer<typeof EngineConfigSchema>;
export type RiskLimits = NonNullable<NonNullable<EngineConfig['config']['config']>['risk']>;

export const KillSwitchEventSchema = z.looseObject({
  ts_utc: IsoDateTime,
  action: z.string(),
  mode: z.string(),
  source: z.string(),
  actor: z.string(),
  reason: z.string(),
});
export const KillSwitchPageSchema = z.object({
  items: z.array(KillSwitchEventSchema),
  next_cursor: z.string().nullable(),
});

export const BreakerRowSchema = z.looseObject({
  name: z.string(),
  scope_key: z.string(),
  state: z.string(),
  reason: z.string(),
  opened_at: IsoDateTime.nullable(),
  latched: z.boolean(),
  trips_today: z.number().int(),
  updated_at: IsoDateTime,
});
export type BreakerRow = z.infer<typeof BreakerRowSchema>;

export const BreakerEventSchema = z.looseObject({
  ts_utc: IsoDateTime,
  name: z.string(),
  scope_key: z.string(),
  action: z.string(),
  severity: z.string(),
  actor: z.string(),
  reason: z.string(),
});

export const BreakersPageSchema = z.object({
  states: z.array(BreakerRowSchema),
  events: z.object({ items: z.array(BreakerEventSchema), next_cursor: z.string().nullable() }),
});

export const riskKeys = {
  config: (engineId: string) => [...engineKey(engineId), 'config'] as const,
  killSwitch: (engineId: string) => [...engineKey(engineId), 'risk', 'kill-switch'] as const,
  breakers: (engineId: string) => [...engineKey(engineId), 'risk', 'breakers'] as const,
};
