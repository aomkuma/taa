/**
 * Translation-key scheme for backend codes (PLAN §A28). The backend persists stable codes; the PWA maps each to
 * a key and renders it in the user's language.
 *
 * | Backend source                                                    | Key                                |
 * | ----------------------------------------------------------------- | ---------------------------------- |
 * | `Reason` (app/risk/reasons.py), `ReasonCode` (app/strategy)       | `codes:reason.<CODE>`              |
 * | `Gate`, `GateStatus` (app/advisory/suitability.py)                | `codes:gate.<G>`, `codes:gateStatus.<S>` |
 * | `OpportunityStatus`, `WindowReason`, `InvalidReason` (advisory)   | `codes:opportunityStatus.<S>`, `codes:windowReason.<R>`, `codes:invalidReason.<R>` |
 * | `ShadowStatus` (app/advisory/shadow.py)                           | `codes:shadowStatus.<S>`           |
 * | `ExitReason` (app/core/enums.py)                                  | `codes:exitReason.<CODE>`          |
 * | `EngineErrorCode` (app/web/engines.py), engine API errors          | `codes:engine.<code>`              |
 * | `BreakerName` (app/risk/circuit_breaker.py)                       | `codes:breaker.<NAME>`             |
 * | `NotificationType` (app/sync/notifications.py)                    | `codes:notificationType.<TYPE>`    |
 * | `Decision` (app/engine/decision_engine.py)                        | `codes:decision.<D>`               |
 * | `Family` (app/evidence/framework.py), theory families             | `codes:family.<FAMILY>`            |
 * | `IntentState` (app/engine/order_manager.py), DEMO broker orders    | `codes:orderState.<S>`             |
 * | `StrategyState` (app/web/strategies.py)                          | `codes:strategyState.<S>`          |
 * | `QueueStatus` (app/sync/command_queue.py), control commands      | `codes:commandStatus.<S>`          |
 * | strategy names (`name = "..."` in app/strategy), their descriptions | `codes:strategy.<name>`            |
 * | the same strategy names, short display names                     | `codes:strategyName.<name>`        |
 * | `BacktestRunRow.status` (app/storage/models/backtests.py)        | `codes:backtestStatus.<S>`         |
 * | `CommandType`, `Reason` (app/sync/commands.py), control commands | `codes:commandType.<T>`, `codes:commandReason.<R>` |
 * | `KillMode` (app/risk/kill_switch.py)                             | `codes:killMode.<M>`               |
 * | `State`, event actions (app/risk/circuit_breaker.py)             | `codes:breakerState.<S>`, `codes:breakerAction.<A>` |
 * | `Trend`, `Regime`, `VolatilityState`, `Session` (app/core/enums.py) | `codes:trend.<T>`, `codes:regime.<R>`, `codes:volatility.<V>`, `codes:session.<S>` |
 * | explanation keys (app/advisory/explanations.py)                   | `explain:<key>` (see explain.ts)   |
 *
 * Parameterized reason codes arrive as `CODE:detail` (`BREAKER_OPEN:daily_loss`); the key is built from `CODE`
 * and the detail is passed as the `{{detail}}` parameter. A code without a translation renders as the raw code,
 * so nothing is silently hidden. Texts for the `codes` namespace are added with the pages that show them
 * (`locales/<lang>/codes.json`; the engine API errors have theirs already, TAA-811).
 *
 * The code lists below mirror the backend enums; codes.test.ts fails when they drift.
 */
import type { i18n as I18n } from 'i18next';

import { translateDynamic } from './dynamic';

