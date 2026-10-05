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

import {
  OrderIntentsPageSchema,
  PaperIntentsPageSchema,
  TradeDetailSchema,
  TradesPageSchema,
} from '@/pages/trades/schemas';

import { DecisionDetailSchema, DecisionLogSchema } from '@/pages/decisions/schemas';
import { StrategiesSchema } from '@/pages/strategies/schemas';
import {
  CompareSchema,
  HistorySchema,
  PresetsSchema,
  RunDetailSchema,
  RunsPageSchema,
  TradesSchema,
} from '@/pages/backtests/schemas';

import samples from './fixtures/api-samples.json';

const E = 'engines/ENGINE/';
// the backtest runs of tests/web/test_api_samples.py
const RUN_A = '0191a0a0-0000-7000-8000-0000000000b1';
const RUN_B = '0191a0a0-0000-7000-8000-0000000000b2';

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
  [`${E}trades?limit=2`, TradesPageSchema],
  [`${E}positions?status=OPEN`, TradesPageSchema],
  [`${E}trades/1`, TradeDetailSchema],
  [`${E}intents?kind=paper`, PaperIntentsPageSchema],
  [`${E}intents?kind=broker`, OrderIntentsPageSchema],
  [`${E}decisions?limit=50&profile=EXECUTION`, DecisionLogSchema],
  [`${E}decisions/d1`, DecisionDetailSchema],
  [`${E}strategies`, StrategiesSchema],
  [`${E}strategies?days=7`, StrategiesSchema],
  [`${E}backtests`, RunsPageSchema],
  [`${E}backtests/${RUN_A}`, RunDetailSchema],
  [`${E}backtests/${RUN_A}/trades?limit=3`, TradesSchema],
  [`${E}backtests/compare?ids=${RUN_A},${RUN_B}`, CompareSchema],
  [`${E}backtests/history`, HistorySchema],
  ['backtests/presets', PresetsSchema],
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
