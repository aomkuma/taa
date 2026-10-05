import { type ReactNode, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { useEngine } from '@/engine/context';
import { evidenceName, translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { SeriesChart } from '@/pages/backtests/SeriesChart';
import { Card } from '@/pages/dashboard/cards';
import { usePreferences } from '@/pages/watchlists/hooks';
import { globalThreshold } from '@/pages/watchlists/watchlistModel';

import {
  breakdownRows,
  bucketRows,
  calibrationPoints,
  curveSeries,
  type Dimension,
  DIMENSIONS,
  scoreGroups,
  theoryParts,
} from './accuracyModel';
import { BucketChart, CalibrationPlot } from './charts';
import { useAccuracy, useCalibration, useOutcomeHistory } from './hooks';
import type { Calibration, Section, Source, Summary, TheoryScore, Variant } from './schemas';

const TABS = ['overview', 'explorer', 'theories'] as const;
type Tab = (typeof TABS)[number];
const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const TH = 'px-2 py-1 text-left font-medium';
const TD = 'px-2 py-1 tabular-nums';

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-500">{error ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
}

function Toggle<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly { value: T; text: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          className={`rounded px-2 py-0.5 text-sm ${value === o.value ? 'bg-slate-200 font-medium dark:bg-slate-700' : ''}`}
          onClick={() => {
            onChange(o.value);
          }}
        >
          {o.text}
        </button>
      ))}
    </div>
  );
}

/** Money in the account currency when it is known, else a plain number. */
function useMoney(currency: string | null | undefined) {
  const format = useFormat();
  return (value: number | null | undefined) =>
    currency ? format.money(value, currency) : format.number(value, { maximumFractionDigits: 2 });
}

function useNumbers() {
  const format = useFormat();
  return {
    pct: (v: number | null | undefined) => format.percent(v, { maximumFractionDigits: 1 }),
    r: (v: number | null | undefined) =>
      v === null || v === undefined
        ? '—'
        : `${format.number(v, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })} R`,
    ratio: (v: number | null | undefined) => format.number(v, { maximumFractionDigits: 2 }),
  };
}

/** "40% (14–73%)". */
function HitRate({ s }: { s: Pick<Summary, 'hit_rate' | 'hit_low' | 'hit_high'> }) {
  const { pct } = useNumbers();
  const format = useFormat();
  if (s.hit_rate === null) return <>—</>;
  return (
    <>
      {pct(s.hit_rate)}{' '}
      <span className="text-xs text-slate-500">
        ({format.number(s.hit_low, { maximumFractionDigits: 0 })}–
        {format.percent(s.hit_high, { maximumFractionDigits: 0 })})
      </span>
    </>
  );
}

function Figure({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{children}</dd>
      {hint !== undefined && <dd className="text-xs text-slate-500">{hint}</dd>}
    </div>
  );
}

function Kpis({ summary, currency }: { summary: Summary; currency: string | null | undefined }) {
  const { t } = useTranslation();
  const money = useMoney(currency);
  const { r, ratio } = useNumbers();
  return (
    <Card title={t('accuracy.kpi.title')}>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Figure label={t('accuracy.kpi.trades')} hint={t('accuracy.kpi.wins', { n: summary.wins })}>
          {summary.n}
        </Figure>
        <Figure label={t('accuracy.kpi.hitRate')} hint={t('accuracy.kpi.ci')}>
          <HitRate s={summary} />
        </Figure>
        <Figure label={t('accuracy.kpi.expectancy')} hint={money(summary.expectancy_money)}>
          {r(summary.expectancy_r)}
        </Figure>
        <Figure label={t('accuracy.kpi.profitFactor')}>{ratio(summary.profit_factor_r)}</Figure>
        <Figure
          label={t('accuracy.kpi.total')}
          hint={t('accuracy.kpi.withMoney', { n: summary.n_money, total: summary.n })}
        >
          {money(summary.total_pnl)}
        </Figure>
        <Figure label={t('accuracy.kpi.drawdown')} hint={r(summary.max_drawdown_r)}>
          {money(summary.max_drawdown)}
        </Figure>
      </dl>
    </Card>
  );
}

