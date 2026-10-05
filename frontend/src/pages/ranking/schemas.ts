/** Responses of the symbol ranking page (TAA-809 advisory APIs, TAA-916 list summary and account header). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

/** A gate result (`snapshot_payload` in app/advisory/ranking_service.py); `key` is an `explain:` key. */
export const GateSchema = z.object({
  gate: z.string(),
  status: z.string(),
  key: z.string(),
  params: z.record(z.string(), z.unknown()),
});
export type GateResult = z.infer<typeof GateSchema>;

/** The account the ranking was sized for: the engine's (owner) or the user's own profile (market feed). */
export const RankingAccountSchema = z.looseObject({
  equity: Value.optional(),
  balance: Value.optional(),
  leverage: Value.optional(),
  currency: z.string().nullable().optional(),
  risk_percent: Value.optional(),
  source: z.string().optional(),
});
export type RankingAccount = z.infer<typeof RankingAccountSchema>;

/** The user's own affordability on the market feed (TAA-8A4 `personal_ranking`). */
const PersonalSchema = z.looseObject({
  eligible: z.boolean().nullable(),
  reason: z.string().optional(),
  currency: z.string().nullable(),
  affordable: z.boolean().optional(),
  risk_budget: Value.optional(),
  lot: Value.optional(),
  min_lot_risk: Value.optional(),
  required_equity: Value.optional(),
});

export const RankingItemSchema = z.looseObject({
  symbol: z.string(),
  asset_class: z.string(),
  rank: z.number().int(),
  eligible: z.boolean(),
  overall: z.number(),
  now_score: z.number(),
  failed_gates: z.array(z.string()),
  computed_at: IsoDateTime,
  market_open: z.boolean().nullable(),
  flags: z.array(z.string()),
  /** The gates that did not pass (FAIL or NOT_EVALUATED); the feed leaves out the account gates. */
  gates: z.array(GateSchema),
  /** The owner's sizing (empty on the feed). */
  metrics: z.object({
    currency: z.string().nullable().optional(),
    lot: Value.optional(),
    risk_money: Value.optional(),
    min_lot_risk: Value.optional(),
    required_equity: Value.optional(),
  }),
  personal: PersonalSchema.optional(),
});
export type RankingItem = z.infer<typeof RankingItemSchema>;

/** `GET /engines/{id}/ranking`. */
export const RankingSchema = z.object({
  computed_at: IsoDateTime.nullable(),
  personal: z.boolean().optional(),
  /** Symbols in the engine's universe; a run after a restart ranks fewer until all are measured. */
  universe: z.number().int().nullable().optional(),
  account: RankingAccountSchema.nullable(),
  items: z.array(RankingItemSchema),
});
export type Ranking = z.infer<typeof RankingSchema>;

const SessionSchema = z.looseObject({
  open: z.boolean(),
  active: z.array(z.string()),
  ends_at: IsoDateTime.nullable(),
  next_open: IsoDateTime.nullable(),
});

/** `GET /engines/{id}/ranking/{symbol}`: the row with its whole payload (older rows carry only the scores). */
export const RankingDetailSchema = z.looseObject({
  symbol: z.string(),
  asset_class: z.string(),
  rank: z.number().int(),
  eligible: z.boolean(),
  overall: z.number(),
  now_score: z.number(),
  computed_at: IsoDateTime,
  failed_gates: z.array(z.string()),
  payload: z.looseObject({
    scores: z.record(z.string(), z.number()),
    flags: z.array(z.string()).optional(),
    gates: z.array(GateSchema).optional(),
    metrics: z.record(z.string(), z.union([z.number(), z.string(), z.null()])).optional(),
    session: SessionSchema.nullable().optional(),
    best_hours_utc: z.array(z.string()).optional(),
    correlation: Value.optional(),
    correlated_with: z.string().nullable().optional(),
    side: z.string().optional(),
  }),
});
export type RankingDetail = z.infer<typeof RankingDetailSchema>;

export const rankingKeys = {
  list: (engineId: string) => [...engineKey(engineId), 'ranking', 'list'] as const,
  detail: (engineId: string, symbol: string) =>
    [...engineKey(engineId), 'ranking', 'detail', symbol] as const,
};
