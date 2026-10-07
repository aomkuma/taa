import { useInfiniteQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useEngineStatus } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { type BrokerTrade, BrokerTradesPageSchema, tradeKeys } from './schemas';
import { heldMinutes } from './tradeMath';

const PAGE = 50;
const TH = 'py-1 pr-3 font-normal whitespace-nowrap';
const TD = 'py-1.5 pr-3 whitespace-nowrap tabular-nums';

function brokerTradesPath(engineId: string, symbol: string, cursor: string | null) {
  const query = new URLSearchParams({ limit: String(PAGE) });
  if (symbol) query.set('symbol', symbol);
  if (cursor) query.set('cursor', cursor);
  return `/engines/${encodeURIComponent(engineId)}/broker-trades?${query.toString()}`;
}

/**
 * The bot's closed positions on the broker account (DEMO/LIVE; TAA-1208), one row per MT5 position as in the
 * terminal's history. Shown while the engine trades on the broker account, or once such trades exist.
 */
export function BrokerTradesCard({ engineId, symbol }: { engineId: string; symbol: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const trades = useInfiniteQuery({
    queryKey: tradeKeys.broker(engineId, symbol),
    queryFn: ({ pageParam, signal }) =>
      apiGet(brokerTradesPath(engineId, symbol, pageParam), BrokerTradesPageSchema, { signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows: BrokerTrade[] = trades.data?.pages.flatMap((p) => p.items) ?? [];
  const engineMode = status.data?.heartbeat?.mode ?? status.data?.run?.mode ?? null;
  const mode = engineMode === 'LIVE' || rows[0]?.mode === 'LIVE' ? 'LIVE' : 'DEMO';
  const onBroker = engineMode === 'DEMO' || engineMode === 'LIVE';
  if (!onBroker && rows.length === 0) return null;

  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 6 });
  const signed = (value: number | null) =>
    format.number(value, { maximumFractionDigits: 2, signDisplay: 'exceptZero' });
  const held = (minutes: number | null) =>
    minutes === null ? '—' : t('trades.duration', { h: Math.floor(minutes / 60), m: minutes % 60 });

  return (
    <div className="mb-4">
      <Card title={t(`trades.brokerClosed.title.${mode}`)}>
        {trades.data === undefined ? (
          <p className="text-sm text-slate-500">
            {trades.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
          </p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-500">{t('trades.brokerClosed.none')}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table aria-label={t(`trades.brokerClosed.title.${mode}`)} className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className={TH}>{t('trades.col.position')}</th>
                    <th className={TH}>{t('trades.brokerClosed.strategy')}</th>
                    <th className={TH}>{t('trades.col.entryExit')}</th>
                    <th className={TH}>{t('trades.col.reason')}</th>
                    <th className={TH}>{t('trades.col.net')}</th>
                    <th className={TH}>{t('trades.col.r')}</th>
                    <th className={TH}>{t('trades.col.held')}</th>
                    <th className={TH}>{t('trades.col.closed')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.position_ticket} className="border-t border-slate-100 dark:border-slate-800">
                      <td className={TD}>
                        #{p.position_ticket} {p.symbol} {p.side} {format.number(p.volume)}
                        {p.part_index > 0 && (
                          <span className="ml-1 text-xs text-slate-500">
                            {t('trades.brokerClosed.part', { n: p.part_index + 1 })}
                          </span>
                        )}
                      </td>
                      <td className={TD}>{translateCode(i18n, 'strategyName', p.strategy)}</td>
                      <td className={TD}>
                        {price(p.entry_price)} → {price(p.exit_price)}
                      </td>
                      <td className={TD}>
                        {p.exit_reason ? translateCode(i18n, 'exitReason', p.exit_reason) : '—'}
                      </td>
                      <td className={TD}>{signed(p.net)}</td>
                      <td className={TD}>{signed(p.r_multiple)}</td>
                      <td className={TD}>{held(heldMinutes(p))}</td>
                      <td className={TD}>{format.dateTime(p.exit_time)}</td>
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
        <p className="mt-2 text-xs text-slate-500">{t('trades.brokerClosed.note')}</p>
      </Card>
    </div>
  );
}
