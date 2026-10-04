import { useTranslation } from 'react-i18next';

import { gaugeFill, type GaugeLevel, gaugeLevel } from './gaugeLevels';

const FILL: Record<GaugeLevel, string> = {
  ok: 'fill-emerald-500',
  warn: 'fill-amber-500',
  danger: 'fill-orange-600',
  breached: 'fill-red-600',
  unknown: 'fill-slate-400',
};

interface Props {
  label: string;
  /** How much of the limit is used, in the limit's unit (null: unknown). */
  used: number | null;
  limit: number;
  /** The figure shown next to the label (e.g. today's P/L). */
  value: string;
  limitText: string;
}

/**
 * A value against its limit (PLAN §A15 dashboard gauges). Drawn with SVG attributes, not inline styles, so it
 * works under the strict CSP.
 */
export function Gauge({ label, used, limit, value, limitText }: Props) {
  const { t } = useTranslation();
  const level = gaugeLevel(used, limit);
  const fill = gaugeFill(used, limit);
  return (
    <div data-level={level}>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span>{label}</span>
        <span className="font-medium tabular-nums">{value}</span>
      </div>
      <svg
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={used ?? undefined}
        aria-valuetext={`${value} (${t('dashboard.limitOf', { limit: limitText })})`}
        viewBox="0 0 100 4"
        preserveAspectRatio="none"
        className="mt-1 h-2 w-full overflow-hidden rounded"
      >
        <rect width="100" height="4" className="fill-slate-200 dark:fill-slate-800" />
        <rect width={fill} height="4" className={FILL[level]} />
      </svg>
      <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
        {t('dashboard.limitOf', { limit: limitText })}
        {level === 'breached' && (
          <span className="ml-1 font-semibold text-red-700">{t('dashboard.limitReached')}</span>
        )}
      </p>
    </div>
  );
}
