import { useTranslation } from 'react-i18next';

import type { GovernedField, RiskLimits } from '@/engine/schemas';
import { useFormat } from '@/i18n/useFormat';

import { limitRows, PERCENT_FIELDS } from './riskLimitsModel';

/**
 * The limits the engine trades with (TAA-924, PLAN §A33): the engine machine's `config.yaml`, the owner's
 * trading profile and the stricter of the two, with where the profile came from.
 */
export function EngineLimits({ limits }: { limits: RiskLimits }) {
  const { t } = useTranslation();
  const format = useFormat();
  const value = (field: GovernedField, v: number) =>
    PERCENT_FIELDS.has(field)
      ? format.percent(v, { maximumFractionDigits: 2 })
      : field === 'min_risk_reward'
        ? format.number(v, { maximumFractionDigits: 2 })
        : format.number(v);
  const minutes = limits.age_seconds === null ? null : Math.round(limits.age_seconds / 60);
  return (
    <div>
      <table aria-label={t('riskLimits.title')} className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="py-1 pr-3 font-normal">{t('riskLimits.col.limit')}</th>
            <th className="py-1 pr-3 font-normal">{t('riskLimits.col.profile')}</th>
            <th className="py-1 pr-3 font-normal">{t('riskLimits.col.cage')}</th>
            <th className="py-1 font-normal">{t('riskLimits.col.effective')}</th>
          </tr>
        </thead>
        <tbody>
          {limitRows(limits).map((r) => (
            <tr key={r.field} className="border-t border-slate-100 dark:border-slate-800">
              <th scope="row" className="py-1 pr-3 text-left font-normal">
                {t(`riskLimits.field.${r.field}`)}
              </th>
              <td className="py-1 pr-3 tabular-nums">{value(r.field, r.profile)}</td>
              <td className="py-1 pr-3 tabular-nums">{value(r.field, r.cage)}</td>
              <td className="py-1 tabular-nums">
                <span className="font-semibold">{value(r.field, r.effective)}</span>
                {r.clamped && (
                  <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
                    {t('riskLimits.clamped')}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
        {t(`riskLimits.source.${limits.source}`)}
        {minutes !== null && ` · ${t('riskLimits.age', { n: format.number(minutes) })}`}
      </p>
      <p className="mt-1 text-xs text-slate-500">{t('riskLimits.explain')}</p>
    </div>
  );
}
