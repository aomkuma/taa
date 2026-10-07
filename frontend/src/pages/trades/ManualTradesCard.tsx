import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { ManualLinkDialog } from './ManualLinkDialog';
import { type ManualTrade, manualKeys, manualPath, ManualTradesSchema } from './manualSchemas';

const TH = 'px-2 py-1 text-left font-medium';
const TD = 'px-2 py-1 tabular-nums';

/** Which signal a manual trade followed, after the owner's correction (TAA-1006). */
export function FollowedSignal({ trade }: { trade: ManualTrade }) {
  const { t, i18n } = useTranslation();
  const e = trade.effective;
  if (!e.followed || e.strategy === null) return <>{t('trades.manual.link.none')}</>;
  const level =
    e.confidence === 'HIGH'
      ? t('trades.manual.link.high')
      : e.confidence === 'LIKELY'
        ? t('trades.manual.link.likely')
        : t('trades.manual.link.owner');
  return (
    <>
      {t('trades.manual.link.follows', { strategy: translateCode(i18n, 'strategyName', e.strategy) })} (
      {level})
    </>
  );
}

/**
 * Closed manual trades with "signal vs bot vs me" (TAA-1006): the owner's result from the MT5 deals next to the
 * signal's PLAN shadow trade and the bot's paper position, all in R.
 */
export function ManualTradesCard() {
  const { t } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const [editing, setEditing] = useState<ManualTrade | null>(null);
  const closed = useQuery({
    queryKey: manualKeys.list(id, 'CLOSED'),
    queryFn: ({ signal }) =>
      apiGet(manualPath(id, '?status=CLOSED&limit=100'), ManualTradesSchema, { signal }),
    enabled: engineId !== null,
  });
  const r = (value: number | null) =>
    value === null
      ? '—'
      : `${format.number(value, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}R`;
  const items = closed.data?.items ?? [];
  return (
    <Card title={t('trades.manual.closed.title')}>
      {closed.data === undefined ? (
        <p className="text-sm text-slate-500">
          {closed.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('trades.manual.closed.none')}</p>
      ) : (
        <div className="overflow-x-auto">
          <table aria-label={t('trades.manual.closed.title')} className="w-full text-sm">
            <thead className="text-xs text-slate-500">
              <tr>
                <th className={TH}>{t('trades.manual.symbol')}</th>
                <th className={TH}>{t('trades.manual.closed.signal')}</th>
                <th className={TH}>{t('trades.manual.closed.me')}</th>
                <th className={TH}>{t('trades.manual.closed.signalR')}</th>
                <th className={TH}>{t('trades.manual.closed.botR')}</th>
                <th className={TH}>{t('trades.manual.pnl')}</th>
                <th className={TH}>
                  <span className="sr-only">{t('trades.manual.correct')}</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {items.map((m) => (
                <tr key={m.position_id}>
                  <td className="px-2 py-1">
                    <span className="font-medium">{m.symbol}</span>{' '}
                    <span className="text-xs text-slate-500">
                      {m.side === 'BUY' ? t('opportunities.buy') : t('opportunities.sell')}
                    </span>
                    <span className="block text-xs text-slate-500">
                      #{m.ticket} · {format.dateTime(m.opened_at)}
                    </span>
                  </td>
                  <td className="px-2 py-1 text-xs">
                    <FollowedSignal trade={m} />
                  </td>
                  <td className={`${TD} font-semibold`}>{r(m.r_multiple)}</td>
                  <td className={TD}>{r(m.compare.signal_r)}</td>
                  <td className={TD}>
                    {m.compare.bot_status === 'OPEN' ? t('trades.manual.closed.botOpen') : r(m.compare.bot_r)}
                    {m.compare.bot_source !== null && (
                      <span className="ml-1 text-xs text-slate-500">
                        {t(`trades.manual.closed.source.${m.compare.bot_source}`)}
                      </span>
                    )}
                  </td>
                  <td className={TD}>
                    {format.number(m.net_profit, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}
                  </td>
                  <td className="px-2 py-1">
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(m);
                      }}
                      className="text-xs underline"
                    >
                      {t('trades.manual.correct')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">{t('trades.manual.closed.note')}</p>
        </div>
      )}
      {editing && (
        <ManualLinkDialog
          engineId={id}
          trade={editing}
          onClose={() => {
            setEditing(null);
          }}
        />
      )}
    </Card>
  );
}
