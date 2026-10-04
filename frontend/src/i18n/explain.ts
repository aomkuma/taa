/**
 * Advisory explanations (app/advisory/explanations.py). Results carry a key and parameters; the text is rendered
 * here in the user's language. Money parameters get two decimals, like the backend's `explain()`, but with
 * locale-aware grouping. An unknown key renders as itself, matching the backend.
 */
import type { i18n as I18n } from 'i18next';

import { translateDynamic } from './dynamic';
import { formatNumber } from './format';
import { DEFAULT_LANGUAGE, isLanguage } from './languages';

/** Mirrors `MONEY_PARAMS` in app/advisory/explanations.py (checked by explain.test.ts). */
export const MONEY_PARAMS: ReadonlySet<string> = new Set([
  'min_lot_risk',
  'budget',
  'required_equity',
  'cap',
  'margin',
  'available',
]);

export type ExplainParams = Readonly<Record<string, string | number>>;

export function explainKey(key: string): string {
  return `explain:${key}`;
}

export function explain(i18n: I18n, key: string, params: ExplainParams = {}): string {
  const fullKey = explainKey(key);
  if (!i18n.exists(fullKey)) return key;
  const language = isLanguage(i18n.language) ? i18n.language : DEFAULT_LANGUAGE;
  const values: Record<string, string> = {};
  for (const [name, value] of Object.entries(params)) {
    if (typeof value !== 'number') {
      values[name] = value;
    } else if (MONEY_PARAMS.has(name)) {
      values[name] = formatNumber(value, language, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else {
      values[name] = formatNumber(value, language);
    }
  }
  return translateDynamic(i18n, fullKey, values);
}
