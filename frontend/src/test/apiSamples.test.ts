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
  BrokerTradesPageSchema,
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
import { CatalogSchema } from '@/pages/theories/schemas';
import {
  AccountProfileSchema,
  AdminUsersSchema,
  MyEntitlementsSchema,
  PlansSchema,
  UserEntitlementsSchema,
} from '@/pages/account/schemas';
import { AIAssessmentsSchema, AINotesSchema } from '@/pages/ai/schemas';
import { BehaviorSchema, ExpectancySchema, TimingSchema } from '@/pages/learning/schemas';
import { RecommendationsSchema, ReportSchema } from '@/pages/analytics/schemas';
import { CandidatesSchema, ManualTradesSchema } from '@/pages/trades/manualSchemas';
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
  [`${E}broker-trades?limit=50`, BrokerTradesPageSchema],
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
  [`${E}manual-trades?status=OPEN&limit=100`, ManualTradesSchema],
  [`${E}manual-trades?status=CLOSED&limit=100`, ManualTradesSchema],
  [`${E}manual-trades/2078278005/candidates`, CandidatesSchema],
  [`${E}analytics?scope=PAPER&days=366`, ReportSchema],
  [`${E}analytics?scope=SHADOW&days=366`, ReportSchema],
  [`${E}analytics?scope=BACKTEST&days=366&run=${RUN_A}`, ReportSchema],
  [`${E}recommendations?scope=BACKTEST&days=366&run=${RUN_A}`, RecommendationsSchema],
  [`${E}ai-assessments?days=366`, AIAssessmentsSchema],
  [`${E}ai-notes?kind=OPPORTUNITY&days=366`, AINotesSchema],
  [`${E}ai-notes?kind=RANKING&days=366`, AINotesSchema],
  [`${E}learning/timing?scope=SHADOW&days=366`, TimingSchema],
  [`${E}learning/timing?scope=MANUAL&days=366`, TimingSchema],
  [`${E}learning/timing?scope=BACKTEST&days=366&run=${RUN_A}`, TimingSchema],
  [`${E}learning/expectancy?scope=SHADOW&days=183`, ExpectancySchema],
  [`${E}learning/behavior?days=366`, BehaviorSchema],
  ['advisory/detectors', CatalogSchema],
  ['me/entitlements', MyEntitlementsSchema],
  ['me/account-profile', AccountProfileSchema],
  ['admin/users', AdminUsersSchema],
  ['admin/plans', PlansSchema],
  ['admin/users/USER/entitlements', UserEntitlementsSchema],
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
