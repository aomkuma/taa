import { useQuery } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import {
  BehaviorSchema,
  type Behavior,
  type Expectancy,
  ExpectancySchema,
  learningKeys,
  type Share,
  type Timing,
  TimingSchema,
} from './schemas';

const SCOPES = ['SHADOW', 'PAPER'] as const;
const DAYS = [30, 90, 180] as const;
const MODES = ['EARLY', 'LATE', 'STALL', 'TF_MISMATCH', 'WRONG', 'OTHER', 'UNKNOWN'] as const;

function useNumbers() {
  const format = useFormat();
  return {
    pct: (v: number | null | undefined) =>
      v === null || v === undefined ? '—' : format.percent(v * 100, { maximumFractionDigits: 0 }),
    r: (v: number | null | undefined) =>
      v === null || v === undefined
        ? '—'
        : `${format.number(v, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}R`,
    size: (v: number) => `${format.number(v, { maximumFractionDigits: 2 })}R`,
    n: (v: number) => format.number(v),
  };
}

function ShareText({ share }: { share: Share | null | undefined }) {
  const { t } = useTranslation();
  const num = useNumbers();
  if (!share || share.n === 0) return <>—</>;
  return (
    <>
      {num.pct(share.share)}{' '}
      <span className="text-xs text-slate-500">
        {t('learning.range', { low: num.pct(share.low), high: num.pct(share.high), n: share.n })}
      </span>
    </>
  );
}

