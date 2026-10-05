import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';

import { chartLink, countdown, reasonKind, type WindowState } from './opportunityModel';
import type { Opportunity, OpportunityFacts, Probability } from './schemas';

const TONE: Record<string, string> = {
  ACTIVE: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  CANDIDATE: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  EXPIRING: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  EXPIRED: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  INVALIDATED: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  FOLLOWED: 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300',
};

/** The status badge with its reason ("suitable time has passed: London session ended") and the countdown. */
export function StatusBadge({ opportunity, state }: { opportunity: OpportunityFacts; state: WindowState }) {
  const { t, i18n } = useTranslation();
  const kind = reasonKind(state.status);
  // the engine's reason once it marked the status, else the window's reason (expired before the next pass)
  const raw = opportunity.status === state.status ? opportunity.status_reason : opportunity.valid_reason;
  const reason = kind && raw ? translateCode(i18n, kind, raw) : opportunity.status === 'FOLLOWED' ? raw : '';
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className={`rounded px-1.5 py-0.5 font-medium ${TONE[state.status] ?? TONE.EXPIRED}`}>
        {translateCode(i18n, 'opportunityStatus', state.status)}
      </span>
      {reason && <span className="text-slate-600 dark:text-slate-400">{reason}</span>}
      {state.remainingMs !== null && state.remainingMs > 0 && (
        <span className="font-medium tabular-nums" title={t('opportunities.countdownHint')}>
          {t('opportunities.countdown', { time: countdown(state.remainingMs) })}
        </span>
      )}
    </div>
  );
}

function Figure({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500 dark:text-slate-400" title={hint}>
        {label}
      </dt>
      <dd className="font-semibold tabular-nums">{children}</dd>
    </div>
  );
}

/** Both metrics (win probability with its interval, setup strength), the baselines and the EV (§A26). */
export function Metrics({ opportunity }: { opportunity: OpportunityFacts }) {
  const { t } = useTranslation();
  const format = useFormat();
  const p: Probability = opportunity.probability;
  const pct = (value: number | null | undefined) => format.percent(value, { maximumFractionDigits: 1 });
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <Figure label={t('opportunities.metric.probability')} hint={t('opportunities.metric.probabilityHint')}>
        {p.available ? (
          <>
            {pct(p.estimate.p)}
            <span className="block text-xs font-normal text-slate-500">
              {p.estimate.insufficient
                ? t('opportunities.metric.insufficient')
                : t('opportunities.metric.interval', {
                    low: pct(p.estimate.low),
                    high: pct(p.estimate.high),
                    n: format.number(p.estimate.n, { maximumFractionDigits: 0 }),
                  })}
            </span>
          </>
        ) : (
          <span className="text-sm font-normal text-slate-500">
            {t('opportunities.metric.notCalibrated')}
          </span>
        )}
      </Figure>
      <Figure label={t('opportunities.metric.strength')} hint={t('opportunities.metric.strengthHint')}>
        {pct(opportunity.setup_strength)}
      </Figure>
      {p.available && (
        <>
          <Figure label={t('opportunities.metric.baseline')} hint={t('opportunities.metric.baselineHint')}>
            {pct(p.random_baseline)}
          </Figure>
          <Figure label={t('opportunities.metric.breakEven')} hint={t('opportunities.metric.breakEvenHint')}>
            {pct(p.break_even)}
          </Figure>
          <Figure label={t('opportunities.metric.ev')} hint={t('opportunities.metric.evHint')}>
            {t('opportunities.r', {
              value: format.number(p.ev_r, { maximumFractionDigits: 2, signDisplay: 'exceptZero' }),
            })}
          </Figure>
        </>
      )}
    </dl>
  );
}

/** Entry, stop and target, with the risk/reward ratio. */
export function Prices({ opportunity }: { opportunity: OpportunityFacts }) {
  const { t } = useTranslation();
  const format = useFormat();
  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 6 });
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Figure label={t('opportunities.entry')}>{price(opportunity.entry)}</Figure>
      <Figure label={t('opportunities.stop')}>{price(opportunity.stop_loss)}</Figure>
      <Figure label={t('opportunities.target')}>{price(opportunity.take_profit)}</Figure>
      <Figure label={t('opportunities.rr')}>
        {opportunity.rr != null ? `1:${format.number(opportunity.rr, { maximumFractionDigits: 2 })}` : '—'}
      </Figure>
    </dl>
  );
}

/** The owner's lot and money at signal time (absent on the market feed: the detail sizes the user's own). */
export function Money({ opportunity }: { opportunity: OpportunityFacts }) {
  const { t } = useTranslation();
  const format = useFormat();
  if (opportunity.lot === undefined) {
    return <p className="text-xs text-slate-500">{t('opportunities.ownSizingInDetail')}</p>;
  }
  const money = (value: number | null | undefined) => format.money(value, opportunity.currency);
  return (
    <dl className="grid grid-cols-3 gap-3">
      <Figure label={t('opportunities.lot')}>
        {format.number(opportunity.lot, { maximumFractionDigits: 2 })}
      </Figure>
      <Figure label={t('opportunities.risk')}>{money(opportunity.risk_money)}</Figure>
      <Figure label={t('opportunities.reward')}>{money(opportunity.reward_money)}</Figure>
    </dl>
  );
}

export function SideBadge({ side }: { side: string }) {
  const { t } = useTranslation();
  const buy = side === 'BUY';
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-semibold ${buy ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'}`}
    >
      {t(buy ? 'opportunities.buy' : 'opportunities.sell')}
    </span>
  );
}

/** One live card (§A28 Opportunities). */
export function OpportunityCard({
  opportunity,
  state,
  own,
}: {
  opportunity: Opportunity;
  state: WindowState;
  own: boolean;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const o = opportunity;
  const detail = `/opportunities/${encodeURIComponent(o.opportunity_id)}`;
  return (
    <article
      aria-label={t('opportunities.cardLabel', { symbol: o.symbol, side: o.side })}
      className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold">{o.symbol}</h2>
          <SideBadge side={o.side} />
          <span className="text-sm text-slate-600 dark:text-slate-400">
            {translateCode(i18n, 'strategyName', o.strategy)} · {o.timeframe}
          </span>
        </div>
        <StatusBadge opportunity={o} state={state} />
        <p className="text-xs text-slate-500">
          {t('opportunities.found', { time: format.dateTime(o.created_at) })}
          {o.valid_until && ` · ${t('opportunities.validUntil', { time: format.dateTime(o.valid_until) })}`}
        </p>
      </header>
      <Metrics opportunity={o} />
      <Prices opportunity={o} />
      <Money opportunity={o} />
      <p className="text-xs text-slate-600 dark:text-slate-400">
        {t('opportunities.theories', { supporting: o.supporting, conflicting: o.conflicting })}
      </p>
      {o.warnings && o.warnings.length > 0 && (
        <ul className="text-xs text-amber-700 dark:text-amber-400">
          {o.warnings.map((w) => (
            <li key={w}>{translateCode(i18n, 'reason', w)}</li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-4 text-sm">
        <Link to={detail} className="underline">
          {t('opportunities.link')}
        </Link>
        {own && (
          <Link to={chartLink(o.symbol, o.opportunity_id, o.timeframe)} className="underline">
            {t('symbols.openChart')}
          </Link>
        )}
      </div>
    </article>
  );
}
