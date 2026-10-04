/**
 * Real API responses (recorded by tests/web/test_api_samples.py) must pass the schemas the pages use. A fake in
 * a component test can drift from the API; these samples cannot.
 */
import type { z } from 'zod';

import { EngineListSchema, EngineStatusSchema, FeedSchema } from '@/engine/schemas';
import { CandlesSchema, SignalSourceSchema, SymbolsSchema } from '@/pages/charts/schemas';
import {
  BreakersSchema,
  DecisionsPageSchema,
  NotificationsPageSchema,
  PositionsPageSchema,
} from '@/pages/dashboard/schemas';
import {
  DecisionMarketSchema,
  DecisionRefsSchema,
  QuotesSchema,
  SymbolDetailSchema,
} from '@/pages/symbols/schemas';

import samples from './fixtures/api-samples.json';

const E = 'engines/ENGINE/';

const CASES: [string, z.ZodType][] = [
  [`${E}status`, EngineStatusSchema],
  [`${E}quotes`, QuotesSchema],
  [`${E}symbols`, SymbolsSchema],
  [`${E}symbols/EURUSD`, SymbolDetailSchema],
  [`${E}candles?symbol=EURUSD&limit=5&overlays=ema:5,rsi:5&zones=true`, CandlesSchema],
  [`${E}positions?status=OPEN`, PositionsPageSchema],
  [`${E}decisions?limit=2`, DecisionsPageSchema],
  [`${E}decisions?limit=2`, DecisionRefsSchema],
  [`${E}decisions/d1`, DecisionMarketSchema],
  [`${E}decisions/d1`, SignalSourceSchema],
  [`${E}breakers?limit=1`, BreakersSchema],
  ['me/feed', FeedSchema],
  ['engines', EngineListSchema],
  ['notifications?limit=5', NotificationsPageSchema],
];

const recorded = samples as Record<string, unknown>;

describe('recorded API samples pass the page schemas', () => {
  it.each(CASES)('%s', (route, schema) => {
    expect(route in recorded, `no sample for ${route}`).toBe(true);
    const result = schema.safeParse(recorded[route]);
    expect(result.success ? [] : result.error.issues).toEqual([]);
  });

  it('covers every recorded route', () => {
    expect(Object.keys(recorded).sort()).toEqual([...new Set(CASES.map(([route]) => route))].sort());
  });
});
