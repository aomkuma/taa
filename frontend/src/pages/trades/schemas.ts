/** Responses of the positions and history pages (TAA-803 positions/trades/intents, TAA-907 trade detail). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

const page = <T extends z.ZodType>(item: T) =>
  z.object({ items: z.array(item), next_cursor: z.string().nullable() });

/** A paper position (`paper_positions`); `profit` is the floating P/L while open, the realized one after. */
export const TradeSchema = z.looseObject({
  ticket: z.number().int(),
  intent_id: z.string(),
  symbol: z.string(),
  side: z.string(),
  volume: z.number(),
  entry_time: IsoDateTime,
  entry_price: z.number(),
  sl: Value,
  tp: Value,
  stop_kind: z.string(),
  commission: z.number(),
  swap: z.number(),
  mae: z.number(),
  mfe: z.number(),
  price_current: z.number(),
  status: z.string(),
  exit_time: IsoDateTime.nullable(),
  exit_price: Value,
  exit_reason: z.string().nullable(),
  profit: Value,
  net: Value,
  r_multiple: Value,
  bars_held: z.number().int(),
});
export type Trade = z.infer<typeof TradeSchema>;
export const TradesPageSchema = page(TradeSchema);

/** A closed bot position on the broker account (`broker_trades`, DEMO/LIVE; TAA-1208); `net` includes swap,
 * commission and fees. */
export const BrokerTradeSchema = z.looseObject({
  position_ticket: z.number().int(),
  mode: z.string(),
  strategy: z.string(),
  symbol: z.string(),
  side: z.string(),
  volume: z.number(),
  part_index: z.number().int(),
  entry_time: IsoDateTime,
  entry_price: z.number(),
  sl_initial: z.number(),
  tp: Value,
  exit_time: IsoDateTime,
  exit_price: z.number(),
  exit_reason: z.string().nullable(),
  profit: z.number(),
  swap: z.number(),
  commission: z.number(),
  net: z.number(),
  r_multiple: Value,
});
export type BrokerTrade = z.infer<typeof BrokerTradeSchema>;
export const BrokerTradesPageSchema = page(BrokerTradeSchema);

export const PaperIntentSchema = z.looseObject({
  intent_id: z.string(),
  decision_id: z.string(),
  strategy: z.string(),
  symbol: z.string(),
  side: z.string(),
  volume: z.number(),
  entry_type: z.string(),
  price: Value,
  sl: Value,
  tp: Value,
  expires_at: IsoDateTime.nullable(),
  status: z.string(),
  detail: z.string(),
  created_at: IsoDateTime,
});
export type PaperIntent = z.infer<typeof PaperIntentSchema>;
export const PaperIntentsPageSchema = page(PaperIntentSchema);

export const OrderIntentSchema = z.looseObject({
  intent_id: z.string(),
  decision_id: z.string(),
  strategy: z.string(),
  symbol: z.string(),
  side: z.string(),
  volume: z.number(),
  price_requested: z.number(),
  sl: z.number(),
  tp: Value,
  state: z.string(),
  retcode: z.number().int().nullable(),
  retcode_desc: z.string(),
  position_ticket: z.number().int().nullable(),
  fill_price: Value,
  created_at: IsoDateTime,
});
export type OrderIntent = z.infer<typeof OrderIntentSchema>;
export const OrderIntentsPageSchema = page(OrderIntentSchema);

const CheckSchema = z.looseObject({
  seq: z.number().int(),
  name: z.string(),
  reason: z.string(),
  passed: z.boolean(),
  kind: z.string(),
});

/** `GET /engines/{id}/trades/{ticket}`. */
export const TradeDetailSchema = z.object({
  position: TradeSchema,
  intent: PaperIntentSchema.nullable(),
  decision: z
    .looseObject({
      decision_id: z.string(),
      created_at: IsoDateTime,
      strategy: z.string(),
      timeframe: z.string(),
      decision: z.string(),
      reason_codes: z.array(z.string()),
      risk_money: Value,
      signal: z.looseObject({
        created_at_utc: IsoDateTime,
        score: z.number(),
        reason_codes: z.array(z.string()),
        explanation: z.string().optional(),
      }),
      checks: z.array(CheckSchema),
    })
    .nullable(),
  events: z.array(
    z.object({ type: z.string(), at: IsoDateTime, payload: z.record(z.string(), z.unknown()) }),
  ),
});
export type TradeDetail = z.infer<typeof TradeDetailSchema>;

export const tradeKeys = {
  open: (engineId: string) => [...engineKey(engineId), 'positions', 'open', 'list'] as const,
  closed: (engineId: string, symbol: string) =>
    [...engineKey(engineId), 'positions', 'closed', symbol] as const,
  broker: (engineId: string, symbol: string) =>
    [...engineKey(engineId), 'positions', 'broker', symbol] as const,
  paperIntents: (engineId: string) => [...engineKey(engineId), 'intents', 'paper', 'PENDING'] as const,
  orderIntents: (engineId: string) => [...engineKey(engineId), 'intents', 'broker'] as const,
  detail: (engineId: string, ticket: number) =>
    [...engineKey(engineId), 'positions', 'detail', ticket] as const,
};
