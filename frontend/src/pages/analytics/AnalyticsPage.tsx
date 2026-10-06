import { useQuery, useQueryClient } from '@tanstack/react-query';
import { lazy, Suspense, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ApiError, apiGet, apiPost } from '@/api/client';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { backtestKeys, RunSchema, RunsPageSchema } from '@/pages/backtests/schemas';
import { Card } from '@/pages/dashboard/cards';
import { AINarrative } from '@/pages/ai/AINotes';

import { backtestPeriod, curvePoints, histogramShares } from './analyticsModel';
import {
  type AnalyticsQuery,
  analyticsKeys,
  DAYS,
  type Dimension,
  DIMENSIONS,
  queryString,
  type Recommendation,
  RecommendationsSchema,
  type Report,
  ReportSchema,
  SCOPES,
} from './schemas';

// the chart library is large: it loads only when there is a curve to draw
const SeriesChart = lazy(async () => ({
  default: (await import('@/pages/backtests/SeriesChart')).SeriesChart,
}));

const SELECT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';

function Field({ label, children }: { label: string; children: (id: string) => React.ReactNode }) {
  const id = useId();
  return (
    <span className="flex items-center gap-1.5 text-sm">
      <label htmlFor={id}>{label}</label>
      {children(id)}
    </span>
  );
}

