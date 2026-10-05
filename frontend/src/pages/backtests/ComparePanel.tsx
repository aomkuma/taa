import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { ApiError, apiGet } from '@/api/client';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { METRICS } from './backtestModel';
import { Limitations, PresetName } from './parts';
import { useMetricText } from './useMetricText';
import { backtestKeys, CompareSchema } from './schemas';

/** 2–4 finished runs side by side: what was asked (preset, symbols, period) and every metric. */
export function ComparePanel({
  engineId,
  ids,
  onBack,
}: {
  engineId: string;
  ids: string;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const metricText = useMetricText();
  const compare = useQuery({
    queryKey: backtestKeys.compare(engineId, ids),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/backtests/compare?ids=${encodeURIComponent(ids)}`,
        CompareSchema,
        { signal },
      ),
  });
  const runs = compare.data?.runs ?? [];
  const failure =
    compare.error instanceof ApiError && compare.error.code === 'backtest_not_finished'
      ? t('backtests.compare.notFinished')
      : t('dashboard.loadFailed');
  return (
    <section className="space-y-4">
      <button type="button" onClick={onBack} className="text-sm underline">
        ← {t('backtests.detail.back')}
      </button>
      <Card title={t('backtests.compare.title')}>
        {compare.isError ? (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {failure}
          </p>
        ) : runs.length === 0 ? (
          <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table aria-label={t('backtests.compare.title')} className="w-full text-sm">
              <thead>
                <tr className="text-left align-bottom">
                  <th className="py-1 pr-3 font-normal text-slate-500">{t('backtests.compare.metric')}</th>
                  {runs.map((r) => (
                    <th key={r.run_id} scope="col" className="py-1 pr-3 font-semibold">
                      <PresetName preset={r.preset} />
                      <span className="block text-xs font-normal text-slate-500">
                        {r.request.symbols.join(', ')} · {format.date(r.request.start)} –{' '}
                        {format.date(r.request.end)}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRICS.map(([key]) => (
                  <tr key={key} className="border-t border-slate-100 dark:border-slate-800">
                    <th
                      scope="row"
                      className="py-1 pr-3 text-left font-normal text-slate-600 dark:text-slate-400"
                    >
                      {t(`backtests.metric.${key}`)}
                    </th>
                    {runs.map((r) => (
                      <td key={r.run_id} className="py-1 pr-3 tabular-nums">
                        {metricText(key, r.metrics?.[key] ?? null)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-xs text-slate-500">{t('backtests.note')}</p>
      </Card>
      <Limitations />
    </section>
  );
}
