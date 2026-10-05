/** Responses of the backtests page (TAA-807 API, TAA-910 history route; app/web/routers/backtests.py). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Num = z.number().nullable();

/** `Metrics` (app/backtest/metrics.py): money in the account currency, percent values in percent units. */
export const MetricsSchema = z.object({
  trades: z.number().int(),
  wins: z.number().int(),
  losses: z.number().int(),
  win_rate: Num,
  net_profit: z.number(),
  gross_profit: z.number(),
  gross_loss: z.number(),
  profit_factor: Num,
  expectancy_money: Num,
  expectancy_r: Num,
  avg_win_r: Num,
  avg_loss_r: Num,
  max_drawdown: z.number(),
  max_drawdown_percent: z.number(),
  longest_drawdown_days: z.number(),
  cagr_percent: Num,
  calmar: Num,
  sharpe: Num,
  sortino: Num,
  exposure_percent: z.number(),
  commission: z.number(),
  swap: z.number(),
  avg_mae_r: Num,
  avg_mfe_r: Num,
  initial_equity: z.number(),
  final_equity: z.number(),
});
export type Metrics = z.infer<typeof MetricsSchema>;

export const RequestSchema = z.looseObject({
  preset: z.string(),
  symbols: z.array(z.string()),
  start: IsoDateTime,
  end: IsoDateTime,
  strategies: z.array(z.string()).nullable().optional(),
  risk_percent: Num.optional(),
  seed: z.number().int().nullable().optional(),
});

export const RunSchema = z.looseObject({
  run_id: z.string(),
  preset: z.string(),
  request: RequestSchema,
  status: z.string(),
  progress: z.number(),
  created_at: IsoDateTime,
  started_at: IsoDateTime.nullable(),
  finished_at: IsoDateTime.nullable(),
  error: z.string(),
  metrics: MetricsSchema.nullable().optional(),
  trades_total: z.number().int(),
});
export type Run = z.infer<typeof RunSchema>;

export const RunsPageSchema = z.object({ items: z.array(RunSchema), next_cursor: z.string().nullable() });

const ProvenanceSchema = z.looseObject({
  seed: z.number().int().nullable().optional(),
  config_hash: z.string().optional(),
  data_hash: z.string().optional(),
  code_version: z.string().optional(),
  strategies: z.array(z.string()).optional(),
});

/** `GET .../backtests/{id}`: the run plus the CLI summary and the equity curve `[time, balance, equity]`. */
export const RunDetailSchema = RunSchema.extend({
  summary: z.looseObject({
    provenance: ProvenanceSchema.optional(),
    period: z.looseObject({ start: IsoDateTime.nullable(), end: IsoDateTime.nullable() }).optional(),
    symbols: z.array(z.string()).optional(),
    signals: z.number().int().optional(),
    decisions: z.record(z.string(), z.number().int()).optional(),
    rejections: z.record(z.string(), z.number().int()).optional(),
    limitations: z.array(z.string()).optional(),
    server: z.string().optional(),
  }),
  equity: z.array(z.tuple([IsoDateTime, z.number(), z.number()])),
});
export type RunDetail = z.infer<typeof RunDetailSchema>;

/** One stored trade (`trade_row` in app/backtest/report.py). */
export const TradeSchema = z.looseObject({
  ticket: z.number().int(),
  symbol: z.string(),
  side: z.string(),
  volume: z.number(),
  entry_time: IsoDateTime,
  entry_price: z.number(),
  exit_time: IsoDateTime,
  exit_price: z.number(),
  exit_reason: z.string(),
  net: z.number(),
  r_multiple: Num,
  strategy: z.string(),
});
export type Trade = z.infer<typeof TradeSchema>;

export const TradesSchema = z.object({
  items: z.array(TradeSchema),
  offset: z.number().int(),
  stored: z.number().int(),
  total: z.number().int(),
});

export const CompareSchema = z.object({
  runs: z.array(
    z.looseObject({
      run_id: z.string(),
      preset: z.string(),
      request: RequestSchema,
      metrics: MetricsSchema.nullable().optional(),
      provenance: ProvenanceSchema.nullable().optional(),
      trades_total: z.number().int(),
    }),
  ),
});
export type Compare = z.infer<typeof CompareSchema>;

export const PresetsSchema = z.object({
  presets: z.array(z.string()),
  max_symbols: z.number().int(),
  max_days: z.number().int(),
  max_open_runs: z.number().int(),
});

export const HistorySchema = z.object({
  items: z.array(
    z.object({
      server: z.string(),
      symbol: z.string(),
      timeframe: z.string(),
      first: IsoDateTime,
      last: IsoDateTime,
      bars: z.number().int(),
    }),
  ),
});
export type History = z.infer<typeof HistorySchema>;

export const OPEN_STATUSES = new Set(['QUEUED', 'RUNNING']);

export const backtestKeys = {
  all: (engineId: string) => [...engineKey(engineId), 'backtests'] as const,
  list: (engineId: string) => [...engineKey(engineId), 'backtests', 'list'] as const,
  detail: (engineId: string, runId: string) => [...engineKey(engineId), 'backtests', 'run', runId] as const,
  trades: (engineId: string, runId: string) =>
    [...engineKey(engineId), 'backtests', 'trades', runId] as const,
  compare: (engineId: string, ids: string) => [...engineKey(engineId), 'backtests', 'compare', ids] as const,
  history: (engineId: string) => [...engineKey(engineId), 'backtests', 'history'] as const,
  presets: ['backtests', 'presets'] as const,
};