function CurveCard({ section }: { section: Section }) {
  const { t } = useTranslation();
  const [unit, setUnit] = useState<'money' | 'r'>(section.summary.n_money > 0 ? 'money' : 'r');
  const points = curveSeries(section.curve, unit === 'money' ? (p) => p.pnl : (p) => p.r);
  return (
    <Card
      title={t('accuracy.curve.title')}
      action={
        <Toggle
          label={t('accuracy.curve.unit')}
          value={unit}
          options={[
            { value: 'money', text: t('accuracy.curve.money') },
            { value: 'r', text: t('accuracy.curve.r') },
          ]}
          onChange={setUnit}
        />
      }
    >
      {points.length === 0 ? (
        <p className="text-sm text-slate-500">{t('accuracy.none')}</p>
      ) : (
        <SeriesChart points={points} kind="equity" label={t('accuracy.curve.title')} precision={2} />
      )}
      <p className="mt-2 text-xs text-slate-500">{t('accuracy.curve.note')}</p>
    </Card>
  );
}

function CalibrationCard({ calibration }: { calibration: Calibration | null | undefined }) {
  const { t } = useTranslation();
  const format = useFormat();
  if (calibration === undefined) {
    return (
      <Card title={t('accuracy.calibration.title')}>
        <Loading error={false} />
      </Card>
    );
  }
  if (calibration === null) {
    return (
      <Card title={t('accuracy.calibration.title')}>
        <p className="text-sm text-slate-500">{t('accuracy.calibration.none')}</p>
      </Card>
    );
  }
  const points = calibrationPoints(calibration.reliability);
  const backtest = calibration.n_replay > calibration.n_live;
  return (
    <Card
      title={t('accuracy.calibration.title')}
      action={
        backtest && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
            {t('accuracy.calibration.backtest')}
          </span>
        )
      }
    >
      {points.length === 0 ? (
        <p className="text-sm text-slate-500">{t('accuracy.calibration.empty')}</p>
      ) : (
        <CalibrationPlot points={points} />
      )}
      <p className="mt-2 text-xs text-slate-500">
        {t('accuracy.calibration.about', {
          brier: format.number(calibration.brier, { maximumFractionDigits: 3 }),
          live: calibration.n_live,
          replay: calibration.n_replay,
          at: format.dateTime(calibration.built_at),
        })}
      </p>
      {points.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer">{t('accuracy.table')}</summary>
          <table className="mt-1 w-full">
            <thead>
              <tr>
                <th className={TH}>{t('accuracy.calibration.predicted')}</th>
                <th className={TH}>{t('accuracy.calibration.observed')}</th>
                <th className={TH}>n</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.predicted}>
                  <td className={TD}>{format.percent(p.predicted, { maximumFractionDigits: 0 })}</td>
                  <td className={TD}>
                    <HitRate s={{ hit_rate: p.observed, hit_low: p.low, hit_high: p.high }} />
                  </td>
                  <td className={TD}>{p.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </Card>
  );
}