export const REASON_CODES = [
  // Reason (app/risk/reasons.py)
  'KILL_SWITCH_ACTIVE',
  'BREAKER_OPEN',
  'BROKER_UNHEALTHY',
  'STORAGE_UNHEALTHY',
  'CLOCK_UNVERIFIED',
  'ORDERS_NOT_ALLOWED_IN_MODE',
  'LIVE_GATE_FAILED',
  'SYMBOL_NOT_ALLOWED',
  'SYMBOL_UNAVAILABLE',
  'SYMBOL_TRADE_DISABLED',
  'DIRECTION_NOT_ALLOWED',
  'DATA_STALE',
  'DATA_GAPS',
  'DATA_INVALID',
  'SIGNAL_EXPIRED',
  'PRICE_DRIFT',
  'SESSION_CLOSED',
  'MARKET_CLOSED',
  'NEWS_BLACKOUT',
  'SPREAD_TOO_HIGH',
  'SPREAD_TO_SL_TOO_HIGH',
  'EXPECTED_SLIPPAGE_TOO_HIGH',
  'SL_MISSING',
  'TP_MISSING',
  'SL_WRONG_SIDE',
  'SL_TOO_CLOSE',
  'SL_TOO_FAR',
  'RR_TOO_LOW',
  'AI_DISAGREES',
  'AI_LOW_CONFIDENCE',
  'AI_UNAVAILABLE',
  'MAX_OPEN_POSITIONS',
  'MAX_POSITIONS_PER_SYMBOL',
  'CONFLICTING_POSITION',
  'DUPLICATE_SIGNAL',
  'PENDING_INTENT_EXISTS',
  'CORRELATION_LIMIT',
  'CURRENCY_EXPOSURE_LIMIT',
  'MAX_TOTAL_OPEN_RISK',
  'UNKNOWN_POSITION_RISK',
  'FOREIGN_POSITIONS',
  'COOLDOWN_ACTIVE',
  'DAILY_LOSS_LIMIT',
  'WEEKLY_LOSS_LIMIT',
  'MAX_DRAWDOWN',
  'CONSECUTIVE_LOSSES',
  'MARGIN_INSUFFICIENT',
  'MARGIN_LEVEL_TOO_LOW',
  'LEVERAGE_LIMIT',
  'SYMBOL_SPEC_INCONSISTENT',
  'RISK_BELOW_MIN_LOT',
  'VOLUME_INVALID',
  'ORDER_CHECK_FAILED',
  // ReasonCode (app/strategy/signal_models.py), codes not already listed above
  'INSUFFICIENT_DATA',
  'DATA_QUALITY',
  'NO_SETUP',
  'NO_BIAS',
  'REGIME_NOT_TRENDING',
  'OUTSIDE_SESSION',
  'FRIDAY_CUTOFF',
  'NEAR_OPPOSING_LEVEL',
  'CONFLICT',
  'LOWER_RANK',
  'STRATEGY_ERROR',
  'DEMO_UNPROVEN',
] as const;

export const GATES = [
  'G1_TRADABLE',
  'G2_MIN_LOT',
  'G3_MARGIN',
  'G4_COST',
  'G5_STOPS_LEVEL',
  'G6_DATA',
] as const;
export const GATE_STATUSES = ['OK', 'FAIL', 'NOT_EVALUATED'] as const;
export const OPPORTUNITY_STATUSES = ['CANDIDATE', 'ACTIVE', 'EXPIRED', 'INVALIDATED', 'FOLLOWED'] as const;
export const WINDOW_REASONS = ['SIGNAL_LIFETIME', 'SESSION_END', 'NEWS_BLACKOUT'] as const;
export const INVALID_REASONS = ['PRICE_DRIFT', 'SL_TOUCHED', 'SPREAD_SPIKE', 'OPPOSITE_SIGNAL'] as const;
export const SHADOW_STATUSES = ['OPEN', 'CLOSED', 'VOID'] as const;
export const EXIT_REASONS = [
  'TP',
  'SL',
  'BE',
  'TRAIL',
  'TIME',
  'SIGNAL',
  'KILL_SWITCH',
  'MANUAL',
  'STOP_OUT',
  'END_OF_DATA',
] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

// EngineErrorCode (app/web/engines.py): the error codes of the engine management API (PLAN §A32).
export const ENGINE_ERRORS = [
  'invalid_label',
  'invalid_engine_id',
  'owner_not_found',
  'engine_exists',
  'engine_linking_disabled',
  'engine_limit_reached',
  'engine_not_found',
  'engine_revoked',
  'engine_rate_limited',
  'confirmation_mismatch',
  'nothing_to_import',
  'owner_only',
] as const;

// BreakerName (app/risk/circuit_breaker.py), NotificationType (app/sync/notifications.py) and Decision
// (app/engine/decision_engine.py): shown on the dashboard (TAA-904), which added their texts.
export const BREAKER_NAMES = [
  'CONNECTION',
  'ACCOUNT_CHANGE',
  'CLOCK',
  'STORAGE',
  'INVALID_PRICE',
  'SPREAD',
  'STALE_DATA',
  'SLIPPAGE',
  'DAILY_LOSS',
  'WEEKLY_LOSS',
  'MAX_DRAWDOWN',
  'CONSECUTIVE_LOSSES',
  'UNHANDLED_EXCEPTION',
  'ORDER_FAILURES',
  'DUPLICATE_EXECUTION',
  'UNPROTECTED_POSITION',
  'SYMBOL_RESTRICTED',
] as const;
export const NOTIFICATION_TYPES = [
  'ENGINE_OFFLINE',
  'ENGINE_BACK',
  'BACKTEST_FINISHED',
  'OPPORTUNITY',
  'OPPORTUNITY_UPDATE',
  'TEST',
] as const;
export const DECISIONS = ['ACCEPT', 'REJECT', 'HOLD'] as const;
// Family (app/evidence/framework.py): the theory toggles of the charts (TAA-905) and settings (TAA-920).
export const FAMILIES = [
  'FIBONACCI',
  'LEVELS',
  'TREND',
  'CHART_PATTERN',
  'CANDLESTICK',
  'MOMENTUM',
  'VOLATILITY_VOLUME',
  'ICHIMOKU',
  'SMART_MONEY',
  'HARMONIC',
  'ELLIOTT',
  'SESSIONS',
] as const;