function ScopeBar({ query, onChange }: { query: AnalyticsQuery; onChange: (q: AnalyticsQuery) => void }) {
  const { t } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const runs = useQuery({
    queryKey: backtestKeys.list(id),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(id)}/backtests`, RunsPageSchema, { signal }),
    enabled: query.scope === 'BACKTEST' && engineId !== null,
  });
  const done = (runs.data?.items ?? []).filter((r) => r.status === 'DONE');
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <Field label={t('analytics.scope.label')}>
        {(fid) => (
          <select
            id={fid}
            value={query.scope}
            onChange={(e) => {
              onChange({ ...query, scope: e.target.value as AnalyticsQuery['scope'] });
            }}
            className={SELECT}
          >
            {SCOPES.map((s) => (
              <option key={s} value={s}>
                {t(`analytics.scope.${s}`)}
              </option>
            ))}
          </select>
        )}
      </Field>
      {query.scope === 'SHADOW' && (
        <Field label={t('analytics.variant.label')}>
          {(fid) => (
            <select
              id={fid}
              value={query.variant}
              onChange={(e) => {
                onChange({ ...query, variant: e.target.value as AnalyticsQuery['variant'] });
              }}
              className={SELECT}
            >
              <option value="PLAN">{t('analytics.variant.PLAN')}</option>
              <option value="MANAGED">{t('analytics.variant.MANAGED')}</option>
            </select>
          )}
        </Field>
      )}
      {query.scope === 'BACKTEST' ? (
        <Field label={t('analytics.run')}>
          {(fid) => (
            <select
              id={fid}
              value={query.run ?? ''}
              onChange={(e) => {
                onChange({ ...query, run: e.target.value || null });
              }}
              className={SELECT}
            >
              <option value="">{t('analytics.pickRun')}</option>
              {done.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {format.dateTime(r.created_at)} · {r.preset}
                </option>
              ))}
            </select>
          )}
        </Field>
      ) : (
        <Field label={t('analytics.days.label')}>
          {(fid) => (
            <select
              id={fid}
              value={query.days}
              onChange={(e) => {
                onChange({ ...query, days: Number(e.target.value) });
              }}
              className={SELECT}
            >
              {DAYS.map((d) => (
                <option key={d} value={d}>
                  {t('analytics.days.n', { n: d })}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}
    </div>
  );
}

function Kpis({ report }: { report: Report }) {
  const { t } = useTranslation();
  const format = useFormat();
  const k = report.kpis;
  const r = (v: number | null) =>
    v === null ? '—' : `${format.number(v, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}R`;
  const tiles: [string, string][] = [
    [t('analytics.kpi.trades'), format.number(k.trades)],
    [
      t('analytics.kpi.winRate'),
      k.win_rate === null ? '—' : format.percent(k.win_rate * 100, { maximumFractionDigits: 1 }),
    ],
    [t('analytics.kpi.expectancy'), r(k.expectancy_r)],
    [t('analytics.kpi.netR'), r(k.net_r)],
    [t('analytics.kpi.profitFactor'), format.number(k.profit_factor, { maximumFractionDigits: 2 })],
    [t('analytics.kpi.maxDrawdown'), r(k.max_drawdown_r === null ? null : -k.max_drawdown_r)],
    [t('analytics.kpi.sharpe'), format.number(k.sharpe, { maximumFractionDigits: 2 })],
    [t('analytics.kpi.sortino'), format.number(k.sortino, { maximumFractionDigits: 2 })],
    [
      t('analytics.kpi.hold'),
      k.avg_hold_minutes === null
        ? '—'
        : t('trades.duration', {
            h: Math.floor(k.avg_hold_minutes / 60),
            m: Math.round(k.avg_hold_minutes % 60),
          }),
    ],
  ];
  return (
    <dl
      aria-label={t('analytics.kpi.title')}
      className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5"
    >
      {tiles.map(([label, value]) => (
        <div key={label} className="rounded border border-slate-200 p-2 dark:border-slate-800">
          <dt className="text-xs text-slate-500">{label}</dt>
          <dd className="text-lg font-semibold tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Histogram({ report }: { report: Report }) {
  const { t } = useTranslation();
  const format = useFormat();
  const shares = histogramShares(report);
  const edge = (v: number | null) => (v === null ? '' : format.number(v, { maximumFractionDigits: 1 }));
  return (
    <div role="img" aria-label={t('analytics.histogram')} className="flex h-32 items-end gap-0.5">
      {report.r_histogram.map((b, i) => {
        const label =
          b.low === null
            ? `< ${edge(b.high)}R`
            : b.high === null
              ? `≥ ${edge(b.low)}R`
              : `${edge(b.low)}…${edge(b.high)}R`;
        return (
          <div
            key={label}
            title={`${label}: ${String(b.count)}`}
            className={`flex-1 rounded-t ${(b.high ?? 1) <= 0 ? 'bg-red-500/70' : 'bg-emerald-500/70'}`}
            style={{ height: `${String(Math.max((shares[i] ?? 0) * 100, b.count > 0 ? 3 : 0))}%` }}
          />
        );
      })}
    </div>
  );
}

function ByStyle({ report }: { report: Report }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const [dimension, setDimension] = useState<Dimension>('strategy');
  const rows = report.by_style[dimension] ?? [];
  const name = (value: string) =>
    dimension === 'strategy' ? translateCode(i18n, 'strategyName', value) : value;
  return (
    <div>
      <Field label={t('analytics.style.by')}>
        {(fid) => (
          <select
            id={fid}
            value={dimension}
            onChange={(e) => {
              setDimension(e.target.value as Dimension);
            }}
            className={SELECT}
          >
            {DIMENSIONS.map((d) => (
              <option key={d} value={d}>
                {t(`analytics.style.${d}`)}
              </option>
            ))}
          </select>
        )}
      </Field>
      <table aria-label={t('analytics.style.title')} className="mt-2 w-full text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className="py-1 pr-2 text-left font-normal">{t(`analytics.style.${dimension}`)}</th>
            <th className="py-1 pr-2 text-left font-normal">{t('analytics.kpi.trades')}</th>
            <th className="py-1 pr-2 text-left font-normal">{t('analytics.kpi.expectancy')}</th>
            <th className="py-1 text-left font-normal">{t('analytics.kpi.winRate')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.value} className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-1 pr-2">{name(row.value)}</td>
              <td className="py-1 pr-2 tabular-nums">{row.trades}</td>
              <td className="py-1 pr-2 tabular-nums">
                {row.expectancy_r === null
                  ? '—'
                  : `${format.number(row.expectancy_r, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}R`}
              </td>
              <td className="py-1 tabular-nums">
                {row.win_rate === null
                  ? '—'
                  : format.percent(row.win_rate * 100, { maximumFractionDigits: 0 })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MaeMfe({ report }: { report: Report }) {
  const { t } = useTranslation();
  const points = report.mae_mfe.filter((p) => p.mae_r !== null && p.mfe_r !== null);
  const max = Math.max(1, ...points.map((p) => Math.max(p.mae_r ?? 0, p.mfe_r ?? 0)));
  const scale = (v: number) => (Math.min(v, max) / max) * 190 + 5;
  return (
    <svg viewBox="0 0 200 200" role="img" aria-label={t('analytics.maeMfe')} className="h-56 w-full max-w-sm">
      <line x1="5" y1="195" x2="195" y2="195" className="stroke-slate-400" />
      <line x1="5" y1="5" x2="5" y2="195" className="stroke-slate-400" />
      {points.map((p) => (
        <circle
          key={p.trade_id}
          cx={scale(p.mae_r ?? 0)}
          cy={200 - scale(p.mfe_r ?? 0)}
          r="3"
          className={
            p.outcome === 'WIN'
              ? 'fill-emerald-500'
              : p.outcome === 'LOSS'
                ? 'fill-red-500'
                : 'fill-slate-400'
          }
        >
          <title>{`${p.symbol}: MAE ${String(p.mae_r)}R, MFE ${String(p.mfe_r)}R`}</title>
        </circle>
      ))}
    </svg>
  );
}

function RecommendationCard({
  rec,
  onBacktest,
}: {
  rec: Recommendation;
  onBacktest: (r: Recommendation) => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const e = rec.evidence;
  const pct = (v: unknown) =>
    typeof v === 'number' ? format.percent(v * 100, { maximumFractionDigits: 0 }) : '—';
  const num = (v: unknown) =>
    typeof v === 'number' ? format.number(v, { maximumFractionDigits: 2 }) : typeof v === 'string' ? v : '—';
  const params = {
    ...Object.fromEntries(Object.entries(e).map(([k, v]) => [k, num(v)])),
    share: pct(e.share),
    strategy: typeof e.strategy === 'string' ? translateCode(i18n, 'strategyName', e.strategy) : '',
    value:
      rec.segment?.dimension === 'strategy'
        ? translateCode(i18n, 'strategyName', rec.segment.value)
        : (rec.segment?.value ?? ''),
    dimension: rec.segment ? t(`analytics.style.${rec.segment.dimension as Dimension}`) : '',
    n: rec.sample_size,
  };
  return (
    <li className="rounded border border-slate-200 p-3 text-sm dark:border-slate-800">
      <p>{t(`analytics.recommendation.${rec.kind}`, params)}</p>
      {rec.ci && (
        <p className="mt-1 text-xs text-slate-500">
          {t('analytics.ci', {
            mean: num(rec.ci.mean),
            low: num(rec.ci.low),
            high: num(rec.ci.high),
            n: rec.ci.n,
          })}
        </p>
      )}
      {!rec.enough && (
        <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">
          {t('analytics.smallSample', { n: rec.sample_size, min: rec.min_samples })}
        </p>
      )}
      {rec.backtest ? (
        <button
          type="button"
          onClick={() => {
            onBacktest(rec);
          }}
          className="mt-2 rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
        >
          {t('analytics.backtestThis')}
        </button>
      ) : (
        <p className="mt-1 text-xs text-slate-500">{t('analytics.noBacktest')}</p>
      )}
    </li>
  );
}

function Recommendations({ query }: { query: AnalyticsQuery }) {
  const { t } = useTranslation();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const recs = useQuery({
    queryKey: analyticsKeys.recommendations(id, query),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(id)}/recommendations?${queryString(query)}`,
        RecommendationsSchema,
        {
          signal,
        },
      ),
    enabled: engineId !== null && (query.scope !== 'BACKTEST' || query.run !== null),
  });
  const backtest = async (rec: Recommendation) => {
    setError(null);
    try {
      const run = await apiPost(
        `/engines/${encodeURIComponent(id)}/backtests`,
        { ...rec.backtest, ...backtestPeriod(new Date(), query.days) },
        RunSchema,
      );
      await queryClient.invalidateQueries({ queryKey: backtestKeys.list(id) });
      void navigate(`/backtests?run=${encodeURIComponent(run.run_id)}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? t('analytics.backtestFailed', { code: err.code }) : t('stepUp.network'),
      );
    }
  };
  return (
    <Card title={t('analytics.recommendations')}>
      {recs.data === undefined ? (
        <p className="text-sm text-slate-500">
          {recs.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : recs.data.items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('analytics.noRecommendations', { n: recs.data.trades })}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {recs.data.items.map((r) => (
            <RecommendationCard
              key={`${r.kind}-${r.segment?.dimension ?? ''}-${r.segment?.value ?? ''}`}
              rec={r}
              onBacktest={(x) => void backtest(x)}
            />
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
      <p className="mt-2 text-xs text-slate-500">{t('analytics.neverApplied')}</p>
    </Card>
  );
}

/**
 * PLAN §A15 analytics and recommendations (TAA-1005): KPIs, curves, R distribution, performance by style,
 * MAE/MFE, attribution and the A16 recommendations, for one scope (paper, shadow or a backtest run). Every
 * result here is hypothetical; recommendations are never applied, only offered as a backtest.
 */
export function AnalyticsPage() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const [query, setQuery] = useState<AnalyticsQuery>({
    scope: 'PAPER',
    days: 90,
    run: null,
    variant: 'PLAN',
  });
  const ready = query.scope !== 'BACKTEST' || query.run !== null;
  const report = useQuery({
    queryKey: analyticsKeys.report(id, query),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(id)}/analytics?${queryString(query)}`, ReportSchema, { signal }),
    enabled: engineId !== null && ready,
  });
  const data = report.data;
  const curves = data ? curvePoints(data) : null;
  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.analytics')}</h1>
      <ScopeBar query={query} onChange={setQuery} />
      {!ready ? (
        <p className="text-sm text-slate-500">{t('analytics.pickRun')}</p>
      ) : data === undefined ? (
        <p className="text-sm text-slate-500">
          {report.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {data.hypothetical && (
            <p
              role="note"
              className="rounded bg-amber-50 p-2 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
            >
              {t('analytics.hypothetical')}
            </p>
          )}
          <AINarrative kind="ANALYTICS" />
          <Card title={t('analytics.kpi.title')}>
            <Kpis report={data} />
            {data.skipped > 0 && (
              <p className="mt-2 text-xs text-slate-500">{t('analytics.skipped', { n: data.skipped })}</p>
            )}
          </Card>
          {data.kpis.rated > 0 && curves && (
            <Suspense fallback={null}>
              <div className="grid gap-4 lg:grid-cols-2">
                <Card title={t('analytics.curve')}>
                  <SeriesChart
                    points={curves.result}
                    kind="equity"
                    label={t('analytics.curve')}
                    precision={2}
                  />
                </Card>
                <Card title={t('analytics.drawdown')}>
                  <SeriesChart
                    points={curves.drawdown}
                    kind="drawdown"
                    label={t('analytics.drawdown')}
                    precision={2}
                  />
                </Card>
                <Card title={t('analytics.histogram')}>
                  <Histogram report={data} />
                </Card>
                <Card title={t('analytics.maeMfe')}>
                  <MaeMfe report={data} />
                </Card>
                <Card title={t('analytics.style.title')}>
                  <ByStyle report={data} />
                </Card>
                <Card title={t('analytics.attribution')}>
                  <ul className="text-sm">
                    {data.attribution.map((a) => (
                      <li key={a.code} className="flex justify-between gap-2 py-0.5">
                        <span>{translateCode(i18n, 'attribution', a.code)}</span>
                        <span className="tabular-nums">
                          {a.count} (
                          {a.share === null
                            ? '—'
                            : format.percent(a.share * 100, { maximumFractionDigits: 0 })}
                          )
                        </span>
                      </li>
                    ))}
                  </ul>
                </Card>
              </div>
            </Suspense>
          )}
          <Recommendations query={query} />
        </div>
      )}
    </section>
  );
}
