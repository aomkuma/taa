/** Pure helpers of the account page (TAA-921). */
import { type AccountProfile, type Entitlements, FEATURES, LIMITS, RISK_CEILING } from './schemas';

export interface ManualForm {
  equity: string;
  balance: string;
  currency: string;
  leverage: string;
  risk: string;
}

export const formOf = (profile: AccountProfile): ManualForm =>
  profile.source === 'MANUAL'
    ? {
        equity: String(profile.equity ?? ''),
        balance:
          profile.balance !== null && profile.balance !== profile.equity ? String(profile.balance) : '',
        currency: profile.currency,
        leverage: String(profile.leverage ?? ''),
        risk: profile.risk_percent === null ? '' : String(profile.risk_percent),
      }
    : { equity: '', balance: '', currency: 'USD', leverage: '', risk: '' };

/** The problems of a manual form (empty: it can be saved). */
export function manualProblems(form: ManualForm): string[] {
  const positive = (text: string) => text !== '' && Number.isFinite(Number(text)) && Number(text) > 0;
  const problems: string[] = [];
  if (!positive(form.equity)) problems.push('equity');
  if (form.balance !== '' && !positive(form.balance)) problems.push('balance');
  if (!/^[A-Z]{3}$/.test(form.currency)) problems.push('currency');
  if (!positive(form.leverage) || Number(form.leverage) > 3000) problems.push('leverage');
  if (form.risk !== '' && (!positive(form.risk) || Number(form.risk) > RISK_CEILING)) problems.push('risk');
  return problems;
}

/** An override's value: a feature switch, a limit (null: unlimited) or an allow-list. */
export type OverrideValue = boolean | number | string[] | null;

export function overrideKind(key: string): 'feature' | 'limit' | 'allowList' {
  if ((FEATURES as readonly string[]).includes(key)) return 'feature';
  if ((LIMITS as readonly string[]).includes(key)) return 'limit';
  return 'allowList';
}

/** The editor's starting value for *key*: what the user has now (null: no limit, every item allowed). */
export function overrideValueOf(key: string, ent: Entitlements): OverrideValue {
  switch (overrideKind(key)) {
    case 'feature':
      return ent.features[key] ?? false;
    case 'limit':
      return ent.limits[key] ?? null;
    default:
      return key === 'FAMILIES' ? ent.families : ent.asset_classes;
  }
}