// Market context (app/core/enums.py): the symbols page (TAA-906).
export const TRENDS = ['BULLISH', 'BEARISH', 'NEUTRAL'] as const;
export const REGIMES = ['TRENDING', 'RANGING', 'VOLATILE', 'UNCLEAR'] as const;
export const VOLATILITY_STATES = ['LOW', 'NORMAL', 'HIGH', 'EXTREME'] as const;
export const SESSIONS = ['ASIA', 'LONDON', 'NEW_YORK', 'LONDON_NY_OVERLAP', 'OFF'] as const;

// IntentState (app/engine/order_manager.py): DEMO broker order states (TAA-907).
export const ORDER_STATES = [
  'NEW',
  'PRECHECKED',
  'SENDING',
  'FILLED',
  'PARTIAL',
  'REJECTED',
  'UNKNOWN',
  'RECONCILED',
  'NOT_EXECUTED',
  'PROTECTED',
  'UNPROTECTED',
  'EMERGENCY_CLOSED',
] as const;

// The strategies page (TAA-909): StrategyState (app/web/strategies.py), QueueStatus (app/sync/command_queue.py)
// and the strategy catalog (app/strategy/catalog.py: example_strategy.py and setups.py), whose text is the
// strategy's description.
export const STRATEGY_STATES = ['ENABLED', 'DISABLED_REMOTE', 'DISABLED_CONFIG', 'UNKNOWN'] as const;
export const COMMAND_STATUSES = ['QUEUED', 'DELIVERED', 'EXECUTED', 'REJECTED', 'FAILED', 'EXPIRED'] as const;
export const STRATEGY_NAMES = [
  'example_trend_pullback',
  'setup_neckline_break',
  'setup_pattern_breakout',
  'setup_fib_pullback',
  'setup_harmonic_prz',
  'setup_elliott_wave',
  'setup_smc_reversal',
  'setup_breakout',
  'setup_candle_reversal',
] as const;

// Cloud backtest runs (TAA-910): the statuses in the comment of BacktestRunRow.status.
export const BACKTEST_STATUSES = ['QUEUED', 'RUNNING', 'DONE', 'FAILED'] as const;

// Risk & controls (TAA-911): CommandType and the result Reason (app/sync/commands.py, without the empty
// NONE), KillMode (app/risk/kill_switch.py), breaker State and the event actions (app/risk/circuit_breaker.py).
export const COMMAND_TYPES = [
  'KILL_SWITCH_ACTIVATE',
  'STRATEGY_DISABLE',
  'RESYNC',
  'RESCAN_SUITABILITY',
  'POSITION_CLOSE',
  'FLATTEN_ALL',
] as const;
export const COMMAND_REASONS = [
  'INVALID',
  'DUPLICATE',
  'EXPIRED',
  'RISK_INCREASING',
  'NOT_ALLOWED',
  'TOTP_NOT_CONFIGURED',
  'TOTP_INVALID',
  'UNSUPPORTED',
  'HANDLER_ERROR',
] as const;
export const KILL_MODES = ['HALT', 'FLATTEN'] as const;
export const BREAKER_STATES = ['CLOSED', 'OPEN', 'HALF_OPEN'] as const;
export const BREAKER_ACTIONS = ['TRIP', 'HALF_OPEN', 'RESET'] as const;

export const CODE_KINDS = [
  'reason',
  'gate',
  'gateStatus',
  'opportunityStatus',
  'windowReason',
  'invalidReason',
  'shadowStatus',
  'exitReason',
  'engine',
  'breaker',
  'notificationType',
  'decision',
  'family',
  'trend',
  'regime',
  'volatility',
  'session',
  'orderState',
  'strategyState',
  'commandStatus',
  'strategy',
  'strategyName',
  'backtestStatus',
  'commandType',
  'commandReason',
  'killMode',
  'breakerState',
  'breakerAction',
] as const;
export type CodeKind = (typeof CODE_KINDS)[number];

export const CODES_NAMESPACE = 'codes';

export interface ParsedCode {
  code: string;
  detail: string | null;
}

/** Splits `CODE:detail` (the backend's `with_detail`) at the first colon. */
export function parseCode(raw: string): ParsedCode {
  const index = raw.indexOf(':');
  return index < 0
    ? { code: raw, detail: null }
    : { code: raw.slice(0, index), detail: raw.slice(index + 1) };
}

export function codeKey(kind: CodeKind, raw: string): string {
  return `${CODES_NAMESPACE}:${kind}.${parseCode(raw).code}`;
}

/** The text for a backend code, or the raw code when no translation exists yet. */
export function translateCode(i18n: I18n, kind: CodeKind, raw: string): string {
  const key = codeKey(kind, raw);
  if (!i18n.exists(key)) return raw;
  const { detail } = parseCode(raw);
  return translateDynamic(i18n, key, { detail: detail ?? '' });
}
