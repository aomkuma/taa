import { useQuery } from '@tanstack/react-query';
import { type ReactNode, useEffect, useId, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { apiGet } from '@/api/client';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';

import { type TradeDetail, TradeDetailSchema, tradeKeys } from './schemas';
import { initialRisk } from './tradeMath';

interface Step {
  key: string;
  at: string | null;
  title: string;
  body: ReactNode;
  tone: 'neutral' | 'good' | 'bad';
}

const DOT = { neutral: 'bg-slate-400', good: 'bg-emerald-500', bad: 'bg-red-600' };

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/** signal → decision → fill → stop changes → exit, from the trade detail (PLAN §A15 history drawer). */
function useSteps(detail: TradeDetail | undefined): Step[] {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  if (!detail) return [];
  const { position: p, decision, events } = detail;
  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 6 });
  const steps: Step[] = [];
  if (decision) {
    steps.push({
      key: 'signal',
      at: decision.signal.created_at_utc,
      title: t('trades.timeline.signal', { strategy: decision.strategy, tf: decision.timeframe }),
      tone: 'neutral',
      body: (
        <>
          {t('trades.timeline.score', {
            score: format.number(decision.signal.score, { maximumFractionDigits: 1 }),
          })}
          {decision.signal.reason_codes.length > 0 && (
            <span className="block text-xs text-slate-500">
              {decision.signal.reason_codes.map((c) => translateCode(i18n, 'reason', c)).join(' · ')}
            </span>
          )}
        </>
      ),
    });
    const failed = decision.checks.filter((c) => !c.passed);
    steps.push({
      key: 'decision',
      at: decision.created_at,
      title: t('trades.timeline.decision', { decision: translateCode(i18n, 'decision', decision.decision) }),
      tone: decision.decision === 'ACCEPT' ? 'good' : 'bad',
      body: (
        <>
          {t('trades.timeline.checks', {
            passed: decision.checks.length - failed.length,
            total: decision.checks.length,
          })}
          {failed.length > 0 && (
            <span className="block text-xs text-red-700 dark:text-red-400">
              {failed.map((c) => translateCode(i18n, 'reason', c.reason)).join(' · ')}
            </span>
          )}
        </>
      ),
    });
  }
  steps.push({
    key: 'fill',
    at: p.entry_time,
    title: t('trades.timeline.fill', { side: p.side, volume: format.number(p.volume) }),
    tone: 'neutral',
    body: t('trades.timeline.fillBody', {
      price: price(p.entry_price),
      sl: price(detail.intent?.sl ?? null),
      tp: price(detail.intent?.tp ?? null),
    }),
  });
  for (const [i, e] of events.entries()) {
    if (e.type !== 'STOP_MOVED') continue;
    const kind = typeof e.payload.kind === 'string' ? e.payload.kind : null;
    steps.push({
      key: `stop-${String(i)}`,
      at: e.at,
      title: kind
        ? t('trades.timeline.stopMovedKind', { kind: translateCode(i18n, 'exitReason', kind) })
        : t('trades.timeline.stopMoved'),
      tone: 'neutral',
      body: t('trades.timeline.stopBody', { old: price(num(e.payload.old)), new: price(num(e.payload.new)) }),
    });
  }
  if (p.status === 'CLOSED') {
    steps.push({
      key: 'exit',
      at: p.exit_time,
      title: t('trades.timeline.exit', {
        reason: p.exit_reason ? translateCode(i18n, 'exitReason', p.exit_reason) : '—',
      }),
      tone: (p.net ?? 0) >= 0 ? 'good' : 'bad',
      body: t('trades.timeline.exitBody', {
        price: price(p.exit_price),
        net: format.number(p.net, { maximumFractionDigits: 2, signDisplay: 'exceptZero' }),
        r: format.number(p.r_multiple, { maximumFractionDigits: 2, signDisplay: 'exceptZero' }),
      }),
    });
  }
  return steps.sort((a, b) => (a.at ?? '').localeCompare(b.at ?? ''));
}

/** The per-trade drawer: timeline, reasons and a link to the trade on the chart. */
export function TradeDrawer({
  engineId,
  ticket,
  onClose,
}: {
  engineId: string;
  ticket: number;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const titleId = useId();
  const close = useRef<HTMLButtonElement>(null);
  const detail = useQuery({
    queryKey: tradeKeys.detail(engineId, ticket),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/trades/${String(ticket)}`, TradeDetailSchema, {
        signal,
      }),
  });
  const steps = useSteps(detail.data);

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

  const p = detail.data?.position;
  const risk = p ? initialRisk(p.entry_price, detail.data?.intent?.sl) : null;
  const chartLink = p
    ? `/charts?symbol=${encodeURIComponent(p.symbol)}${detail.data?.decision ? `&decision=${encodeURIComponent(detail.data.decision.decision_id)}` : ''}`
    : null;
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
            {p
              ? t('trades.drawer.title', { ticket, symbol: p.symbol, side: p.side })
              : t('trades.drawer.loading', { ticket })}
          </h2>
          <button ref={close} type="button" onClick={onClose} className="rounded px-2 py-1 text-sm underline">
            {t('nav.close')}
          </button>
        </div>
        {detail.isError ? (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {t('dashboard.loadFailed')}
          </p>
        ) : !detail.data ? (
          <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
        ) : (
          <>
            {risk !== null && p && (
              <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
                {t('trades.drawer.risk', { risk: format.number(risk, { maximumFractionDigits: 6 }) })}
              </p>
            )}
            <ol
              aria-label={t('trades.timeline.label')}
              className="relative ml-2 border-l border-slate-200 dark:border-slate-700"
            >
              {steps.map((step) => (
                <li key={step.key} className="mb-4 ml-4">
                  <span
                    aria-hidden="true"
                    className={`absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full ${DOT[step.tone]}`}
                  />
                  <p className="text-sm font-medium">{step.title}</p>
                  <p className="text-xs text-slate-500">{format.dateTime(step.at)}</p>
                  <div className="mt-0.5 text-sm">{step.body}</div>
                </li>
              ))}
            </ol>
            {chartLink && (
              <Link to={chartLink} className="text-sm underline">
                {t('trades.drawer.chart')}
              </Link>
            )}
          </>
        )}
      </div>
    </div>
  );
}
