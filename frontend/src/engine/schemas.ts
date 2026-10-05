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
  /** `EngineInfo.public()` (TAA-811); optional so older test fixtures still parse. */
  first_seen_at: IsoDateTime.nullable().optional(),
  created_at: IsoDateTime.optional(),
  rotated_at: IsoDateTime.nullable().optional(),
  revoked_at: IsoDateTime.nullable().optional(),
  rotation_pending: z.boolean().optional(),
});
export type EngineSummary = z.infer<typeof EngineSummarySchema>;

/** `GET /engines`: the user's engines (TAA-811). */
export const EngineListSchema = z.object({ items: z.array(EngineSummarySchema) });

/** Nullable number: the engine sends null for a figure it could not measure (never 0). */
const Figure = z.number().nullable();

/** The traded account at the engine's last health step (TAA-904; `AccountSnapshot` in app/sync/heartbeat.py). */
/** A position the bot did not open (a manual MT5 trade), read-only (`ForeignPosition` in app/sync/heartbeat.py). */
export const ForeignPositionSchema = z.object({
  ticket: z.number().int(),
  symbol: z.string(),
  side: z.enum(['BUY', 'SELL']),
  volume: z.number(),
  price_open: z.number(),
  price_current: z.number(),
  sl: z.number().nullable(),
  tp: z.number().nullable(),
  profit: z.number(),
  swap: z.number(),
  opened_at: IsoDateTime,
  magic: z.number().int(),
  comment: z.string(),
  /** Loss if the stop is hit; null: no stop (unknown risk) or not measurable. */
  risk_to_stop: z.number().nullable(),
  /** Whether it counts toward the bot's limits (`risk.foreign_positions_policy`). */
  counted: z.boolean(),
});
export type ForeignPosition = z.infer<typeof ForeignPositionSchema>;

/** The `RiskConfig` fields a trading profile governs (`governed()` in app/risk/limits.py). */
export const GovernedLimitsSchema = z.object({
  risk_per_trade_percent: z.number().positive(),
  total_open_risk_percent: z.number().positive(),
  max_open_positions: z.number().int().positive(),
  max_daily_loss_percent: z.number().positive(),
  min_risk_reward: z.number().positive(),
});
export type GovernedLimits = z.infer<typeof GovernedLimitsSchema>;
export const GOVERNED_FIELDS = [
  'risk_per_trade_percent',
  'total_open_risk_percent',
  'max_open_positions',
  'max_daily_loss_percent',
  'min_risk_reward',
] as const;
export type GovernedField = (typeof GOVERNED_FIELDS)[number];

/**
 * Which limits the engine trades with (TAA-710, `RiskLimits` in app/sync/heartbeat.py): the engine machine's
 * `config.yaml` cage, the owner's trading profile and the stricter of the two per field.
 */
export const RiskLimitsSchema = z.object({
  source: z.enum(['cloud', 'cache', 'local']),
  version: z.string(),
  age_seconds: z.number().int().nonnegative().nullable(),
  cage: GovernedLimitsSchema,
  profile: GovernedLimitsSchema,
  effective: GovernedLimitsSchema,
});
export type RiskLimits = z.infer<typeof RiskLimitsSchema>;

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
  /** Engines from 2026-10-05 on: the counted positions' effective leverage and the manual positions. */
  effective_leverage: z.number().nonnegative().nullable().optional(),
  max_effective_leverage: z.number().positive().nullable().optional(),
  foreign_positions: z.array(ForeignPositionSchema).nullable().optional(),
  /** PAPER only: the real MT5 account next to the simulated book (the two equities differ by design). */
  broker_account: z
    .object({
      currency: z.string(),
      balance: z.number(),
      equity: z.number(),
      margin_free: z.number(),
      leverage: z.number().int(),
    })
    .nullable()
    .optional(),
  /** Engines with TAA-710: the cage, the owner's profile and the effective limits. */
  risk_limits: RiskLimitsSchema.nullable().optional(),
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
