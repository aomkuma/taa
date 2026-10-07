/** Manual MT5 trades and the signals they followed (TAA-1006; app/web/manual_trades.py). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

export const LINK_CHOICES = ['CONFIRMED', 'OWN_IDEA', 'SIGNAL'] as const;
export type LinkChoice = (typeof LINK_CHOICES)[number];

export const EffectiveLinkSchema = z.object({
  source: z.enum(['AUTO', 'OWNER']),
  followed: z.boolean(),
  /** The engine's HIGH / LIKELY / UNMATCHED, or the owner's CONFIRMED / OWNER (another signal) / OWN_IDEA. */
  confidence: z.enum(['HIGH', 'LIKELY', 'UNMATCHED', 'CONFIRMED', 'OWNER', 'OWN_IDEA']),
  signal_key: z.string().nullable(),
  strategy: z.string().nullable(),
  decision_id: z.string().nullable(),
  opportunity_id: z.string().nullable(),
});
export type EffectiveLink = z.infer<typeof EffectiveLinkSchema>;

export const ManualTradeSchema = z.object({
  position_id: z.number().int(),
  ticket: z.number().int(),
  symbol: z.string(),
  side: z.enum(['BUY', 'SELL']),
  volume: z.number(),
  price_open: z.number(),
  sl_initial: Value,
  opened_at: IsoDateTime,
  status: z.enum(['OPEN', 'CLOSED']),
  closed_at: IsoDateTime.nullable(),
  close_price: Value,
  net_profit: Value,
  r_multiple: Value,
  auto: z.object({
    confidence: z.enum(['HIGH', 'LIKELY', 'UNMATCHED']),
    strategy: z.string().nullable(),
    decision_id: z.string().nullable(),
    opportunity_id: z.string().nullable(),
    distance_r: Value,
    candidates: z.number().int(),
  }),
  effective: EffectiveLinkSchema,
  /** "Signal vs bot vs me": the signal's PLAN shadow trade and the bot's trade, in R; `bot_source` says
   * whether the bot's trade is its demo/live broker position or its paper position. */
  compare: z.object({
    signal_r: Value,
    signal_status: z.string().nullable(),
    bot_r: Value,
    bot_status: z.string().nullable(),
    bot_source: z.enum(['PAPER', 'DEMO', 'LIVE']).nullable(),
  }),
});
export type ManualTrade = z.infer<typeof ManualTradeSchema>;

export const ManualTradesSchema = z.object({ items: z.array(ManualTradeSchema) });

export const CandidateSchema = z.object({
  signal_key: z.string(),
  strategy: z.string(),
  decision_id: z.string().nullable(),
  opportunity_id: z.string().nullable(),
  entry: z.number(),
  stop: z.number(),
  issued_at: IsoDateTime,
  expires_at: IsoDateTime,
  qualifies: z.boolean(),
  score: Value,
  distance_r: Value,
});
export type Candidate = z.infer<typeof CandidateSchema>;

export const CandidatesSchema = z.object({ items: z.array(CandidateSchema) });

export const manualKeys = {
  all: (engineId: string) => [...engineKey(engineId), 'manual-trades'] as const,
  list: (engineId: string, status: 'OPEN' | 'CLOSED') =>
    [...engineKey(engineId), 'manual-trades', status] as const,
  candidates: (engineId: string, positionId: number) =>
    [...engineKey(engineId), 'manual-trades', 'candidates', positionId] as const,
};

export const manualPath = (engineId: string, rest = '') =>
  `/engines/${encodeURIComponent(engineId)}/manual-trades${rest}`;
