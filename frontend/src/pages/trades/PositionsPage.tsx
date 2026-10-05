import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useAuthState } from '@/auth/hooks';
import { useEngine, useEngineStatus } from '@/engine/context';
import { engineKey } from '@/engine/schemas';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { controlsOf } from '@/pages/risk/riskModel';
import { EngineConfigSchema, riskKeys } from '@/pages/risk/schemas';
import { Link } from 'react-router';

import { OrderIntentsPageSchema, PaperIntentsPageSchema, TradesPageSchema, tradeKeys } from './schemas';
import { useLiveTrades, useTradeDrawer } from './hooks';
import { ClosePositionDialog } from './ClosePositionDialog';
import { TradeDrawer } from './TradeDrawer';
import { excursionR, initialRisk, openR } from './tradeMath';

const PAGE = 200;
const TH = 'py-1 pr-3 font-normal whitespace-nowrap';
const TD = 'py-1.5 pr-3 whitespace-nowrap tabular-nums';

/** PLAN §A15 positions (TAA-907): open positions with R, P/L, stop state and excursions; pending orders. */
export function PositionsPage() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const base = `/engines/${encodeURIComponent(id)}`;
  const status = useEngineStatus();
  const drawer = useTradeDrawer();
  useLiveTrades(id);

  const open = useQuery({
    queryKey: tradeKeys.open(id),
    queryFn: ({ signal }) =>
      apiGet(`${base}/positions?status=OPEN&limit=${String(PAGE)}`, TradesPageSchema, { signal }),
  });
  // The initial stop (the trade's 1R) is on its intent; the position's own stop may have moved since.
  const filled = useQuery({
    queryKey: [...engineKey(id), 'intents', 'paper', 'FILLED'],
    queryFn: ({ signal }) =>
      apiGet(`${base}/intents?kind=paper&status=FILLED&limit=${String(PAGE)}`, PaperIntentsPageSchema, {
        signal,
      }),
  });
  const pending = useQuery({
    queryKey: tradeKeys.paperIntents(id),
    queryFn: ({ signal }) =>
      apiGet(`${base}/intents?kind=paper&status=PENDING&limit=${String(PAGE)}`, PaperIntentsPageSchema, {
        signal,
      }),
  });
  const mode = status.data?.heartbeat?.mode ?? status.data?.run?.mode;
  const broker = useQuery({
    queryKey: tradeKeys.orderIntents(id),
    queryFn: ({ signal }) =>
      apiGet(`${base}/intents?kind=broker&limit=50`, OrderIntentsPageSchema, { signal }),
    enabled: mode === 'DEMO',
  });
  const config = useQuery({
    queryKey: riskKeys.config(id),
    queryFn: ({ signal }) => apiGet(`${base}/config`, EngineConfigSchema, { signal }),
    retry: false,
  });
  const auth = useAuthState();
  // closes need step-up and the engine's control code; ADMIN has no trading controls (PLAN §A30)
  const canClose =
    auth.data?.status === 'signed_in' &&
    auth.data.session.user.role !== 'ADMIN' &&
    controlsOf(config.data).engineCode;
  const [closing, setClosing] = useState<{ ticket: number; label: string } | null>(null);
  const initialStops = useMemo(
    () => new Map((filled.data?.items ?? []).map((i) => [i.intent_id, i.sl])),
    [filled.data],
  );

  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 6 });
  const r = (value: number | null) =>
    format.number(value, { maximumFractionDigits: 2, signDisplay: 'exceptZero' });

  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.positions')}</h1>
      <div className="grid gap-4">
        <Card
          title={t('trades.open.title')}
          action={
            <Link to="/risk" className="text-sm underline">
              {t('controls.toRisk')}
            </Link>
          }
        >
          {open.data === undefined ? (
            <p className="text-sm text-slate-500">
              {open.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
            </p>
          ) : open.data.items.length === 0 ? (
            <p className="text-sm text-slate-500">{t('trades.open.none')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className={TH}>{t('trades.col.position')}</th>
                    <th className={TH}>{t('trades.col.entry')}</th>
                    <th className={TH}>{t('trades.col.current')}</th>
                    <th className={TH}>{t('trades.col.slTp')}</th>
                    <th className={TH}>{t('trades.col.stop')}</th>
                    <th className={TH}>{t('trades.col.pnl')}</th>
                    <th className={TH}>{t('trades.col.r')}</th>
                    <th className={TH}>{t('trades.col.maeMfe')}</th>
                    <th className={TH}>{t('trades.col.opened')}</th>
                    {canClose && (
                      <th className={TH}>
                        <span className="sr-only">{t('controls.close.column')}</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {open.data.items.map((p) => {
                    const risk = initialRisk(
                      p.entry_price,
                      initialStops.get(p.intent_id) ?? (p.stop_kind === 'SL' ? p.sl : null),
                    );
                    return (
                      <tr key={p.ticket} className="border-t border-slate-100 dark:border-slate-800">
                        <td className={TD}>
                          <button
                            type="button"
                            className="font-medium underline"
                            onClick={() => {
                              drawer.open(p.ticket);
                            }}
                          >
                            #{p.ticket} {p.symbol} {p.side} {format.number(p.volume)}
                          </button>
                        </td>
                        <td className={TD}>{price(p.entry_price)}</td>
                        <td className={TD}>{price(p.price_current)}</td>
                        <td className={TD}>
                          {price(p.sl)} / {price(p.tp)}
                        </td>
                        <td className={TD}>{translateCode(i18n, 'exitReason', p.stop_kind)}</td>
                        <td className={TD}>
                          {format.number(p.profit, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}
                        </td>
                        <td className={TD}>{r(openR(p, risk))}</td>
                        <td className={TD}>
                          {r(excursionR(-p.mae, risk))} / {r(excursionR(p.mfe, risk))}
                        </td>
                        <td className={TD}>{format.dateTime(p.entry_time)}</td>
                        {canClose && (
                          <td className={TD}>
                            <button
                              type="button"
                              onClick={() => {
                                setClosing({
                                  ticket: p.ticket,
                                  label: `#${String(p.ticket)} ${p.symbol} ${p.side}`,
                                });
                              }}
                              className="rounded border border-red-700 px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-400 dark:text-red-400 dark:hover:bg-red-950"
                            >
                              {t('controls.close.button')}
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-xs text-slate-500">{t('trades.open.note')}</p>
        </Card>

        <Card title={t('trades.pending.title')}>
          {pending.data === undefined ? (
            <p className="text-sm text-slate-500">
              {pending.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
            </p>
          ) : pending.data.items.length === 0 ? (
            <p className="text-sm text-slate-500">{t('trades.pending.none')}</p>
          ) : (
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {pending.data.items.map((i) => (
                <li key={i.intent_id} className="flex flex-wrap justify-between gap-x-3 py-1.5 text-sm">
                  <span className="font-medium">
                    {i.symbol} {i.side} {format.number(i.volume)} · {i.entry_type} {price(i.price)}
                  </span>
                  <span className="text-slate-500">
                    {t('trades.pending.expires', { time: format.dateTime(i.expires_at) })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {mode === 'DEMO' && (
          <Card title={t('trades.broker.title')}>
            {broker.data === undefined ? (
              <p className="text-sm text-slate-500">
                {broker.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
              </p>
            ) : broker.data.items.length === 0 ? (
              <p className="text-sm text-slate-500">{t('trades.broker.none')}</p>
            ) : (
              <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                {broker.data.items.map((i) => (
                  <li key={i.intent_id} className="py-1.5 text-sm">
                    <div className="flex flex-wrap justify-between gap-x-3">
                      <span className="font-medium">
                        {i.symbol} {i.side} {format.number(i.volume)} ·{' '}
                        {translateCode(i18n, 'orderState', i.state)}
                      </span>
                      <span className="text-slate-500">{format.dateTime(i.created_at)}</span>
                    </div>
                    <span className="text-xs text-slate-500">
                      {t('trades.broker.detail', {
                        requested: price(i.price_requested),
                        fill: price(i.fill_price),
                        sl: price(i.sl),
                        ticket: i.position_ticket ?? '—',
                      })}
                      {i.retcode_desc && ` · ${i.retcode_desc}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>
      {drawer.ticket !== null && <TradeDrawer engineId={id} ticket={drawer.ticket} onClose={drawer.close} />}
      {closing && (
        <ClosePositionDialog
          engineId={id}
          ticket={closing.ticket}
          label={closing.label}
          onClose={() => {
            setClosing(null);
          }}
        />
      )}
    </section>
  );
}