function SummaryTable({
  rows,
  label,
  first,
  currency,
  highlight,
}: {
  rows: [string, Summary][];
  label: (key: string) => string;
  first: string;
  currency: string | null | undefined;
  highlight?: string;
}) {
  const { t } = useTranslation();
  const money = useMoney(currency);
  const { r, ratio } = useNumbers();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className={TH}>{first}</th>
            <th className={TH}>{t('accuracy.kpi.trades')}</th>
            <th className={TH}>{t('accuracy.kpi.hitRate')}</th>
            <th className={TH}>{t('accuracy.kpi.expectancy')}</th>
            <th className={TH}>{t('accuracy.kpi.profitFactor')}</th>
            <th className={TH}>{t('accuracy.kpi.total')}</th>
            <th className={TH}>{t('accuracy.kpi.drawdownR')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
          {rows.map(([key, s]) => (
            <tr key={key} className={key === highlight ? 'bg-sky-50 dark:bg-sky-950/40' : ''}>
              <td className="px-2 py-1">{label(key)}</td>
              <td className={TD}>{s.n}</td>
              <td className={TD}>
                <HitRate s={s} />
              </td>
              <td className={TD}>{r(s.expectancy_r)}</td>
              <td className={TD}>{ratio(s.profit_factor_r)}</td>
              <td className={TD}>{s.n_money > 0 ? money(s.total_pnl) : '—'}</td>
              <td className={TD}>{r(s.max_drawdown_r === 0 ? 0 : -s.max_drawdown_r)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BucketsCard({ section, currency }: { section: Section; currency: string | null | undefined }) {
  const { t } = useTranslation();
  const rows = bucketRows(section.breakdowns.bucket);
  return (
    <Card title={t('accuracy.buckets.title')}>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">{t('accuracy.none')}</p>
      ) : (
        <>
          <BucketChart rows={rows} />
          <details className="mt-2">
            <summary className="cursor-pointer text-sm">{t('accuracy.table')}</summary>
            <SummaryTable
              rows={rows}
              label={(k) => k}
              first={t('accuracy.buckets.strength')}
              currency={currency}
            />
          </details>
        </>
      )}
      <p className="mt-2 text-xs text-slate-500">{t('accuracy.buckets.note')}</p>
    </Card>
  );
}

function useKeyLabel() {
  const { t, i18n } = useTranslation();
  return (dimension: Dimension, key: string): string => {
    switch (dimension) {
      case 'strategy':
        return translateCode(i18n, 'strategyName', key);
      case 'asset_class':
        return translateCode(i18n, 'assetClass', key);
      case 'session':
        return translateCode(i18n, 'session', key);
      case 'side':
        return key === 'BUY' ? t('opportunities.buy') : key === 'SELL' ? t('opportunities.sell') : key;
      case 'alerted':
      case 'followed':
        return i18n.exists(`accuracy.key.${key}`) ? t(`accuracy.key.${key as 'alerted'}`) : key;
      default:
        return key;
    }
  };
}

function BreakdownCard({ section, currency }: { section: Section; currency: string | null | undefined }) {
  const { t } = useTranslation();
  const id = useId();
  const keyLabel = useKeyLabel();
  const present = DIMENSIONS.filter((d) => section.breakdowns[d] !== undefined);
  const [dimension, setDimension] = useState<Dimension>('symbol');
  const shown = present.includes(dimension) ? dimension : (present[0] ?? 'symbol');
  const rows = breakdownRows(section.breakdowns[shown]);
  return (
    <Card
      title={t('accuracy.breakdown.title')}
      action={
        <span className="flex items-center gap-2 text-sm">
          <label htmlFor={id}>{t('accuracy.breakdown.by')}</label>
          <select
            id={id}
            className="rounded border border-slate-300 bg-white px-2 py-0.5 dark:border-slate-700 dark:bg-slate-950"
            value={shown}
            onChange={(e) => {
              setDimension(e.target.value as Dimension);
            }}
          >
            {present.map((d) => (
              <option key={d} value={d}>
                {t(`accuracy.dimension.${d}`)}
              </option>
            ))}
          </select>
        </span>
      }
    >
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">{t('accuracy.none')}</p>
      ) : (
        <SummaryTable
          rows={rows}
          label={(k) => keyLabel(shown, k)}
          first={t(`accuracy.dimension.${shown}`)}
          currency={currency}
        />
      )}
    </Card>
  );
}

function HistoryCard({ source, variant, own }: { source: Source; variant: Variant; own: boolean }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const { r } = useNumbers();
  const history = useOutcomeHistory(engineId ?? '', source, variant);
  const items = history.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <Card title={t('accuracy.history.title')}>
      <p className="mb-2 text-xs text-slate-500">
        {own ? t('accuracy.history.note') : t('accuracy.history.noteFeed')}
      </p>
      {history.data === undefined ? (
        <Loading error={history.isError} />
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('accuracy.none')}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-slate-500">
              <tr>
                <th className={TH}>{t('accuracy.history.signal')}</th>
                <th className={TH}>{t('accuracy.history.symbol')}</th>
                <th className={TH}>{t('accuracy.history.strategy')}</th>
                <th className={TH}>{t('accuracy.history.strength')}</th>
                <th className={TH}>{t('accuracy.history.exit')}</th>
                <th className={TH}>{t('accuracy.history.result')}</th>
                {own && <th className={TH}>{t('accuracy.history.pnl')}</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {items.map((trade) => (
                <tr key={trade.shadow_id}>
                  <td className="px-2 py-1 whitespace-nowrap">{format.dateTime(trade.signal_at)}</td>
                  <td className="px-2 py-1">
                    {trade.symbol}{' '}
                    <span className="text-xs text-slate-500">
                      {trade.side === 'BUY' ? t('opportunities.buy') : t('opportunities.sell')}{' '}
                      {trade.timeframe}
                    </span>
                  </td>
                  <td className="px-2 py-1">{translateCode(i18n, 'strategyName', trade.strategy)}</td>
                  <td className={TD}>{format.number(trade.setup_strength, { maximumFractionDigits: 0 })}</td>
                  <td className="px-2 py-1">
                    {trade.exit_reason ? translateCode(i18n, 'exitReason', trade.exit_reason) : '—'}
                    {trade.flags.map((flag) => (
                      <span
                        key={flag}
                        className="ml-1 rounded bg-slate-100 px-1 text-xs dark:bg-slate-800"
                        title={translateCode(i18n, 'shadowFlag', flag)}
                      >
                        {translateCode(i18n, 'shadowFlag', flag)}
                      </span>
                    ))}
                  </td>
                  <td
                    className={`${TD} ${trade.win === true ? 'text-emerald-700 dark:text-emerald-400' : trade.win === false ? 'text-red-700 dark:text-red-400' : ''}`}
                  >
                    {r(trade.r_net)}
                  </td>
                  {own && (
                    <td className={TD}>
                      {trade.net_pnl != null && trade.currency
                        ? format.money(trade.net_pnl, trade.currency, { signDisplay: 'exceptZero' })
                        : '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {history.hasNextPage && (
        <button
          type="button"
          className={`${BUTTON} mt-2`}
          disabled={history.isFetchingNextPage}
          onClick={() => {
            void history.fetchNextPage();
          }}
        >
          {t('accuracy.history.more')}
        </button>
      )}
    </Card>
  );
}

function ExplorerTab({ section, currency }: { section: Section; currency: string | null | undefined }) {
  const { t, i18n } = useTranslation();
  const prefs = usePreferences();
  const alerts = prefs.data?.alerts;
  const explorer = section.explorer;
  // the user's current x, when it is measured on the same metric (to the explorer's 5-point steps)
  const mine =
    alerts && alerts.metric === explorer.metric
      ? explorer.rows
          .filter((row) => row.threshold <= globalThreshold(alerts))
          .at(-1)
          ?.threshold.toString()
      : undefined;
  const rows: [string, Summary][] = explorer.rows.map((row) => [row.threshold.toString(), row.summary]);
  return (
    <Card title={t('accuracy.explorer.title')}>
      <p
        role="note"
        className="mb-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
      >
        {t('accuracy.explorer.inSample')}
      </p>
      <p className="mb-2 text-sm">
        {t('accuracy.explorer.about', {
          metric: i18n.t(`alerts.metric.${explorer.metric}.name`, explorer.metric),
        })}
      </p>
      {section.summary.n === 0 ? (
        <p className="text-sm text-slate-500">{t('accuracy.none')}</p>
      ) : (
        <SummaryTable
          rows={rows}
          label={(k) => `≥ ${k}`}
          first={t('accuracy.explorer.threshold')}
          currency={currency}
          {...(mine !== undefined ? { highlight: mine } : {})}
        />
      )}
      {mine !== undefined && <p className="mt-2 text-xs text-slate-500">{t('accuracy.explorer.yours')}</p>}
    </Card>
  );
}

function TheoriesTab({ section }: { section: Section }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { pct, r } = useNumbers();
  const [level, setLevel] = useState<TheoryScore['level']>('family');
  const groups = scoreGroups(section.scoreboard, level);
  return (
    <Card
      title={t('accuracy.theories.title')}
      action={
        <Toggle
          label={t('accuracy.theories.level')}
          value={level}
          options={[
            { value: 'family', text: t('accuracy.theories.family') },
            { value: 'detector', text: t('accuracy.theories.detector') },
          ]}
          onChange={setLevel}
        />
      }
    >
      <p className="mb-3 text-xs text-slate-500">{t('accuracy.theories.note')}</p>
      {groups.length === 0 ? (
        <p className="text-sm text-slate-500">{t('accuracy.none')}</p>
      ) : (
        groups.map((group) => (
          <section
            key={`${group.assetClass}|${group.timeframe}`}
            aria-label={`${translateCode(i18n, 'assetClass', group.assetClass)} ${group.timeframe}`}
            className="mb-4"
          >
            <h3 className="mb-1 text-sm font-semibold">
              {translateCode(i18n, 'assetClass', group.assetClass)} · {group.timeframe}{' '}
              <span className="font-normal text-slate-500">
                {t('accuracy.theories.base', { rate: pct(group.rows[0]?.base_rate) })}
              </span>
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-slate-500">
                  <tr>
                    <th className={TH}>{t('accuracy.theories.theory')}</th>
                    <th className={TH}>{t('accuracy.kpi.trades')}</th>
                    <th className={TH}>{t('accuracy.kpi.hitRate')}</th>
                    <th className={TH}>{t('accuracy.theories.lift')}</th>
                    <th className={TH}>{t('accuracy.kpi.expectancy')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {group.rows.map((row) => {
                    const parts = theoryParts(row);
                    return (
                      <tr key={row.theory}>
                        <td className="px-2 py-1">
                          {parts.detector !== null
                            ? evidenceName(i18n, parts.detector)
                            : translateCode(i18n, 'family', parts.family)}
                          {parts.detector !== null && (
                            <span className="ml-1 text-xs text-slate-500">
                              {translateCode(i18n, 'family', parts.family)}
                            </span>
                          )}
                        </td>
                        <td className={TD}>{row.n}</td>
                        <td className={TD}>
                          <HitRate s={{ hit_rate: row.hit_rate, hit_low: row.low, hit_high: row.high }} />
                        </td>
                        <td className={TD}>
                          {row.lift === null
                            ? '—'
                            : `×${format.number(row.lift, { maximumFractionDigits: 2 })}`}
                        </td>
                        <td className={TD}>{r(row.expectancy_r)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}
    </Card>
  );
}

/**
 * PLAN §A28 Signal Accuracy (TAA-919): the hypothetical record of every opportunity (shadow trades, §A27),
 * LIVE and REPLAY never mixed: KPIs, the follow-all curve, calibration, strength buckets, breakdowns, the
 * outcome history, the in-sample threshold explorer and the theory scoreboard.
 */
export function AccuracyPage() {
  const { t } = useTranslation();
  const { engineId, own } = useEngine();
  const [params, setParams] = useSearchParams();
  const tabParam = params.get('tab');
  const tab: Tab = TABS.find((x) => x === tabParam) ?? 'overview';
  const source: Source = params.get('source') === 'REPLAY' ? 'REPLAY' : 'LIVE';
  const variant: Variant = params.get('variant') === 'MANAGED' ? 'MANAGED' : 'PLAN';
  // the market feed only ever sees its own alerts
  const mine = !own || params.get('scope') === 'mine';
  const set = (key: string, value: string, fallback: string) => {
    setParams(
      (old) => {
        const next = new URLSearchParams(old);
        if (value === fallback) next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );
  };
  const accuracy = useAccuracy(engineId ?? '', variant, mine);
  const calibration = useCalibration(engineId ?? '');
  const data = accuracy.data;
  const section = data === undefined ? undefined : source === 'LIVE' ? data.live : data.replay;
  const other = data === undefined ? undefined : source === 'LIVE' ? data.replay : data.live;
  const currency = data?.currency;

  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.accuracy')}</h1>
      <p
        role="note"
        className="mb-4 rounded border border-slate-300 bg-slate-50 p-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
      >
        {t('accuracy.hypothetical')}
      </p>
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Toggle
          label={t('accuracy.source.label')}
          value={source}
          options={[
            { value: 'LIVE', text: t('accuracy.source.LIVE') },
            { value: 'REPLAY', text: t('accuracy.source.REPLAY') },
          ]}
          onChange={(v) => {
            set('source', v, 'LIVE');
          }}
        />
        <Toggle
          label={t('accuracy.variant.label')}
          value={variant}
          options={[
            { value: 'PLAN', text: t('accuracy.variant.PLAN') },
            { value: 'MANAGED', text: t('accuracy.variant.MANAGED') },
          ]}
          onChange={(v) => {
            set('variant', v, 'PLAN');
          }}
        />
        {own && (
          <Toggle
            label={t('accuracy.scope.label')}
            value={mine ? 'mine' : 'all'}
            options={[
              { value: 'all', text: t('accuracy.scope.all') },
              { value: 'mine', text: t('accuracy.scope.mine') },
            ]}
            onChange={(v) => {
              set('scope', v, 'all');
            }}
          />
        )}
      </div>
      <div
        role="tablist"
        aria-label={t('accuracy.tabs')}
        className="mb-4 flex gap-1 border-b border-slate-200 dark:border-slate-800"
      >
        {TABS.map((x) => (
          <button
            key={x}
            type="button"
            role="tab"
            aria-selected={tab === x}
            className={`-mb-px border-b-2 px-3 py-1.5 text-sm ${tab === x ? 'border-sky-600 font-medium' : 'border-transparent text-slate-600 dark:text-slate-400'}`}
            onClick={() => {
              set('tab', x, 'overview');
            }}
          >
            {t(`accuracy.tab.${x}`)}
          </button>
        ))}
      </div>
      {section === undefined || other === undefined ? (
        <Loading error={accuracy.isError} />
      ) : (
        <div className="flex flex-col gap-4">
          {mine && (
            <p className="text-sm text-slate-600 dark:text-slate-400">{t('accuracy.scope.mineNote')}</p>
          )}
          {section.summary.n === 0 && other.summary.n > 0 && (
            <p className="text-sm text-amber-700 dark:text-amber-400">
              {t(source === 'LIVE' ? 'accuracy.source.onlyReplay' : 'accuracy.source.onlyLive', {
                n: other.summary.n,
              })}
            </p>
          )}
          {tab === 'overview' && (
            <>
              <Kpis summary={section.summary} currency={currency} />
              <div className="grid gap-4 lg:grid-cols-2">
                <CurveCard key={`${source}-${variant}-${String(mine)}`} section={section} />
                <CalibrationCard calibration={calibration.data} />
                <BucketsCard section={section} currency={currency} />
                <BreakdownCard section={section} currency={currency} />
              </div>
              <HistoryCard source={source} variant={variant} own={own} />
            </>
          )}
          {tab === 'explorer' && <ExplorerTab section={section} currency={currency} />}
          {tab === 'theories' && <TheoriesTab section={section} />}
        </div>
      )}
    </section>
  );
}
