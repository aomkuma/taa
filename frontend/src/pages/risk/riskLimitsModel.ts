import { type EntryPlanInUse, GOVERNED_FIELDS, type GovernedField, type RiskLimits } from '@/engine/schemas';
import type { ProfileField } from '@/pages/profile/profileModel';

/** The trading-profile field behind each governed engine limit (`ResolvedProfile.limits()` in Python). */
export const PROFILE_FIELD: Record<GovernedField, ProfileField> = {
  risk_per_trade_percent: 'risk_per_signal_percent',
  total_open_risk_percent: 'portfolio_heat_percent',
  max_open_positions: 'max_positions',
  max_daily_loss_percent: 'max_daily_loss_percent',
  min_risk_reward: 'min_rr',
};

export const PERCENT_FIELDS: ReadonlySet<GovernedField> = new Set([
  'risk_per_trade_percent',
  'total_open_risk_percent',
  'max_daily_loss_percent',
]);

export interface LimitRow {
  field: GovernedField;
  cage: number;
  profile: number;
  effective: number;
  /** The engine machine's `config.yaml` is stricter than the profile, so the profile's value is not used. */
  clamped: boolean;
}

const same = (a: number, b: number) => Math.abs(a - b) < 1e-9;

export function limitRows(limits: RiskLimits): LimitRow[] {
  return GOVERNED_FIELDS.map((field) => {
    const profile = limits.profile[field];
    const effective = limits.effective[field];
    return { field, cage: limits.cage[field], profile, effective, clamped: !same(profile, effective) };
  });
}

/**
 * Whether the engine still trades with other profile values than the saved ones (it pulls about once a
 * minute). *saved*: the resolved values of the saved trading profile.
 */
export function profilePending(limits: RiskLimits, saved: Partial<Record<ProfileField, unknown>>): boolean {
  return GOVERNED_FIELDS.some((field) => {
    const value = saved[PROFILE_FIELD[field]];
    return typeof value === 'number' && !same(value, limits.profile[field]);
  });
}

/** `cloud:<version>` → `cloud` (decision records, TAA-710); null for older records or unknown origins. */
export function riskOrigin(source: string | null | undefined): 'cloud' | 'cache' | 'local' | null {
  const origin = source?.split(':', 1)[0];
  return origin === 'cloud' || origin === 'cache' || origin === 'local' ? origin : null;
}

/** How the bot splits its entries now (TAA-1207): the owner's split plan when the engine follows plans, else
 * one order; `off` when a split plan is saved but the engine machine has entry plans switched off. */
export function planInUse(limits: RiskLimits): {
  key: 'active' | 'single' | 'off' | 'unknown';
  plan: EntryPlanInUse | null;
} {
  const plan = limits.entry_plan && limits.entry_plan.mode !== 'SINGLE' ? limits.entry_plan : null;
  if (limits.entry_plans_enabled === undefined || limits.entry_plans_enabled === null) {
    return { key: 'unknown', plan: null };
  }
  if (!limits.entry_plans_enabled) return { key: plan ? 'off' : 'single', plan: null };
  return plan ? { key: 'active', plan } : { key: 'single', plan: null };
}
