import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { engineKey } from '@/engine/schemas';
import { DECISIONS, REASON_CODES, translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { useLiveEvents } from '@/live/context';
import { Card } from '@/pages/dashboard/cards';

import {
  type Check,
  type DecisionFilters,
  DecisionDetailSchema,
  DecisionLogSchema,
  decisionKeys,
} from './schemas';

const PAGE = 50;
const PROFILES = ['EXECUTION', 'ADVISORY'] as const;
const SELECT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';
const TONE: Record<string, string> = {
  ACCEPT: 'text-emerald-700 dark:text-emerald-400',
  REJECT: 'text-red-700 dark:text-red-400',
  HOLD: 'text-slate-500',
};

function logPath(engineId: string, f: DecisionFilters, cursor: string | null): string {
  const query = new URLSearchParams({ limit: String(PAGE) });
  if (f.decision) query.set('decision', f.decision);
  if (f.profile && f.profile !== 'ALL') query.set('profile', f.profile);
  if (f.symbol) query.set('symbol', f.symbol);
  if (f.reason) query.set('reason', f.reason);
  if (cursor) query.set('cursor', cursor);
  return `/engines/${encodeURIComponent(engineId)}/decisions?${query.toString()}`;
}

function measured(value: Check['value'], format: ReturnType<typeof useFormat>): string {
  if (value === null) return '—';
  if (typeof value === 'number') return format.number(value, { maximumFractionDigits: 4 });
  return String(value);
}

/** Every check of one decision, in the order the decision engine ran them (PLAN §A8). */
function DecisionDetail({
  engineId,
  decisionId,
  onClose,
}: {
  engineId: string;
  decisionId: string;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const titleId = useId();
  const close = useRef<HTMLButtonElement>(null);
  const detail = useQuery({
    queryKey: decisionKeys.detail(engineId, decisionId),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/decisions/${encodeURIComponent(decisionId)}`,
        DecisionDetailSchema,
        {
          signal,
        },
      ),
  });
  useEffect(() => {
    close.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose]);
  const d = detail.data;
  return (
    <div className="fixed inset-0 z-40">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        className="absolute inset-0 h-full w-full bg-slate-900/50"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="absolute inset-y-0 right-0 w-full max-w-2xl overflow-y-auto bg-white p-4 shadow-xl dark:bg-slate-900"
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <h2 id={titleId} className="text-lg font-semibold">
            {d
              ? t('decisions.detail.title', {
                  symbol: d.symbol,
                  action: d.action,
                  decision: translateCode(i18n, 'decision', d.decision),
                })
              : t('dashboard.loading')}
          </h2>
          <button ref={close} type="button" onClick={onClose} className="rounded px-2 py-1 text-sm underline">
            {t('nav.close')}
          </button>
        </div>
        {detail.isError ? (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {t('dashboard.loadFailed')}
          </p>
        ) : !d ? null : (
          <>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {t('decisions.detail.meta', {
                strategy: d.strategy,
                tf: d.timeframe,
                profile: t(`decisions.profile.${d.profile === 'ADVISORY' ? 'ADVISORY' : 'EXECUTION'}`),
                time: format.dateTime(d.created_at),
              })}
            </p>
            <section aria-label={t('decisions.detail.signal')} className="mt-3">
              <h3 className="text-sm font-semibold">{t('decisions.detail.signal')}</h3>
              <p className="text-sm">
                {t('decisions.detail.score', {
                  score: format.number(d.signal.score, { maximumFractionDigits: 1 }),
                  strength: format.number(d.signal.setup_strength ?? null, { maximumFractionDigits: 0 }),
                })}
              </p>
              {d.signal.explanation && (
                <p className="text-sm text-slate-600 dark:text-slate-400">{d.signal.explanation}</p>
              )}
              {d.signal.conditions.length > 0 && (
                <ul className="mt-1 flex flex-wrap gap-2 text-xs">
                  {d.signal.conditions.map((c) => (
                    <li
                      key={c.name}
                      className={`rounded px-1.5 py-0.5 ${c.passed ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200' : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'}`}
                    >
                      {c.passed ? '✓' : '✗'} {c.name}
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="mt-4">
              <h3 className="mb-1 text-sm font-semibold">
                {t('decisions.detail.checks', {
                  passed: d.checks.filter((c) => c.passed).length,
                  total: d.checks.length,
                })}
              </h3>
              <div className="overflow-x-auto">
                <table aria-label={t('decisions.detail.checksTable')} className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500">
                      <th className="py-1 pr-3 font-normal">{t('decisions.col.result')}</th>
                      <th className="py-1 pr-3 font-normal">{t('decisions.col.check')}</th>
                      <th className="py-1 pr-3 font-normal">{t('decisions.col.value')}</th>
                      <th className="py-1 pr-3 font-normal">{t('decisions.col.threshold')}</th>
                      <th className="py-1 font-normal">{t('decisions.col.kind')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.checks.map((c) => (
                      <tr key={c.seq} className="border-t border-slate-100 align-top dark:border-slate-800">
                        <td
                          className={`py-1 pr-3 font-semibold ${c.passed ? (TONE.ACCEPT ?? '') : (TONE.REJECT ?? '')}`}
                        >
                          {t(c.passed ? 'decisions.passed' : 'decisions.failed')}
                        </td>
                        <td className="py-1 pr-3">
                          {translateCode(i18n, 'reason', c.reason)}
                          <span className="block text-xs text-slate-500">
                            {c.name}
                            {c.detail && ` · ${c.detail}`}
                          </span>
                        </td>
                        <td className="py-1 pr-3 tabular-nums">{measured(c.value, format)}</td>
                        <td className="py-1 pr-3 tabular-nums">{measured(c.threshold, format)}</td>
                        <td className="py-1 text-xs text-slate-500">{c.kind}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <Link
              to={`/charts?symbol=${encodeURIComponent(d.symbol)}&tf=${encodeURIComponent(d.timeframe)}&decision=${encodeURIComponent(d.decision_id)}`}
              className="mt-4 inline-block text-sm underline"
            >
              {t('decisions.detail.chart')}
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

/** PLAN §A15 signals & decisions (TAA-908): the decision log with check-by-check results and filters. */
export function DecisionsPage() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const queryClient = useQueryClient();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const [params, setParams] = useSearchParams();
  const filters: DecisionFilters = {
    decision: params.get('decision') ?? '',
    profile: params.get('profile') ?? 'EXECUTION',
    symbol: (params.get('symbol') ?? '').toUpperCase(),
    reason: params.get('reason') ?? '',
  };
  const selected = params.get('id');
  const set = (name: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === '') next.delete(name);
    else next.set(name, value);
    setParams(next, { replace: name !== 'id' });
  };

  const log = useInfiniteQuery({
    queryKey: decisionKeys.log(id, filters),
    queryFn: ({ pageParam, signal }) =>
      apiGet(logPath(id, filters, pageParam), DecisionLogSchema, { signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  useLiveEvents('decisions', () => {
    void queryClient.invalidateQueries({ queryKey: [...engineKey(id), 'decisions', 'log'] });
  });
  const rows = log.data?.pages.flatMap((p) => p.items) ?? [];
  const reasonOptions = [...REASON_CODES]
    .map((code) => ({ code, label: translateCode(i18n, 'reason', code).replace(/:\s*$/, '') }))
    .sort((a, b) => a.label.localeCompare(b.label, i18n.language));

  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.decisions')}</h1>
      <Card title={t('decisions.log')}>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm">
            {t('decisions.filter.decision')}
            <select
              value={filters.decision}
              onChange={(e) => {
                set('decision', e.target.value);
              }}
              className={SELECT}
            >
              <option value="">{t('decisions.filter.all')}</option>
              {DECISIONS.map((d) => (
                <option key={d} value={d}>
                  {translateCode(i18n, 'decision', d)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            {t('decisions.filter.profile')}
            <select
              value={filters.profile}
              onChange={(e) => {
                set('profile', e.target.value || 'ALL');
              }}
              className={SELECT}
            >
              {PROFILES.map((p) => (
                <option key={p} value={p}>
                  {t(`decisions.profile.${p}`)}
                </option>
              ))}
              <option value="ALL">{t('decisions.filter.all')}</option>
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            {t('decisions.filter.reason')}
            <select
              value={filters.reason}
              onChange={(e) => {
                set('reason', e.target.value);
              }}
              className={`${SELECT} max-w-56`}
            >
              <option value="">{t('decisions.filter.all')}</option>
              {reasonOptions.map((o) => (
                <option key={o.code} value={o.code}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            {t('decisions.filter.symbol')}
            <input
              type="search"
              value={filters.symbol}
              onChange={(e) => {
                set('symbol', e.target.value.trim().toUpperCase());
              }}
              className={`${SELECT} w-28`}
            />
          </label>
        </div>
        {log.data === undefined ? (
          <p className="text-sm text-slate-500">
            {log.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
          </p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-500">{t('decisions.none')}</p>
        ) : (
          <>
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {rows.map((d) => (
                <li key={d.decision_id} className="py-2 text-sm">
                  <button
                    type="button"
                    onClick={() => {
                      set('id', d.decision_id);
                    }}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <span className="flex flex-wrap justify-between gap-x-3">
                      <span className="font-medium">
                        {d.symbol} {d.action} ·{' '}
                        <span className={TONE[d.decision] ?? ''}>
                          {translateCode(i18n, 'decision', d.decision)}
                        </span>
                      </span>
                      <span className="text-slate-500">{format.dateTime(d.created_at)}</span>
                    </span>
                    <span className="block text-xs text-slate-500">
                      {d.strategy} · {d.timeframe}
                      {d.reason_codes.length > 0 &&
                        ` · ${d.reason_codes.map((c) => translateCode(i18n, 'reason', c)).join(' · ')}`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {log.hasNextPage && (
              <button
                type="button"
                disabled={log.isFetchingNextPage}
                onClick={() => void log.fetchNextPage()}
                className="mt-3 text-sm underline"
              >
                {t('trades.closed.more')}
              </button>
            )}
          </>
        )}
      </Card>
      {selected !== null && (
        <DecisionDetail
          engineId={id}
          decisionId={selected}
          onClose={() => {
            set('id', null);
          }}
        />
      )}
    </section>
  );
}
