/** Learning reports (TAA-L701 / L801 / L808; app/web/learning.py). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const Value = z.number().nullable();

const ShareSchema = z.object({
  count: z.number().int(),
  n: z.number().int(),
  share: z.number(),
  low: z.number(),
  high: z.number(),
});
export type Share = z.infer<typeof ShareSchema>;

const Quantiles = z.record(z.string(), z.number()).nullable();

export const TimingGroupSchema = z.object({
  key: z.array(z.string()),
  trades: z.number().int(),
  losers: z.number().int(),
  /** FailureMode (app/learning/timing.py) → share of the losing trades */
  modes: z.record(z.string(), ShareSchema.nullable()),
  winner_mae_r: Quantiles,
  winner_mae_atr: Quantiles,
  winner_bars_to_tp: Quantiles,
  hit_rate: ShareSchema.nullable(),
  baseline_hit_rate: Value,
  vindicated: ShareSchema.nullable(),
  baseline_vindicated: Value,
});
export type TimingGroup = z.infer<typeof TimingGroupSchema>;

export const TimingSchema = z.object({
  scope: z.string(),
  trades: z.number().int(),
  skipped: z.number().int(),
  lookahead_hours: z.number().int(),
  hypothetical: z.boolean(),
  overall: z.array(TimingGroupSchema),
  groups: z.array(TimingGroupSchema),
});
export type Timing = z.infer<typeof TimingSchema>;

const DecompositionSchema = z.object({
  key: z.array(z.string()),
  n: z.number().int(),
  p: z.number(),
  win_r: z.number(),
  loss_r: z.number(),
  cost_r: z.number(),
  expectancy_r: z.number(),
  ci: z.object({ mean: z.number(), low: z.number(), high: z.number() }),
  per_week: Value,
  unknown_costs: z.number().int(),
});
export type Decomposition = z.infer<typeof DecompositionSchema>;

export const ExpectancySchema = z.object({
  scope: z.string(),
  days: z.number().int(),
  hypothetical: z.boolean(),
  overall: DecompositionSchema.nullable(),
  previous: DecompositionSchema.nullable(),
  change: z
    .object({
      p: z.number(),
      win_r: z.number(),
      loss_r: z.number(),
      cost_r: z.number(),
      total: z.number(),
      main: z.enum(['p', 'W', 'L', 'c']),
    })
    .nullable(),
  groups: z.array(DecompositionSchema),
});
export type Expectancy = z.infer<typeof ExpectancySchema>;

export const BehaviorSchema = z.object({
  days: z.number().int(),
  trades: z.number().int(),
  max_trades_per_day: z.number().int().nullable(),
  lookahead_hours: z.number().int(),
  hypothetical: z.boolean(),
  patterns: z.array(
    z.object({
      /** Pattern (app/learning/behavior.py) */
      pattern: z.string(),
      count: z.number().int(),
      considered: z.number().int(),
      share: z.number(),
      delta_r: z.number(),
    }),
  ),
  class_mix: z.record(z.string(), z.number()),
  opportunity_mix: z.record(z.string(), z.number()),
  comfort_distance: Value,
});
export type Behavior = z.infer<typeof BehaviorSchema>;

export const learningKeys = {
  timing: (engineId: string, scope: string, days: number) =>
    [...engineKey(engineId), 'learning', 'timing', scope, days] as const,
  expectancy: (engineId: string, scope: string, days: number) =>
    [...engineKey(engineId), 'learning', 'expectancy', scope, days] as const,
  behavior: (engineId: string, days: number) =>
    [...engineKey(engineId), 'learning', 'behavior', days] as const,
};
