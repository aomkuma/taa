/**
 * The trading profile as the backend resolves it (`TradingProfile.resolve()` in app/advisory/preferences.py;
 * parity in the tests): the style slider interpolates between five anchors, a field in `overrides` replaces
 * the slider's value ("custom"), and the hard ceilings always apply.
 */
import type { EntryPlan, ProfileOverrides, TradingProfile } from '@/pages/watchlists/schemas';

export const ANCHORS = [0, 25, 50, 75, 100] as const;
type Policy = 'IGNORE' | 'PENALIZE' | 'BLOCK';
export type ProfileField = keyof ProfileOverrides;

/** `PROFILE_ANCHORS`. */
export const PROFILE_ANCHORS: Record<ProfileField, readonly (number | boolean | Policy)[]> = {
  risk_per_signal_percent: [0.25, 0.5, 0.75, 1.0, 1.5],
  portfolio_heat_percent: [0.5, 1.0, 2.0, 3.0, 4.0],
  max_positions: [1, 2, 3, 4, 5],
  max_daily_loss_percent: [1.0, 1.5, 2.0, 3.0, 4.0],
  min_rr: [2.5, 2.0, 1.5, 1.3, 1.2],
  min_win_probability: [62.0, 58.0, 55.0, 52.0, 50.0],
  min_supporting_families: [4, 3, 2, 2, 1],
  conflict_policy: ['BLOCK', 'BLOCK', 'PENALIZE', 'PENALIZE', 'IGNORE'],
  require_htf_alignment: [true, true, true, false, false],
};
export const PROFILE_FIELDS = Object.keys(PROFILE_ANCHORS) as ProfileField[];

/** `CEILING_*` of app/config.py that bound the slider (the overrides' field limits match them). */
export const CEILINGS: Partial<Record<ProfileField, number>> = {
  risk_per_signal_percent: 2.0,
  portfolio_heat_percent: 10.0,
  max_daily_loss_percent: 10.0,
};

/** Bounds of the override fields (`ProfileOverrides`); `min_exclusive`: the value must be above `min`. */
export const OVERRIDE_BOUNDS: Partial<
  Record<ProfileField, { min: number; max: number; minExclusive?: boolean }>
> = {
  risk_per_signal_percent: { min: 0, max: 2.0, minExclusive: true },
  portfolio_heat_percent: { min: 0, max: 10.0, minExclusive: true },
  max_positions: { min: 1, max: 20 },
  max_daily_loss_percent: { min: 0, max: 10.0, minExclusive: true },
  min_rr: { min: 1.0, max: 10 },
  min_win_probability: { min: 0, max: 100 },
  min_supporting_families: { min: 1, max: 12 },
};
const INTEGER: ReadonlySet<ProfileField> = new Set(['max_positions', 'min_supporting_families']);

const round = (value: number, digits: number) => Math.round(value * 10 ** digits) / 10 ** digits;

/** `interpolate()`: integers to the defensive side, switches and policies to the more defensive neighbour. */
export function interpolate(field: ProfileField, style: number): number | boolean | Policy {
  const values = PROFILE_ANCHORS[field];
  const s = Math.max(0, Math.min(100, style));
  const i = Math.min(Math.floor(s / 25), ANCHORS.length - 2);
  const lo = values[i];
  const hi = values[i + 1];
  const t = (s - (ANCHORS[i] ?? 0)) / 25;
  if (typeof lo !== 'number' || typeof hi !== 'number') return (t >= 1 ? hi : lo) ?? false;
  const value = lo + (hi - lo) * t;
  if (field === 'max_positions') return Math.floor(round(value, 9));
  if (field === 'min_supporting_families') return Math.ceil(round(value, 9));
  return round(value, 4);
}

export type Resolved = Record<ProfileField, number | boolean | Policy>;

