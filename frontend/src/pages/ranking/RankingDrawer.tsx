import { useQuery } from '@tanstack/react-query';
import { type ReactNode, useEffect, useId, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { explain } from '@/i18n/explain';
import { useFormat } from '@/i18n/useFormat';

import { explainParams, FLAGS, OVERALL_SCORES, SCORES } from './rankingModel';
import { rankingKeys, type RankingDetail, RankingDetailSchema, type RankingItem } from './schemas';

/** Metrics in display order: money in the account currency, then plain numbers and a ratio. */
const MONEY_METRICS = ['risk_budget', 'min_lot_risk', 'required_equity', 'risk_money', 'margin'] as const;
const NUMBER_METRICS = ['typical_sl', 'min_lot', 'lot', 'effective_leverage'] as const;

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-1 text-sm last:border-0 dark:border-slate-800">
      <dt className="text-slate-600 dark:text-slate-400">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="mb-4">
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

/** A 0–100 score as an SVG bar (attributes, not inline styles, for the CSP). */
function ScoreBar({ name, value, overall }: { name: string; value: number; overall: boolean }) {
  const { t } = useTranslation();
  const format = useFormat();
  const text = format.number(value, { maximumFractionDigits: 1 });
  const width = Math.max(0, Math.min(100, value));
  return (
    <li className="mb-2">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span>
          {name}
          {overall && <span className="ml-1 text-xs text-slate-500">{t('ranking.drawer.inOverall')}</span>}
        </span>
        <span className="font-medium tabular-nums">{text}</span>
      </div>
      <svg
        role="meter"
        aria-label={name}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        aria-valuetext={text}
        viewBox="0 0 100 4"
        preserveAspectRatio="none"
        className="mt-0.5 h-1.5 w-full overflow-hidden rounded"
      >
        <rect width="100" height="4" className="fill-slate-200 dark:fill-slate-800" />
        <rect width={width} height="4" className={value >= 50 ? 'fill-sky-600' : 'fill-slate-400'} />
      </svg>
    </li>
  );
}

function DetailBody({ detail, item }: { detail: RankingDetail; item: RankingItem | undefined }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { own } = useEngine();
  const p = detail.payload;
  const metrics = p.metrics ?? {};
  const currency = typeof metrics.currency === 'string' ? metrics.currency : 'USD';
  const num = (key: string) => (typeof metrics[key] === 'number' ? metrics[key] : null);
  const costRatio = num('cost_ratio');
  const flags = (p.flags ?? []).filter((f) => f !== 'market_closed');
  const session = p.session;
  return (
    <>
      <dl className="mb-4 grid grid-cols-2 gap-3">
        <div>
          <dt className="text-xs text-slate-500">{t('ranking.col.now')}</dt>
          <dd className="text-2xl font-semibold tabular-nums">
            {format.number(detail.now_score, { maximumFractionDigits: 1 })}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">{t('ranking.col.overall')}</dt>
          <dd className="text-2xl font-semibold tabular-nums">
            {format.number(detail.overall, { maximumFractionDigits: 1 })}
          </dd>
        </div>
      </dl>
      <p className="mb-4 text-sm">
        {translateCode(i18n, 'assetClass', detail.asset_class)} ·{' '}
        <span
          className={
            detail.eligible ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'
          }
        >
          {t(detail.eligible ? 'ranking.drawer.eligible' : 'ranking.drawer.notEligible')}
        </span>
        {item?.personal && (
          <span className="block text-xs text-slate-500">
            {t(
              item.personal.eligible === true
                ? 'ranking.drawer.personalYes'
                : item.personal.eligible === false
                  ? 'ranking.drawer.personalNo'
                  : 'ranking.drawer.personalUnknown',
            )}
          </span>
        )}
      </p>
      <Section title={t('ranking.drawer.scores')}>
        <ul>
          {SCORES.filter((s) => s in p.scores).map((s) => (
            <ScoreBar
              key={s}
              name={t(`ranking.score.${s}`)}
              value={p.scores[s] ?? 0}
              overall={OVERALL_SCORES.has(s)}
            />
          ))}
        </ul>
        {flags.length > 0 && (
          <p className="text-xs text-slate-500">
            {flags
              .map((f) =>
                (FLAGS as readonly string[]).includes(f)
                  ? t(`ranking.flag.${f as (typeof FLAGS)[number]}`)
                  : f,
              )
              .join(' · ')}
          </p>
        )}
      </Section>
      {p.gates && p.gates.length > 0 && (
        <Section title={t('ranking.drawer.gates')}>
          <ul className="text-sm">
            {p.gates.map((g) => (
              <li key={g.gate} className="border-b border-slate-100 py-1 last:border-0 dark:border-slate-800">
                <span className="font-medium">{translateCode(i18n, 'gate', g.gate)}</span>{' '}
                <span
                  className={
                    g.status === 'OK'
                      ? 'text-emerald-700 dark:text-emerald-400'
                      : g.status === 'FAIL'
                        ? 'text-red-700 dark:text-red-400'
                        : 'text-slate-500'
                  }
                >
                  {translateCode(i18n, 'gateStatus', g.status)}
                </span>
                <span className="block text-xs text-slate-600 dark:text-slate-400">
                  {explain(i18n, g.key, explainParams(g.params))}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {Object.keys(metrics).length > 0 && (
        <Section title={t('ranking.drawer.metrics')}>
          <dl>
            {MONEY_METRICS.filter((m) => m in metrics).map((m) => (
              <Row key={m} label={t(`ranking.metric.${m}`)}>
                {format.money(num(m), currency)}
              </Row>
            ))}
            {NUMBER_METRICS.filter((m) => m in metrics).map((m) => (
              <Row key={m} label={t(`ranking.metric.${m}`)}>
                {format.number(num(m), { maximumFractionDigits: 6 })}
              </Row>
            ))}
            {'cost_ratio' in metrics && (
              <Row label={t('ranking.metric.cost_ratio')}>
                {format.percent(costRatio === null ? null : costRatio * 100, { maximumFractionDigits: 1 })}
              </Row>
            )}
          </dl>
        </Section>
      )}
      <Section title={t('ranking.drawer.session')}>
        <dl>
          {session && (
            <Row label={t('ranking.drawer.marketNow')}>
              {session.open
                ? t('ranking.drawer.openUntil', {
                    sessions: session.active.join(', ') || '—',
                    time: format.dateTime(session.ends_at),
                  })
                : t('ranking.drawer.closedUntil', { time: format.dateTime(session.next_open) })}
            </Row>
          )}
          {p.best_hours_utc && p.best_hours_utc.length > 0 && (
            <Row label={t('ranking.drawer.bestHours')}>{p.best_hours_utc.join(', ')}</Row>
          )}
          {p.correlated_with && (
            <Row label={t('ranking.drawer.correlation')}>
              {p.correlated_with} ({format.number(p.correlation, { maximumFractionDigits: 2 })})
            </Row>
          )}
        </dl>
      </Section>
      <p className="mb-3 text-xs text-slate-500">
        {t('ranking.account.asOf', { time: format.dateTime(detail.computed_at) })}
      </p>
      <div className="flex flex-wrap gap-4 text-sm">
        {own && (
          <>
            <Link to={`/charts?symbol=${encodeURIComponent(detail.symbol)}`} className="underline">
              {t('symbols.openChart')}
            </Link>
            <Link to={`/symbols?symbol=${encodeURIComponent(detail.symbol)}`} className="underline">
              {t('ranking.drawer.openSymbol')}
            </Link>
          </>
        )}
      </div>
    </>
  );
}

/** Every score, gate and metric of one symbol (PLAN §A28 "detail drawer with every score"). */
export function RankingDrawer({
  engineId,
  symbol,
  item,
  onClose,
}: {
  engineId: string;
  symbol: string;
  item: RankingItem | undefined;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const titleId = useId();
  const close = useRef<HTMLButtonElement>(null);
  const detail = useQuery({
    queryKey: rankingKeys.detail(engineId, symbol),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/ranking/${encodeURIComponent(symbol)}`,
        RankingDetailSchema,
        { signal },
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
        className="absolute inset-y-0 right-0 w-full max-w-md overflow-y-auto bg-white p-4 shadow-xl dark:bg-slate-900"
      >
        <div className="mb-4 flex items-start justify-between gap-2">
          <h2 id={titleId} className="text-lg font-semibold">
            {detail.data ? t('ranking.drawer.title', { symbol, rank: detail.data.rank }) : symbol}
          </h2>
          <button ref={close} type="button" onClick={onClose} className="rounded px-2 py-1 text-sm underline">
            {t('nav.close')}
          </button>
        </div>
        {detail.isError ? (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {t('ranking.drawer.notFound')}
          </p>
        ) : !detail.data ? (
          <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
        ) : (
          <DetailBody detail={detail.data} item={item} />
        )}
      </div>
    </div>
  );
}
