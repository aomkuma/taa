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

/** An AI note on advisory (TAA-1305, TAA-1304; `ai_notes`, app/web/ai.py `note_dict`): opinion, not advice. */
export const AINoteSchema = z.object({
  note_id: z.string(),
  /** OPPORTUNITY RANKING ANALYTICS */
  kind: z.string(),
  subject: z.string(),
  created_at: z.iso.datetime({ offset: true }),
  status: z.string(),
  verdict: z.enum(['AGREE', 'DISAGREE', 'UNSURE']).nullable(),
  confidence: z.number().int().nullable(),
  reasons: z.array(z.string()),
  text_en: z.string(),
  text_th: z.string(),
  model: z.string().nullable(),
  cost_usd: z.number(),
});
export type AINote = z.infer<typeof AINoteSchema>;

const VerdictStats = z.object({ n: z.number().int(), win_rate: Value, avg_r: Value });

export const AINotesSchema = z.object({
  kind: z.string(),
  days: z.number().int(),
  cost_usd: z.number(),
  items: z.array(AINoteSchema),
  /** OPPORTUNITY only: accuracy and calibration against the shadow outcomes (simulated). */
  stats: z
    .object({
      judged: z.number().int(),
      right_rate: Value,
      base_win_rate: Value,
      verdicts: z.record(z.string(), VerdictStats),
      brier: Value,
      brier_baseline: Value,
      calibration: z.array(
        z.object({
          low: z.number(),
          high: z.number(),
          n: z.number().int(),
          implied: z.number(),
          observed: z.number(),
        }),
      ),
      simulated: z.boolean(),
    })
    .nullable(),
  /** OPPORTUNITY only: would alerting only AGREE have done better (the opt-in filter's offer). */
  filter: z
    .object({
      n_all: z.number().int(),
      n_kept: z.number().int(),
      avg_r_all: Value,
      avg_r_kept: Value,
      diff: Value,
      ci_low: Value,
      ci_high: Value,
      min_kept: z.number().int(),
      min_all: z.number().int(),
      offered: z.boolean(),
    })
    .nullable(),
});
export type AINotes = z.infer<typeof AINotesSchema>;

export const AI_NOTE_KINDS = ['OPPORTUNITY', 'RANKING', 'ANALYTICS'] as const;
export type AINoteKind = (typeof AI_NOTE_KINDS)[number];

export const aiNoteKeys = {
  list: (engineId: string, kind: AINoteKind, days: number) =>
    [...engineKey(engineId), 'ai-notes', kind, days] as const,
};
