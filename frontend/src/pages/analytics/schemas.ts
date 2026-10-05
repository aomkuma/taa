/** Analytics and recommendations of the owner's engine (TAA-1005; app/analytics/report.py, recommendations.py). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

export const SCOPES = ['PAPER', 'SHADOW', 'BACKTEST'] as const;
export type AnalyticsScope = (typeof SCOPES)[number];
export const DAYS = [30, 90, 180, 366] as const;
/** `STYLE_DIMENSIONS` in app/analytics/report.py. */
export const DIMENSIONS = [
  'strategy',
  'symbol',
  'session',
  'setup',
  'holding',
  'regime',
  'volatility',
  'direction',
  'weekday',
] as const;
export type Dimension = (typeof DIMENSIONS)[number];

const StyleRow = z.object({
  value: z.string(),
  trades: z.number().int(),
  expectancy_r: Value,
  net_r: Value,
  win_rate: Value,
});

export const ReportSchema = z.object({
  scope: z.enum(SCOPES),
  skipped: z.number().int(),
  period: z.object({ start: IsoDateTime.nullable(), end: IsoDateTime.nullable() }),
  hypothetical: z.boolean(),
  kpis: z.object({
    trades: z.number().int(),
    rated: z.number().int(),
    wins: z.number().int(),
    losses: z.number().int(),
    scratches: z.number().int(),
    win_rate: Value,
    expectancy_r: Value,
    net_r: Value,
    net_pnl: Value,
    profit_factor: Value,
    basis: z.enum(['MONEY', 'R']),
    max_drawdown_r: Value,
    sharpe: Value,
    sortino: Value,
    avg_hold_minutes: Value,
  }),
  curve: z.array(z.object({ time: IsoDateTime, r: z.number(), money: Value, drawdown_r: z.number() })),
  r_histogram: z.array(z.object({ low: Value, high: Value, count: z.number().int() })),
  by_style: z.record(z.string(), z.array(StyleRow)),
  mae_mfe: z.array(
    z.object({
      trade_id: z.string(),
      symbol: z.string(),
      mae_r: Value,
      mfe_r: Value,
      r: Value,
      outcome: z.enum(['WIN', 'LOSS', 'SCRATCH']),
    }),
  ),
  attribution: z.array(z.object({ code: z.string(), count: z.number().int(), share: Value })),
});
export type Report = z.infer<typeof ReportSchema>;

/** `Kind` in app/analytics/recommendations.py. */
export const RECOMMENDATION_KINDS = [
  'RESTRICT_SEGMENT',
  'EARLIER_BREAK_EVEN',
  'STOP_TOO_TIGHT',
  'COST_DRAG',
  'REDUCE_RISK',
] as const;

export const RecommendationSchema = z.object({
  kind: z.enum(RECOMMENDATION_KINDS),
  key: z.string(),
  sample_size: z.number().int(),
  enough: z.boolean(),
  min_samples: z.number().int(),
  evidence: z.record(z.string(), z.union([z.number(), z.string()])),
  segment: z.object({ dimension: z.string(), value: z.string() }).nullable(),
  ci: z.object({ mean: z.number(), low: z.number(), high: z.number(), n: z.number().int() }).nullable(),
  change: z
    .object({ kind: z.string(), value: z.union([z.number(), z.string()]), strategy: z.string().nullable() })
    .nullable(),
  /** The fields of a "Backtest this change" job (symbols and the change); null when it cannot be tested. */
  backtest: z.record(z.string(), z.unknown()).nullable(),
});
export type Recommendation = z.infer<typeof RecommendationSchema>;

export const RecommendationsSchema = z.object({
  scope: z.enum(SCOPES),
  trades: z.number().int(),
  after_stop_bars: z.number().int(),
  stops_checked: z.number().int(),
  hypothetical: z.boolean(),
  items: z.array(RecommendationSchema),
});

export interface AnalyticsQuery {
  scope: AnalyticsScope;
  days: number;
  run: string | null;
  variant: 'PLAN' | 'MANAGED';
}

export function queryString(q: AnalyticsQuery): string {
  const params = new URLSearchParams({ scope: q.scope, days: String(q.days) });
  if (q.scope === 'BACKTEST' && q.run) params.set('run', q.run);
  if (q.scope === 'SHADOW') params.set('variant', q.variant);
  return params.toString();
}

export const analyticsKeys = {
  report: (engineId: string, q: AnalyticsQuery) => [...engineKey(engineId), 'analytics', q] as const,
  recommendations: (engineId: string, q: AnalyticsQuery) =>
    [...engineKey(engineId), 'recommendations', q] as const,
};
