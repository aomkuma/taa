/** Responses of the signals & decisions page (TAA-803 decisions, TAA-908 reason filter). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

export const DecisionRowSchema = z.looseObject({
  decision_id: z.string(),
  created_at: IsoDateTime,
  strategy: z.string(),
  symbol: z.string(),
  timeframe: z.string(),
  action: z.string(),
  profile: z.string(),
  decision: z.string(),
  reason_codes: z.array(z.string()),
  warnings: z.array(z.string()),
  volume: Value,
  risk_money: Value,
  entry_price: Value,
  stop_loss: Value,
  take_profit: Value,
});
export type DecisionRow = z.infer<typeof DecisionRowSchema>;

export const DecisionLogSchema = z.object({
  items: z.array(DecisionRowSchema),
  next_cursor: z.string().nullable(),
});

/** A check's value and threshold are whatever the rule measured: a number, a text or nothing. */
const Measured = z.union([z.number(), z.string(), z.boolean()]).nullable();

export const CheckSchema = z.looseObject({
  seq: z.number().int(),
  name: z.string(),
  reason: z.string(),
  passed: z.boolean(),
  kind: z.string(),
  value: Measured,
  threshold: Measured,
  detail: z.string(),
});
export type Check = z.infer<typeof CheckSchema>;

const ConditionSchema = z.looseObject({ name: z.string(), passed: z.boolean() });

/** `GET /engines/{id}/decisions/{id}`: the row, its signal document and every check in order. */
export const DecisionDetailSchema = DecisionRowSchema.extend({
  signal: z.looseObject({
    score: z.number(),
    setup_strength: z.number().nullable().optional(),
    conditions: z.array(ConditionSchema),
    reason_codes: z.array(z.string()),
    explanation: z.string().optional(),
  }),
  checks: z.array(CheckSchema),
});
export type DecisionDetail = z.infer<typeof DecisionDetailSchema>;

export interface DecisionFilters {
  decision: string;
  profile: string;
  symbol: string;
  reason: string;
}

export const decisionKeys = {
  log: (engineId: string, filters: DecisionFilters) =>
    [...engineKey(engineId), 'decisions', 'log', filters] as const,
  // not 'detail': the symbols page caches the same route under that key with another schema
  detail: (engineId: string, decisionId: string) =>
    [...engineKey(engineId), 'decisions', 'checks', decisionId] as const,
};