function TimingCard({ data }: { data: Timing }) {
  const { t, i18n } = useTranslation();
  const num = useNumbers();
  const all = data.overall[0];
  if (!all || data.trades === 0) return <p className="text-sm text-slate-500">{t('learning.none')}</p>;
  return (
    <>
      <p className="mb-2 text-sm">
        {t('learning.timing.losers', { losers: all.losers, trades: all.trades })}
      </p>
      <table className="w-full text-sm">
        <tbody>
          {MODES.map((mode) => (
            <tr key={mode} className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-1 pr-2">{translateCode(i18n, 'failureMode', mode)}</td>
              <td className="py-1 text-right tabular-nums">
                <ShareText share={all.modes[mode]} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="mt-3 grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-slate-500">{t('learning.timing.hitRate')}</dt>
          <dd>
            <ShareText share={all.hit_rate} />{' '}
            <span className="text-xs text-slate-500">
              {t('learning.timing.baseline', { value: num.pct(all.baseline_hit_rate) })}
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">{t('learning.timing.vindicated')}</dt>
          <dd>
            <ShareText share={all.vindicated} />{' '}
            <span className="text-xs text-slate-500">
              {t('learning.timing.baseline', { value: num.pct(all.baseline_vindicated) })}
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">{t('learning.timing.winnerMae')}</dt>
          <dd>{all.winner_mae_r ? num.r(all.winner_mae_r['0.5']) : t('learning.fewTrades')}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">{t('learning.timing.barsToTarget')}</dt>
          <dd>
            {all.winner_bars_to_tp
              ? t('learning.timing.bars', { n: num.n(all.winner_bars_to_tp['0.5'] ?? 0) })
              : t('learning.fewTrades')}
          </dd>
        </div>
      </dl>
      <p className="mt-2 text-xs text-slate-500">
        {t('learning.timing.note', { hours: data.lookahead_hours })}
      </p>
    </>
  );
}

function ExpectancyCard({ data }: { data: Expectancy }) {
  const { t, i18n } = useTranslation();
  const num = useNumbers();
  const now = data.overall;
  if (!now) return <p className="text-sm text-slate-500">{t('learning.none')}</p>;
  const tiles: [string, string][] = [
    [t('learning.expectancy.p'), num.pct(now.p)],
    [t('learning.expectancy.w'), num.size(now.win_r)],
    [t('learning.expectancy.l'), num.size(now.loss_r)],
    [t('learning.expectancy.c'), num.size(now.cost_r)],
  ];
  return (
    <>
      <p className="mb-2 text-sm">
        {t('learning.expectancy.result', {
          value: num.r(now.expectancy_r),
          low: num.r(now.ci.low),
          high: num.r(now.ci.high),
          n: now.n,
        })}
      </p>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map(([label, value]) => (
          <div key={label} className="rounded border border-slate-200 p-2 dark:border-slate-800">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="text-lg font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {data.change && (
        <p className="mt-2 text-sm">
          {t('learning.expectancy.change', {
            total: num.r(data.change.total),
            lever: t(`learning.expectancy.lever.${data.change.main}`),
          })}
        </p>
      )}
      {data.groups.length > 0 && (
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="py-1 font-normal">{t('learning.expectancy.group')}</th>
              <th className="py-1 text-right font-normal">n</th>
              <th className="py-1 text-right font-normal">E[R]</th>
            </tr>
          </thead>
          <tbody>
            {data.groups.map((g) => (
              <tr key={g.key.join('|')} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-1">
                  {translateCode(i18n, 'strategyName', g.key[0] ?? '')} · {g.key[1]}
                </td>
                <td className="py-1 text-right tabular-nums">{num.n(g.n)}</td>
                <td className="py-1 text-right tabular-nums">{num.r(g.expectancy_r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function BehaviorCard({ data }: { data: Behavior }) {
  const { t, i18n } = useTranslation();
  const num = useNumbers();
  if (data.trades === 0) return <p className="text-sm text-slate-500">{t('learning.behavior.none')}</p>;
  return (
    <>
      <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
        {data.patterns.map((p) => (
          <li key={p.pattern} className="flex flex-wrap justify-between gap-2 py-1.5">
            <span>{translateCode(i18n, 'behaviorPattern', p.pattern)}</span>
            <span className="tabular-nums">
              {p.considered === 0
                ? t('learning.behavior.unknown')
                : t('learning.behavior.count', { hits: p.count, considered: p.considered })}
              {p.count > 0 && (
                <span className="ml-1 text-xs text-slate-500">
                  {t('learning.behavior.delta', { r: num.r(p.delta_r) })}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {data.comfort_distance !== null && (
        <p className="mt-2 text-sm">
          {t('learning.behavior.comfort', { value: num.pct(data.comfort_distance) })}{' '}
          <span className="text-xs text-slate-500">
            {Object.keys(data.class_mix)
              .map((c) => translateCode(i18n, 'assetClass', c))
              .join(', ')}
          </span>
        </p>
      )}
      <p className="mt-2 text-xs text-slate-500">{t('learning.behavior.note')}</p>
    </>
  );
}

/**
 * PLAN_LEARNING §L19–§L20 (TAA-L701 / L801 / L808): why trades lost (timing), which lever of
 * E[R] = p·W − (1 − p)·L − c moved, and patterns in the owner's manual trades. Hypothetical, descriptive.
 */
export function LearningPage() {
  const { t } = useTranslation();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const scopeId = useId();
  const daysId = useId();
  const [scope, setScope] = useState<string>('SHADOW');
  const [days, setDays] = useState<number>(90);
  const base = `/engines/${encodeURIComponent(id)}/learning`;
  const timing = useQuery({
    queryKey: learningKeys.timing(id, scope, days),
    queryFn: ({ signal }) =>
      apiGet(`${base}/timing?scope=${scope}&days=${String(days)}`, TimingSchema, { signal }),
    enabled: engineId !== null,
  });
  const expectancy = useQuery({
    queryKey: learningKeys.expectancy(id, scope, days),
    queryFn: ({ signal }) =>
      apiGet(`${base}/expectancy?scope=${scope}&days=${String(days)}`, ExpectancySchema, { signal }),
    enabled: engineId !== null,
  });
  const behavior = useQuery({
    queryKey: learningKeys.behavior(id, days),
    queryFn: ({ signal }) => apiGet(`${base}/behavior?days=${String(days)}`, BehaviorSchema, { signal }),
    enabled: engineId !== null,
  });
  const waiting = (failed: boolean) => (
    <p className="text-sm text-slate-500">{failed ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
  const select =
    'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';
  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.learning')}</h1>
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">{t('learning.intro')}</p>
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <span className="flex items-center gap-1.5">
          <label htmlFor={scopeId}>{t('learning.scope.label')}</label>
          <select
            id={scopeId}
            value={scope}
            onChange={(e) => {
              setScope(e.target.value);
            }}
            className={select}
          >
            {SCOPES.map((s) => (
              <option key={s} value={s}>
                {t(`learning.scope.${s}`)}
              </option>
            ))}
          </select>
        </span>
        <span className="flex items-center gap-1.5">
          <label htmlFor={daysId}>{t('analytics.days.label')}</label>
          <select
            id={daysId}
            value={days}
            onChange={(e) => {
              setDays(Number(e.target.value));
            }}
            className={select}
          >
            {DAYS.map((d) => (
              <option key={d} value={d}>
                {t('analytics.days.n', { n: d })}
              </option>
            ))}
          </select>
        </span>
      </div>
      <div className="flex flex-col gap-4">
        <Card title={t('learning.timing.title')}>
          {timing.data ? <TimingCard data={timing.data} /> : waiting(timing.isError)}
        </Card>
        <Card title={t('learning.expectancy.title')}>
          {expectancy.data ? <ExpectancyCard data={expectancy.data} /> : waiting(expectancy.isError)}
        </Card>
        <Card title={t('learning.behavior.title')}>
          {behavior.data ? <BehaviorCard data={behavior.data} /> : waiting(behavior.isError)}
        </Card>
        <p className="text-xs text-slate-500">{t('learning.hypothetical')}</p>
      </div>
    </section>
  );
}
