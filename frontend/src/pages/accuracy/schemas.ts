/**
 * Responses of the signal accuracy page (TAA-809 advisory APIs; `app/advisory/stats.py`, `calibration.py`).
 * Every result is hypothetical: shadow trades, not orders.
 */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

/** `Summary`: hit rate and its 90% Wilson interval in percent; money at each moment's lot. */
export const SummarySchema = z.object({
  n: z.number().int(),
  wins: z.number().int(),
  hit_rate: Value,
  hit_low: Value,
  hit_high: Value,
  expectancy_r: Value,
  profit_factor_r: Value,
  n_money: z.number().int(),
  expectancy_money: Value,
  profit_factor_money: Value,
  total_pnl: z.number(),
  max_drawdown: z.number(),
  max_drawdown_r: z.number(),
});
export type Summary = z.infer<typeof SummarySchema>;

/** The "follow every one" curve in exit order, from 0. */
export const CurvePointSchema = z.object({
  at: IsoDateTime,
  pnl: z.number(),
  r: z.number(),
  drawdown: z.number(),
  drawdown_r: z.number(),
});
export type CurvePoint = z.infer<typeof CurvePointSchema>;

export const ExplorerSchema = z.looseObject({
  metric: z.string(),
  in_sample: z.boolean(),
  rows: z.array(z.object({ threshold: z.number(), summary: SummarySchema })),
});
export type Explorer = z.infer<typeof ExplorerSchema>;

/** `TheoryScore`: a detector (`ev:FAMILY:detector`) or a family, per (asset class, timeframe). */
export const TheoryScoreSchema = z.object({
  theory: z.string(),
  level: z.enum(['detector', 'family']),
  group: z.array(z.string()),
  n: z.number().int(),
  hit_rate: z.number(),
  low: z.number(),
  high: z.number(),
  expectancy_r: z.number(),
  base_rate: z.number(),
  lift: Value,
});
export type TheoryScore = z.infer<typeof TheoryScoreSchema>;

export const SectionSchema = z.object({
  source: z.enum(['LIVE', 'REPLAY']),
  summary: SummarySchema,
  curve: z.array(CurvePointSchema),
  /** dimension → group key → summary (`DIMENSIONS`, plus `watchlist` when the user has lists) */
  breakdowns: z.record(z.string(), z.record(z.string(), SummarySchema)),
  explorer: ExplorerSchema,
  scoreboard: z.array(TheoryScoreSchema),
});
export type Section = z.infer<typeof SectionSchema>;

/** `GET /engines/{id}/accuracy[?mine=true]`: LIVE and REPLAY never mixed. */
export const AccuracySchema = z.object({
  server: z.string(),
  variant: z.enum(['PLAN', 'MANAGED']),
  hypothetical: z.literal(true),
  /** `my_alerts`: only the alerts this user got, at their own risk money (always on the market feed). */
  scope: z.literal('my_alerts').optional(),
  currency: z.string().nullable().optional(),
  live: SectionSchema,
  replay: SectionSchema,
});
export type Accuracy = z.infer<typeof AccuracySchema>;

export const ReliabilityBinSchema = z.object({
  low: z.number(),
  high: z.number(),
  n: z.number().int(),
  mean_predicted: Value,
  observed: Value,
});
export type ReliabilityBin = z.infer<typeof ReliabilityBinSchema>;

/** `GET /engines/{id}/calibration`: the newest version (404 `calibration_not_found` before the first). */
export const CalibrationSchema = z.looseObject({
  version: z.string(),
  built_at: IsoDateTime,
  variant: z.string(),
  n_live: z.number().int(),
  n_replay: z.number().int(),
  window_start: IsoDateTime.nullable(),
  window_end: IsoDateTime.nullable(),
  uses_evidence: z.boolean(),
  /** Of the selected model, out of sample. */
  brier: Value,
  reliability: z.array(ReliabilityBinSchema),
});
export type Calibration = z.infer<typeof CalibrationSchema>;

/** A shadow trade (`shadow_trades` row; money fields are left out on the market feed). */
export const ShadowTradeSchema = z.looseObject({
  shadow_id: z.string(),
  opportunity_id: z.string(),
  source: z.string(),
  variant: z.string(),
  status: z.string(),
  symbol: z.string(),
  side: z.string(),
  strategy: z.string(),
  timeframe: z.string(),
  setup_strength: z.number(),
  rr: Value,
  signal_at: IsoDateTime,
  exit_at: IsoDateTime.nullable(),
  exit_reason: z.string().nullable(),
  win: z.boolean().nullable(),
  r_net: Value,
  net_pnl: Value.optional(),
  currency: z.string().nullable().optional(),
  flags: z.array(z.string()),
});
export type ShadowTrade = z.infer<typeof ShadowTradeSchema>;

export const ShadowTradesSchema = z.object({
  items: z.array(ShadowTradeSchema),
  next_cursor: z.string().nullable(),
});

export type Source = 'LIVE' | 'REPLAY';
export type Variant = 'PLAN' | 'MANAGED';

export const accuracyKeys = {
  report: (engineId: string, variant: Variant, mine: boolean) =>
    [...engineKey(engineId), 'accuracy', variant, mine] as const,
  calibration: (engineId: string) => [...engineKey(engineId), 'accuracy', 'calibration'] as const,
  history: (engineId: string, source: Source, variant: Variant) =>
    [...engineKey(engineId), 'accuracy', 'history', source, variant] as const,
};
