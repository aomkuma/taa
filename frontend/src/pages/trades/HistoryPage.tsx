import { useInfiniteQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { z } from 'zod';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { useLiveTrades, useTradeDrawer } from './hooks';
import { ManualTradesCard } from './ManualTradesCard';
import { type Trade, TradesPageSchema, tradeKeys } from './schemas';
import { TradeDrawer } from './TradeDrawer';
import { heldMinutes, tradesCsv } from './tradeMath';

const PAGE = 50;
const EXPORT_PAGE = 200;
/** A guard for the export loop: 50 000 trades. */
const EXPORT_MAX_PAGES = 250;
const TH = 'py-1 pr-3 font-normal whitespace-nowrap';
const TD = 'py-1.5 pr-3 whitespace-nowrap tabular-nums';

function tradesPath(engineId: string, symbol: string, limit: number, cursor: string | null) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (symbol) query.set('symbol', symbol);
  if (cursor) query.set('cursor', cursor);
  return `/engines/${encodeURIComponent(engineId)}/trades?${query.toString()}`;
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * PLAN §A15 history (TAA-907): closed trades, symbol filter, CSV export, per-trade drawer; then the owner's
 * closed manual trades with "signal vs bot vs me" (TAA-1006).
 */
export function HistoryPage() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const drawer = useTradeDrawer();
  const [symbol, setSymbol] = useState('');
  const [exporting, setExporting] = useState<'idle' | 'busy' | 'failed'>('idle');
  useLiveTrades(id);

  const filter = symbol.trim().toUpperCase();
  const trades = useInfiniteQuery({
    queryKey: tradeKeys.closed(id, filter),
    queryFn: ({ pageParam, signal }) =>
      apiGet(tradesPath(id, filter, PAGE, pageParam), TradesPageSchema, { signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows: Trade[] = trades.data?.pages.flatMap((p) => p.items) ?? [];

  const exportCsv = async () => {
    setExporting('busy');
    try {
      const all: Trade[] = [];
      let cursor: string | null = null;
      for (let i = 0; i < EXPORT_MAX_PAGES; i++) {
        // straight from the API: the export needs every page, the table keeps its own cache
        const page: z.infer<typeof TradesPageSchema> = await apiGet(
          tradesPath(id, filter, EXPORT_PAGE, cursor),
          TradesPageSchema,
        );
        all.push(...page.items);
        cursor = page.next_cursor;
        if (cursor === null) break;
      }
      download(`taa-trades${filter ? `-${filter}` : ''}.csv`, tradesCsv(all));
      setExporting('idle');
    } catch {
      setExporting('failed');
    }
  };

  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 6 });
  const signed = (value: number | null) =>
    format.number(value, { maximumFractionDigits: 2, signDisplay: 'exceptZero' });
  const held = (minutes: number | null) =>
    minutes === null ? '—' : t('trades.duration', { h: Math.floor(minutes / 60), m: minutes % 60 });

  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.history')}</h1>
      <Card
        title={t('trades.closed.title')}
        action={
          <button
            type="button"
            disabled={exporting === 'busy'}
            onClick={() => void exportCsv()}
            className="rounded border border-slate-300 px-2 py-1 text-sm dark:border-slate-700"
          >
            {exporting === 'busy' ? t('trades.closed.exporting') : t('trades.closed.export')}
          </button>
        }
      >
        <label className="mb-3 flex items-center gap-2 text-sm">
          {t('trades.closed.symbol')}
          <input
            type="search"
            value={symbol}
            onChange={(event) => {
              setSymbol(event.target.value);
            }}
            className="w-40 rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          />
        </label>
        {exporting === 'failed' && (
          <p role="alert" className="mb-2 text-sm text-red-700 dark:text-red-400">
            {t('trades.closed.exportFailed')}
          </p>
        )}
        {trades.data === undefined ? (
          <p className="text-sm text-slate-500">
            {trades.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
          </p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-500">{t('trades.closed.none')}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className={TH}>{t('trades.col.position')}</th>
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
        <p className="mt-2 text-xs text-slate-500">{t('trades.closed.note')}</p>
      </Card>
      <div className="mt-4">
        <ManualTradesCard />
      </div>
      {drawer.ticket !== null && <TradeDrawer engineId={id} ticket={drawer.ticket} onClose={drawer.close} />}
    </section>
  );
}
