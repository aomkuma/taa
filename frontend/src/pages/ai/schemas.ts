/** The AI review of entries (TAA-1304; app/web/ai.py). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const Value = z.number().nullable();

export const AssessmentSchema = z.object({
  assessment_id: z.string(),
  created_at: z.iso.datetime({ offset: true }),
  symbol: z.string(),
  strategy: z.string(),
  side: z.string(),
  mode: z.string(),
  /** OK REFUSED TRUNCATED INVALID TIMEOUT ERROR BUDGET SKIPPED (app/ai/schema.py `Status`) */
  status: z.string(),
  verdict: z.enum(['AGREE', 'DISAGREE', 'UNSURE']).nullable(),
  confidence: z.number().int().nullable(),
  reasons: z.array(z.string()),
  /** VETOED / PASSED (veto mode) or ADVISORY */
  effect: z.string(),
  model: z.string().nullable(),
  cost_usd: z.number(),
  latency_ms: Value,
  /** The signal's simulated (PLAN shadow) outcome, once closed. */
  outcome: z.object({ win: z.boolean().nullable(), r: Value }).nullable(),
});
export type Assessment = z.infer<typeof AssessmentSchema>;

export const AIAssessmentsSchema = z.object({
  days: z.number().int(),
  summary: z.object({
    calls: z.number().int(),
    answered: z.number().int(),
    unavailable: z.number().int(),
    budget_holds: z.number().int(),
    agree: z.number().int(),
    disagree: z.number().int(),
    unsure: z.number().int(),
    agreement_rate: Value,
    vetoed: z.number().int(),
    passed: z.number().int(),
    advisory: z.number().int(),
    with_outcome: z.number().int(),
    right_rate: Value,
    win_rate_when_agree: Value,
    win_rate_when_disagree: Value,
    cost_usd: z.number(),
    cost_today_usd: z.number(),
    tokens: z.number().int(),
    avg_latency_ms: Value,
    models: z.array(z.string()),
  }),
  items: z.array(AssessmentSchema),
});
export type AIAssessments = z.infer<typeof AIAssessmentsSchema>;

export const aiKeys = {
  list: (engineId: string, days: number) => [...engineKey(engineId), 'ai-assessments', days] as const,
};
