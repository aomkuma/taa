/** API schemas of the engine the shell reads (PLAN §A14, §A32). Nested objects are loose: pages add fields. */
import { z } from 'zod';

const IsoDateTime = z.iso.datetime({ offset: true });

/** `GET /me/feed`: the user's own engine (`own`), the owner's market feed, or none. */
export const FeedSchema = z.object({
  engine_id: z.string().nullable(),
  own: z.boolean(),
});
export type Feed = z.infer<typeof FeedSchema>;

export const EngineSummarySchema = z.looseObject({
  engine_id: z.string(),
  label: z.string(),
  status: z.string(),
  last_seen_at: IsoDateTime.nullable(),
});
export type EngineSummary = z.infer<typeof EngineSummarySchema>;

/** `GET /engines`: the user's engines (TAA-811). */
export const EngineListSchema = z.object({ items: z.array(EngineSummarySchema) });

/** Nullable number: the engine sends null for a figure it could not measure (never 0). */
const Figure = z.number().nullable();

/** The traded account at the engine's last health step (TAA-904; `AccountSnapshot` in app/sync/heartbeat.py). */
export const AccountSnapshotSchema = z.looseObject({
  as_of: IsoDateTime,
  backend: z.string(),
  currency: z.string(),
  balance: Figure,
  equity: Figure,
  margin: Figure,
  margin_free: Figure,
  day_pnl: Figure,
  day_pnl_percent: Figure,
  week_pnl: Figure,
  week_pnl_percent: Figure,
  drawdown_percent: Figure,
  open_risk: Figure,
  heat_percent: Figure,
  unknown_risk_positions: z.number().int().nonnegative(),
  consecutive_losses: z.number().int().nonnegative(),
  limits: z.looseObject({
    daily_loss_percent: z.number().positive(),
    weekly_loss_percent: z.number().positive(),
    drawdown_percent: z.number().positive(),
    heat_percent: z.number().positive(),
    consecutive_losses: z.number().int().positive(),
  }),
});
export type AccountSnapshot = z.infer<typeof AccountSnapshotSchema>;

/**
 * The engine's newest heartbeat (TAA-705), as `GET /engines/{id}/status` returns it and as the stream sends it
 * (`status`/`heartbeat`). `received_at` is on the cloud clock.
 */
export const HeartbeatSchema = z.looseObject({
  at: IsoDateTime,
  received_at: IsoDateTime,
  mode: z.string(),
  state: z.enum(['running', 'stopped']),
  connected: z.boolean(),
  clock_verified: z.boolean(),
  kill_switch: z.boolean(),
  market_open: z.boolean(),
  market_change_at: IsoDateTime.nullable(),
  open_positions: z.number().int().nonnegative().optional(),
  outbox_pending: z.number().int().nonnegative().nullable().optional(),
  /** Absent from heartbeats of engines older than TAA-904. */
  account: AccountSnapshotSchema.nullable().optional(),
});
export type Heartbeat = z.infer<typeof HeartbeatSchema>;

/** `GET /engines/{id}/status` (TAA-803). */
export const EngineStatusSchema = z.looseObject({
  engine: EngineSummarySchema,
  run: z.looseObject({ mode: z.string(), status: z.string(), started_at: IsoDateTime }).nullable(),
  last_received_at: IsoDateTime.nullable(),
  kill_switch: z.looseObject({ active: z.boolean() }),
  open_breakers: z.number().int(),
  open_positions: z.number().int(),
  heartbeat: HeartbeatSchema.nullable(),
});
export type EngineStatus = z.infer<typeof EngineStatusSchema>;

/** Query keys. Everything under `engineKey(id)` is refetched when the live stream asks for a resync. */
export const FEED_QUERY_KEY = ['me', 'feed'] as const;
export const ENGINES_QUERY_KEY = ['me', 'engines'] as const;
export const engineKey = (engineId: string) => ['engine', engineId] as const;
export const engineStatusKey = (engineId: string) => ['engine', engineId, 'status'] as const;
