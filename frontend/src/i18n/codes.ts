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
 * | explanation keys (app/advisory/explanations.py)                   | `explain:<key>` (see explain.ts)   |
 *
 * Parameterized reason codes arrive as `CODE:detail` (`BREAKER_OPEN:daily_loss`); the key is built from `CODE`
 * and the detail is passed as the `{{detail}}` parameter. A code without a translation renders as the raw code,
 * so nothing is silently hidden. Texts for the `codes` namespace are added with the pages that show them.
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

export const CODE_KINDS = [
  'reason',
  'gate',
  'gateStatus',
  'opportunityStatus',
  'windowReason',
  'invalidReason',
  'shadowStatus',
  'exitReason',
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
