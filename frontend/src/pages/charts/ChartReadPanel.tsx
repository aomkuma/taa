import { useTranslation } from 'react-i18next';

import { useFormat } from '@/i18n/useFormat';

import type { ChartRead } from './schemas';

/**
 * The bot's read of the shown timeframe in words (TAA-L813): its structure and invalidation, how deep the
 * price sits in the last leg, the events at its levels and the two scenarios at the level being tested.
 * No probabilities: the read describes the chart, it does not predict it.
 */
export function ChartReadPanel({ read, failed }: { read: ChartRead | null | undefined; failed: boolean }) {
  const { t } = useTranslation();
  const format = useFormat();
  if (failed || !read) {
    return <p className="mb-1 text-xs text-slate-500">{t('charts.read.unavailable')}</p>;
  }
  const price = (value: number | null) =>
    format.number(value, { minimumFractionDigits: read.digits, maximumFractionDigits: read.digits });
  const dir = (direction: number) => t(direction > 0 ? 'charts.read.dir.up' : 'charts.read.dir.down');
  const retrace = read.leg?.retrace ?? null;
  return (
    <div
      className="mb-2 rounded border border-slate-300 p-2 text-xs dark:border-slate-700"
      aria-label={t('charts.read.title')}
    >
      <p className="font-medium">
        {t('charts.read.structure', {
          tf: read.timeframe,
          structure: t(`charts.read.structures.${read.structure}`),
        })}
        {read.invalidation !== null &&
          ` · ${t(read.structure === 'DOWN' ? 'charts.read.endsAbove' : 'charts.read.endsBelow', {
            price: price(read.invalidation),
          })}`}
        {read.broken && ` · ${t('charts.read.broken')}`}
        {retrace !== null &&
          ` · ${t('charts.read.retrace', { pct: format.number(retrace * 100, { maximumFractionDigits: 0 }) })}`}
      </p>
      {read.scenarios.length > 0 && (
        <ul className="mt-1 list-disc pl-4">
          {read.scenarios.map((s) => (
            <li key={`${s.kind}:${String(s.direction)}`}>
              {t(`charts.read.scenario.${s.kind}_${s.direction > 0 ? 'up' : 'down'}`, {
                trigger: price(s.trigger),
                target: price(s.target),
              })}
            </li>
          ))}
        </ul>
      )}
      {read.events.length > 0 && (
        <p className="mt-1">
          {read.events
            .map((e) =>
              t(`charts.read.event.${e.kind}`, {
                dir: dir(e.direction),
                price: price(e.price),
                where: e.trendline ? t('charts.read.onTrendline') : '',
              }),
            )
            .join(' · ')}
        </p>
      )}
      <p className="mt-1 text-slate-500">{t('charts.read.legend')}</p>
    </div>
  );
}