/** `resolve()`: every field's value and the fields that came from overrides. */
export function resolve(profile: TradingProfile): { values: Resolved; custom: Set<ProfileField> } {
  const custom = new Set<ProfileField>();
  const values = {} as Resolved;
  for (const field of PROFILE_FIELDS) {
    const override = profile.overrides[field];
    if (override !== null) {
      values[field] = override;
      custom.add(field);
    } else {
      values[field] = interpolate(field, profile.style);
    }
    const ceiling = CEILINGS[field];
    const value = values[field];
    if (ceiling !== undefined && typeof value === 'number') values[field] = Math.min(value, ceiling);
  }
  return { values, custom };
}

export function setOverride(
  profile: TradingProfile,
  field: ProfileField,
  value: ProfileOverrides[ProfileField],
): TradingProfile {
  return { ...profile, overrides: { ...profile.overrides, [field]: value } };
}

/** Whether an override value is within its field's bounds (switches and policies always are). */
export function overrideValid(field: ProfileField, value: unknown): boolean {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return true;
  const bound = OVERRIDE_BOUNDS[field];
  if (typeof value !== 'number' || !Number.isFinite(value) || bound === undefined) return false;
  if (INTEGER.has(field) && !Number.isInteger(value)) return false;
  return (bound.minExclusive === true ? value > bound.min : value >= bound.min) && value <= bound.max;
}

export type ProfileWarning = 'risk' | 'heat' | 'dailyLoss' | 'rr' | 'conflict' | 'htf' | 'backLoaded';

/** Settings worth a second look: more offensive than the balanced anchor's, or a back-loaded scale-in. */
export function warnings(values: Resolved, plan: EntryPlan): ProfileWarning[] {
  const out: ProfileWarning[] = [];
  const num = (field: ProfileField) => Number(values[field]);
  if (num('risk_per_signal_percent') > 1.0) out.push('risk');
  if (num('portfolio_heat_percent') > 3.0) out.push('heat');
  if (num('max_daily_loss_percent') > 3.0) out.push('dailyLoss');
  if (num('min_rr') < 1.5) out.push('rr');
  if (values.conflict_policy === 'IGNORE') out.push('conflict');
  if (values.require_htf_alignment === false) out.push('htf');
  if (plan.mode === 'SCALE_IN' && plan.weights === 'BACK_LOADED') out.push('backLoaded');
  return out;
}

export type PlanProblem = 'parts' | 'lotUnit' | 'spacing' | 'takeProfits';

/** `EntryPlanPreferences._coherent` and the field bounds. */
export function planProblems(plan: EntryPlan): PlanProblem[] {
  const out: PlanProblem[] = [];
  const single = plan.mode === 'SINGLE';
  if (!Number.isInteger(plan.parts) || plan.parts < (single ? 1 : 2) || plan.parts > (single ? 1 : 5)) {
    out.push('parts');
  }
  if (
    plan.lot_unit !== null &&
    !(Number.isFinite(plan.lot_unit) && plan.lot_unit > 0 && plan.lot_unit <= 100)
  ) {
    out.push('lotUnit');
  }
  if (!(Number.isFinite(plan.spacing_atr) && plan.spacing_atr >= 0.1 && plan.spacing_atr <= 3))
    out.push('spacing');
  if (plan.mode === 'SAME_PRICE') {
    const levels = plan.partial_tp_r;
    const increasing = levels.every(
      (r, i) => r > 0 && Number.isFinite(r) && (i === 0 || r > (levels[i - 1] ?? 0)),
    );
    if (levels.length < plan.parts - 1 || !increasing) out.push('takeProfits');
  }
  return out;
}

/** A mode change keeps the plan valid: SINGLE has one part, the others at least two. */
export function setMode(plan: EntryPlan, mode: EntryPlan['mode']): EntryPlan {
  const parts = mode === 'SINGLE' ? 1 : Math.max(2, plan.parts);
  return { ...plan, mode, parts, partial_tp_r: fillTakeProfits(plan.partial_tp_r, parts) };
}

/** Partial take-profits for *parts*: kept, extended by +1R steps when more parts need them. */
export function fillTakeProfits(levels: readonly number[], parts: number): number[] {
  const out = [...levels];
  while (out.length < parts - 1) out.push((out.at(-1) ?? 0) + 1);
  return out;
}
