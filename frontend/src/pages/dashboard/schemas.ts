/** Responses the dashboard reads (TAA-803 read APIs, TAA-806 notifications). Loose: other pages add fields. */
import { z } from 'zod';

const IsoDateTime = z.iso.datetime({ offset: true });

const page = <T extends z.ZodType>(item: T) =>
  z.object({ items: z.array(item), next_cursor: z.string().nullable() });

export const PositionSchema = z.looseObject({
  ticket: z.number().int(),
  symbol: z.string(),
  side: z.string(),
  volume: z.number(),
  entry_price: z.number(),
  entry_time: IsoDateTime,
  sl: z.number().nullable(),
  tp: z.number().nullable(),
  price_current: z.number(),
});
export const PositionsPageSchema = page(PositionSchema);

export const DecisionSchema = z.looseObject({
  decision_id: z.string(),
  created_at: IsoDateTime,
  symbol: z.string(),
  strategy: z.string(),
  action: z.string(),
  decision: z.string(),
  reason_codes: z.array(z.string()),
});
export const DecisionsPageSchema = page(DecisionSchema);

export const BreakerStateSchema = z.looseObject({
  name: z.string(),
  scope_key: z.string(),
  state: z.string(),
  latched: z.boolean(),
  reason: z.string(),
  opened_at: IsoDateTime.nullable(),
});
export const BreakersSchema = z.looseObject({ states: z.array(BreakerStateSchema) });

export const NotificationSchema = z.looseObject({
  notification_id: z.string(),
  type: z.string(),
  severity: z.string(),
  created_at: IsoDateTime,
  read_at: IsoDateTime.nullable(),
});
export const NotificationsPageSchema = page(NotificationSchema);

export const NOTIFICATIONS_QUERY_KEY = ['me', 'notifications'] as const;
