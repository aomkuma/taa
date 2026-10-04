/** Responses of the symbols page (TAA-803 symbols/decisions, TAA-906 quotes). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

/** `SymbolSpec` (app/market_data/data_models.py) as stored in the catalog. */
export const SpecSchema = z.looseObject({
  digits: z.number().int(),
  point: z.number(),
  tick_size: z.number(),
  tick_value: z.number(),
  contract_size: z.number(),
  volume_min: z.number(),
  volume_max: z.number(),
  volume_step: z.number(),
  stops_level: z.number().int(),
  freeze_level: z.number().int(),
  filling_mode: z.number().int(),
  trade_mode: z.number().int(),
  currency_base: z.string(),
  currency_profit: z.string(),
  currency_margin: z.string(),
  spread_float: z.boolean(),
  swap_long: z.number(),
  swap_short: z.number(),
});
export type Spec = z.infer<typeof SpecSchema>;

export const SymbolDetailSchema = z.looseObject({
  server: z.string(),
  symbol: z.string(),
  asset_class: z.string(),
  enabled: z.boolean(),
  reason: z.string(),
  description: z.string(),
  spec: SpecSchema,
  refreshed_at: IsoDateTime,
});

export const QuoteSchema = z.looseObject({
  symbol: z.string(),
  bid: z.number(),
  ask: z.number(),
  spread_points: Value,
  /** The engine's spread limit for the symbol (absent from engines older than TAA-906). */
  max_spread_points: Value.optional(),
  time: IsoDateTime,
});
export type Quote = z.infer<typeof QuoteSchema>;

/** `GET /engines/{id}/quotes`; the stream's `quotes` events carry `{at, quotes}`. */
export const QuotesSchema = z.object({
  at: IsoDateTime.nullable(),
  received_at: IsoDateTime.nullable(),
  quotes: z.array(QuoteSchema),
});
export type Quotes = z.infer<typeof QuotesSchema>;
export const QuotesEventSchema = z.object({ at: IsoDateTime, quotes: z.array(QuoteSchema) });

const TimeframeStateSchema = z.looseObject({
  timeframe: z.string(),
  bar_close_utc: IsoDateTime,
  close: z.number(),
  trend: z.string(),
  regime: z.string(),
  volatility: z.string(),
  structure: z.string().nullable().optional(),
  atr: Value.optional(),
  adx: Value.optional(),
  rsi: Value.optional(),
});

/** A decision's `market` document (`MarketContext.to_dict`). */
export const DecisionMarketSchema = z.looseObject({
  decision_id: z.string(),
  created_at: IsoDateTime,
  market: z.looseObject({
    session: z.string(),
    states: z.array(TimeframeStateSchema),
    support_levels: z.array(z.number()),
    resistance_levels: z.array(z.number()),
  }),
});

export const DecisionRefsSchema = z.object({
  items: z.array(z.looseObject({ decision_id: z.string(), created_at: IsoDateTime })),
  next_cursor: z.string().nullable(),
});

export const symbolKeys = {
  all: (engineId: string) => [...engineKey(engineId), 'symbols', 'all'] as const,
  detail: (engineId: string, symbol: string) =>
    [...engineKey(engineId), 'symbols', 'detail', symbol] as const,
  quotes: (engineId: string) => [...engineKey(engineId), 'quotes'] as const,
  latestDecision: (engineId: string, symbol: string) =>
    [...engineKey(engineId), 'decisions', 'latest', symbol] as const,
  decision: (engineId: string, decisionId: string) =>
    [...engineKey(engineId), 'decisions', 'detail', decisionId] as const,
};
