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
import { CommandsPageSchema } from '@/engine/commands';
import { BreakersPageSchema, EngineConfigSchema, KillSwitchPageSchema } from '@/pages/risk/schemas';
import {
  CompareSchema,
  HistorySchema,
  PresetsSchema,
  RunDetailSchema,
  RunsPageSchema,
  TradesSchema,
} from '@/pages/backtests/schemas';

import { DevicesSchema, NotificationListSchema, PreferencesSchema } from '@/pages/notifications/schemas';
import {
  AuditVerifySchema,
  MaskedConfigSchema,
  SessionsSchema,
  SystemStatusSchema,
} from '@/pages/system/schemas';
import { RankingDetailSchema, RankingSchema } from '@/pages/ranking/schemas';
import { PreferencesSchema as AdvisoryPreferencesSchema } from '@/pages/watchlists/schemas';
import {
  OpportunitiesPageSchema,
  OpportunityDetailSchema,
  ScoreboardSchema,
} from '@/pages/opportunities/schemas';
import { AccuracySchema, CalibrationSchema, ShadowTradesSchema } from '@/pages/accuracy/schemas';
import { CatalogSchema, EntitlementsSchema } from '@/pages/theories/schemas';
import samples from './fixtures/api-samples.json';

const E = 'engines/ENGINE/';
// the backtest runs of tests/web/test_api_samples.py
const RUN_A = '0191a0a0-0000-7000-8000-0000000000b1';
const RUN_B = '0191a0a0-0000-7000-8000-0000000000b2';
// the scanner's EURUSD opportunity (tests/web/test_api_samples.py OPP_EUR)
const OPP = 'ebf613a7581b7648eaca8328cdccb599d0751b14ec0d0d451901e2799917e5de';

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
  [`${E}config`, EngineConfigSchema],
  [`${E}kill-switch?limit=20`, KillSwitchPageSchema],
  [`${E}commands?limit=20`, CommandsPageSchema],
  [`${E}breakers?limit=20`, BreakersPageSchema],
  ['me/feed', FeedSchema],
  ['engines', EngineListSchema],
  ['notifications?limit=5', NotificationsPageSchema],
  ['notifications?limit=20', NotificationListSchema],
  ['notifications/preferences', PreferencesSchema],
  ['push/subscriptions', DevicesSchema],
  ['auth/sessions', SessionsSchema],
  [`${E}audit/verify`, AuditVerifySchema],
  [`${E}status`, SystemStatusSchema],
  [`${E}config`, MaskedConfigSchema],
  [`${E}ranking`, RankingSchema],
  [`${E}ranking/XAUUSD`, RankingDetailSchema],
  ['advisory/preferences', AdvisoryPreferencesSchema],
  [`${E}opportunities?limit=50`, OpportunitiesPageSchema],
  [`${E}opportunities/${OPP}`, OpportunityDetailSchema],
  [`${E}opportunities/${OPP}`, SignalSourceSchema],
  [`${E}theory-scoreboard`, ScoreboardSchema],
  [`${E}accuracy`, AccuracySchema],
  [`${E}accuracy?mine=true`, AccuracySchema],
  [`${E}calibration`, CalibrationSchema],
  [`${E}shadow-trades?limit=20`, ShadowTradesSchema],
  ['advisory/detectors', CatalogSchema],
  ['me/entitlements', EntitlementsSchema],
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
