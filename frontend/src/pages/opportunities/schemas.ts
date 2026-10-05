/** Responses of the opportunities page (TAA-809 advisory APIs; TAA-917 list probability and theory counts). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

/** `ProbabilityEstimate` (app/advisory/confidence.py), in percent. */
const EstimateSchema = z.looseObject({
  p: z.number(),
  low: z.number(),
  high: z.number(),
  n: z.number(),
  insufficient: z.boolean(),
  calibration: z.string(),
  source: z.string(),
});

export const ContributionSchema = z.object({
  feature: z.string(),
  family: z.string(),
  detector: z.string(),
  points: z.number(),
});
export type Contribution = z.infer<typeof ContributionSchema>;

/** The win probability for this user's theory selection; the list leaves out the contributions (null). */
export const ProbabilitySchema = z.union([
  z.looseObject({
    available: z.literal(true),
    calibration_version: z.string(),
    estimate: EstimateSchema,
    base_rate: Value,
    contributions: z.array(ContributionSchema).nullable(),
    random_baseline: z.number(),
    break_even: z.number(),
    ev_r: z.number(),
  }),
  z.looseObject({ available: z.literal(false), reason: z.string() }),
]);
export type Probability = z.infer<typeof ProbabilitySchema>;

/** What a list row and the detail share: the owner's sizing and warnings are absent on the market feed. */
const OpportunityBaseSchema = z.looseObject({
  opportunity_id: z.string(),
  server: z.string(),
  strategy: z.string(),
  symbol: z.string(),
  asset_class: z.string(),
  timeframe: z.string(),
  side: z.string(),
  bar_close_at: IsoDateTime,
  created_at: IsoDateTime,
  entry: z.number(),
  stop_loss: z.number(),
  take_profit: Value,
  rr: Value,
  setup_strength: z.number(),
  status: z.string(),
  status_reason: z.string(),
  status_at: IsoDateTime,
  valid_until: IsoDateTime.nullable(),
  valid_reason: z.string(),
  alerted_at: IsoDateTime.nullable(),
  lot: Value.optional(),
  risk_money: Value.optional(),
  reward_money: Value.optional(),
  currency: z.string(),
  warnings: z.array(z.string()).optional(),
  probability: ProbabilitySchema,
});
export type OpportunityFacts = z.infer<typeof OpportunityBaseSchema>;

/** A list row (`brief`): the facts plus the number of supporting and conflicting theories. */
export const OpportunitySchema = OpportunityBaseSchema.extend({
  supporting: z.number().int(),
  conflicting: z.number().int(),
});
export type Opportunity = z.infer<typeof OpportunitySchema>;

export const OpportunitiesPageSchema = z.object({
  items: z.array(OpportunitySchema),
  next_cursor: z.string().nullable(),
});

/** One evidence record of the signal snapshot (`EvidenceRef.to_dict`). */
export const EvidenceRefSchema = z.looseObject({
  relation: z.string(),
  item: z.looseObject({
    age_bars: z.number().optional(),
    evidence: z.looseObject({
      detector_id: z.string(),
      family: z.string(),
      name: z.string(),
      direction: z.string(),
      timeframe: z.string(),
      quality: z.number(),
      tier: z.string().optional(),
      i18n_key: z.string().optional(),
    }),
  }),
});
export type EvidenceRef = z.infer<typeof EvidenceRefSchema>;

const PlanPartSchema = z.looseObject({
  order_type: z.string(),
  entry: z.union([z.string(), z.number()]).nullable(),
  volume: z.union([z.string(), z.number()]),
  risk_money: z.union([z.string(), z.number()]).nullable().optional(),
  taps: z.number().int().optional(),
});

/** `GET /engines/{id}/opportunities/{oid}`. */
export const OpportunityDetailSchema = OpportunityBaseSchema.extend({
  evidence: z.array(EvidenceRefSchema),
  plan: z.array(PlanPartSchema).optional(),
  heat_after: Value.optional(),
  /** The market feed: the opportunity sized for the user's own (MANUAL) account profile. */
  my_sizing: z
    .looseObject({
      available: z.boolean(),
      reason: z.string().nullable().optional(),
      currency: z.string().optional(),
      lot: z.number().optional(),
      risk_money: z.number().optional(),
    })
    .optional(),
});
export type OpportunityDetail = z.infer<typeof OpportunityDetailSchema>;

/** `GET /engines/{id}/theory-scoreboard`: each theory's hypothetical record per (asset class, timeframe). */
export const ScoreboardSchema = z.looseObject({
  hypothetical: z.literal(true),
  items: z.array(
    z.looseObject({
      theory: z.string(),
      level: z.string(),
      group: z.array(z.string()),
      n: z.number().int(),
      hit_rate: z.number(),
      expectancy_r: z.number().nullable(),
    }),
  ),
});
export type Scoreboard = z.infer<typeof ScoreboardSchema>;

export const opportunityKeys = {
  list: (engineId: string) => [...engineKey(engineId), 'opportunities', 'list'] as const,
  detail: (engineId: string, id: string) => [...engineKey(engineId), 'opportunities', 'detail', id] as const,
  scoreboard: (engineId: string) => [...engineKey(engineId), 'opportunities', 'scoreboard'] as const,
};
