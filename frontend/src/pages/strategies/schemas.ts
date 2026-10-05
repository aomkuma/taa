/** Responses of the strategies page (TAA-909; `app/web/strategies.py`) and the control API (TAA-805). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';
import { STRATEGY_STATES } from '@/i18n/codes';

const IsoDateTime = z.iso.datetime({ offset: true });
const Ratio = z.number().nullable();

/** A queued control command as `public()` in app/sync/command_queue.py shows it (never with a code). */
export const CommandSchema = z.looseObject({
  id: z.string(),
  type: z.string(),
  params: z.record(z.string(), z.unknown()),
  created_by: z.string(),
  created_at: IsoDateTime,
  expires_at: IsoDateTime,
  status: z.string(),
  delivered_at: IsoDateTime.nullable(),
  completed_at: IsoDateTime.nullable(),
  result: z.looseObject({
    outcome: z.string().nullable().optional(),
    reason: z.string().nullable().optional(),
    detail: z.string().nullable().optional(),
  }),
});
export type Command = z.infer<typeof CommandSchema>;

/** A parameter value is whatever the strategy's pydantic model dumps: scalars, lists or small objects. */
const ParamValue = z.unknown();

export const StrategySchema = z.looseObject({
  name: z.string(),
  configured_enabled: z.boolean(),
  state: z.enum(STRATEGY_STATES),
  known: z.boolean(),
  version: z.string().nullable(),
  description: z.string().nullable(),
  demo_only: z.boolean(),
  timeframes: z.array(z.string()),
  warmup_bars: z.number().int().nullable(),
  params: z.record(z.string(), ParamValue),
  overrides: z.array(z.string()),
  decisions: z.object({ ACCEPT: z.number().int(), REJECT: z.number().int(), HOLD: z.number().int() }),
  top_reject_reasons: z.array(z.object({ code: z.string(), count: z.number().int() })),
  performance: z.object({
    trades: z.number().int(),
    open: z.number().int(),
    wins: z.number().int(),
    losses: z.number().int(),
    win_rate: Ratio,
    net: z.number().nullable(),
    profit_factor: Ratio,
    avg_r: z.number().nullable(),
    r_trades: z.number().int(),
    last_exit_at: IsoDateTime.nullable(),
  }),
  last_command: CommandSchema.nullable(),
});
export type Strategy = z.infer<typeof StrategySchema>;

export const StrategiesSchema = z.object({
  config_hash: z.string().nullable(),
  run_id: z.string().nullable(),
  mode: z.string().nullable(),
  heartbeat_at: IsoDateTime.nullable().optional(),
  remote_known: z.boolean(),
  window: z.object({ days: z.number().int(), since: IsoDateTime }),
  timeframes: z.object({
    higher: z.string().nullable().optional(),
    entry: z.string().nullable().optional(),
    refinement: z.string().nullable().optional(),
  }),
  shared: z.object({
    cooldown_bars: z.number().int().nullable().optional(),
    signal_expiry_bars: z.number().int().nullable().optional(),
    allow_single_indicator_signals: z.boolean().nullable().optional(),
  }),
  strategies: z.array(StrategySchema),
});
export type Strategies = z.infer<typeof StrategiesSchema>;

export const WINDOWS = [7, 30, 90, 365] as const;

export const strategyKeys = {
  all: (engineId: string) => [...engineKey(engineId), 'strategies'] as const,
  list: (engineId: string, days: number) => [...engineKey(engineId), 'strategies', days] as const,
};
