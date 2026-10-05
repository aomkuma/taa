import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { ChartAttribution } from '@/pages/charts/PriceChart';
import { Card } from '@/pages/dashboard/cards';

import { drawdownPoints, equityPoints, HEADLINE, METRICS } from './backtestModel';
import { Limitations, PresetName, RunStatus } from './parts';
import { useMetricText } from './useMetricText';
import { backtestKeys, OPEN_STATUSES, RunDetailSchema, TradesSchema } from './schemas';
import { SeriesChart } from './SeriesChart';

const TRADES_PAGE = 100;
const TH = 'py-1 pr-3 font-normal';
const TD = 'py-1 pr-3 tabular-nums';

function Trades({ engineId, runId }: { engineId: string; runId: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const path = (offset: number) =>
    `/engines/${encodeURIComponent(engineId)}/backtests/${encodeURIComponent(runId)}/trades?offset=${String(offset)}&limit=${String(TRADES_PAGE)}`;
  const trades = useInfiniteQuery({
    queryKey: backtestKeys.trades(engineId, runId),
    queryFn: ({ pageParam, signal }) => apiGet(path(pageParam), TradesSchema, { signal }),
    initialPageParam: 0,
    getNextPageParam: (last) =>
      last.offset + last.items.length < last.stored ? last.offset + last.items.length : undefined,
  });
  const pages = trades.data?.pages ?? [];
  const rows = pages.flatMap((p) => p.items);
  const first = pages[0];
  return (
    <Card title={t('backtests.detail.trades')}>
      {first === undefined ? (
        <p className="text-sm text-slate-500">
          {trades.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">{t('backtests.detail.noTrades')}</p>
      ) : (
        <>
          {first.stored < first.total && (
            <p className="mb-2 text-xs text-slate-500">
              {t('backtests.detail.tradesStored', { stored: first.stored, total: first.total })}
            </p>
          )}
          <div className="overflow-x-auto">
            <table aria-label={t('backtests.detail.trades')} className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className={TH}>{t('backtests.tcol.trade')}</th>
                  <th className={TH}>{t('backtests.tcol.entryExit')}</th>
                  <th className={TH}>{t('backtests.tcol.reason')}</th>
                  <th className={TH}>{t('backtests.tcol.net')}</th>
                  <th className={TH}>R</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((tr) => (
                  <tr key={tr.ticket} className="border-t border-slate-100 align-top dark:border-slate-800">
                    <td className="py-1 pr-3">
                      {tr.symbol} {tr.side} {format.number(tr.volume)}
                      <span className="block text-xs text-slate-500">{tr.strategy}</span>
                    </td>
                    <td className={TD}>
                      {format.dateTime(tr.entry_time)} → {format.dateTime(tr.exit_time)}
                      <span className="block text-xs text-slate-500">
                        {format.number(tr.entry_price, { maximumFractionDigits: 5 })} →{' '}
                        {format.number(tr.exit_price, { maximumFractionDigits: 5 })}
                      </span>
                    </td>
                    <td className="py-1 pr-3">{translateCode(i18n, 'exitReason', tr.exit_reason)}</td>
                    <td className={TD}>{format.number(tr.net, { signDisplay: 'exceptZero' })}</td>
                    <td className={TD}>{format.number(tr.r_multiple, { signDisplay: 'exceptZero' })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {trades.hasNextPage && (
            <button
              type="button"
              disabled={trades.isFetchingNextPage}
              onClick={() => void trades.fetchNextPage()}
              className="mt-3 text-sm underline"
            >
              {t('trades.closed.more')}
            </button>
          )}
        </>
      )}
    </Card>
  );
}

/** One run (PLAN §A15 backtests): headline figures, equity and drawdown, every metric, trades, provenance. */
export function RunDetail({
  engineId,
  runId,
  onBack,
}: {
  engineId: string;
  runId: string;
  onBack: () => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const metricText = useMetricText();
  const detail = useQuery({
    queryKey: backtestKeys.detail(engineId, runId),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/backtests/${encodeURIComponent(runId)}`,
        RunDetailSchema,
        { signal },
      ),
    refetchInterval: (query) =>
      query.state.data && OPEN_STATUSES.has(query.state.data.status) ? 3_000 : false,
  });
  const run = detail.data;
  const equity = useMemo(() => (run ? equityPoints(run.equity) : []), [run]);
  const drawdown = useMemo(() => drawdownPoints(equity), [equity]);

  const back = (
    <button type="button" onClick={onBack} className="mb-3 text-sm underline">
      ← {t('backtests.detail.back')}
    </button>
  );
  if (!run) {
    return (
      <section>
        {back}
        <p className="text-sm text-slate-500">
          {detail.isError ? t('backtests.detail.notFound') : t('dashboard.loading')}
        </p>
      </section>
    );
  }
  const summary = run.summary;
  const metrics = run.metrics ?? null;
  const rejections = Object.entries(summary.rejections ?? {});
  return (
    <section className="space-y-4">
      <div>
        {back}
        <h2 className="text-xl font-semibold">
          <PresetName preset={run.preset} /> · {run.request.symbols.join(', ')}
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t('backtests.detail.meta', {
            start: format.date(run.request.start),
            end: format.date(run.request.end),
            created: format.dateTime(run.created_at),
          })}
          {summary.server && ` · ${summary.server}`} · <RunStatus run={run} />
        </p>
        {run.status === 'FAILED' && (
          <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-400">
            {t('backtests.detail.failed')} {run.error}
          </p>
        )}
        {OPEN_STATUSES.has(run.status) && (
          <p className="mt-2 text-sm text-slate-500">{t('backtests.detail.waiting')}</p>
        )}
      </div>
      {metrics && (
        <>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {HEADLINE.map((key) => (
              <div key={key} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <dt className="text-xs text-slate-500">{t(`backtests.metric.${key}`)}</dt>
                <dd className="text-lg font-semibold tabular-nums">{metricText(key, metrics[key])}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-slate-500">{t('backtests.note')}</p>
        </>
      )}
      {equity.length > 1 && (
        <Card title={t('backtests.detail.curves')}>
          <h3 className="text-sm font-medium">{t('backtests.detail.equity')}</h3>
          <SeriesChart points={equity} kind="equity" label={t('backtests.detail.equity')} precision={2} />
          <h3 className="mt-3 text-sm font-medium">{t('backtests.detail.drawdown')}</h3>
          <SeriesChart
            points={drawdown}
            kind="drawdown"
            label={t('backtests.detail.drawdown')}
            precision={2}
          />
          <ChartAttribution />
        </Card>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {metrics && (
          <Card title={t('backtests.detail.metrics')}>
            <dl>
              {METRICS.map(([key]) => (
                <div
                  key={key}
                  className="flex justify-between gap-3 border-t border-slate-100 py-1 text-sm first:border-0 dark:border-slate-800"
                >
                  <dt className="text-slate-600 dark:text-slate-400">{t(`backtests.metric.${key}`)}</dt>
                  <dd className="tabular-nums">{metricText(key, metrics[key])}</dd>
                </div>
              ))}
            </dl>
          </Card>
        )}
        <div className="space-y-4">
          {run.status === 'DONE' && (
            <Card title={t('backtests.detail.decisions')}>
              <p className="text-sm">
                {t('backtests.detail.signals', {
                  signals: format.number(summary.signals ?? null),
                  accepted: format.number(summary.decisions?.ACCEPT ?? 0),
                  rejected: format.number(summary.decisions?.REJECT ?? 0),
                })}
              </p>
              {rejections.length > 0 && (
                <ul className="mt-2 text-sm">
                  {rejections.map(([code, n]) => (
                    <li key={code} className="flex justify-between gap-3">
                      <span>{translateCode(i18n, 'reason', code)}</span>
                      <span className="tabular-nums">{format.number(n)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
          {summary.provenance && (
            <Card title={t('backtests.detail.provenance')}>
              <dl className="text-sm">
                {(
                  [
                    ['strategies', summary.provenance.strategies?.join(', ')],
                    ['seed', summary.provenance.seed],
                    ['configHash', summary.provenance.config_hash],
                    ['dataHash', summary.provenance.data_hash],
                    ['codeVersion', summary.provenance.code_version],
                  ] as const
                ).map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-3 py-0.5">
                    <dt className="text-slate-600 dark:text-slate-400">{t(`backtests.provenance.${key}`)}</dt>
                    <dd className="break-all text-right font-mono text-xs">{value ?? '—'}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}
          <Limitations />
        </div>
      </div>
      {run.status === 'DONE' && <Trades engineId={engineId} runId={runId} />}
    </section>
  );
}
