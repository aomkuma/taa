import { useTranslation } from 'react-i18next';

import { useEngineStatus } from '@/engine/context';
import type { ForeignPosition } from '@/engine/schemas';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

const TH = 'px-2 py-1 text-left font-medium';
const TD = 'px-2 py-1 tabular-nums';

function sideText(t: (key: 'opportunities.buy' | 'opportunities.sell') => string, side: string) {
  return side === 'BUY' ? t('opportunities.buy') : t('opportunities.sell');
}

/**
 * Positions on the MT5 account that the bot did not open (manual trades), live from the engine heartbeat.
 * Read-only: the bot never manages or closes them, but they count toward its limits (heat, leverage) while
 * `risk.foreign_positions_policy` is `count`.
 */
export function ManualPositionsCard({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const account = status.data?.heartbeat?.account;
  const positions: ForeignPosition[] | null | undefined = account?.foreign_positions;
  if (positions === undefined || positions === null) {
    // an engine older than this report, or no account snapshot yet
    return compact ? null : (
      <Card title={t('trades.manual.title')}>
        <p className="text-sm text-slate-500">{t('trades.manual.unknown')}</p>
      </Card>
    );
  }
  if (compact && positions.length === 0) return null;
  const currency = account?.currency ?? 'USD';
  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 6 });
  const counted = positions.filter((p) => p.counted);
  const risk = counted.reduce((sum, p) => sum + (p.risk_to_stop ?? 0), 0);
  const noStop = positions.filter((p) => p.risk_to_stop === null).length;
  const pnl = positions.reduce((sum, p) => sum + p.profit + p.swap, 0);
  return (
    <Card
      title={t('trades.manual.title')}
      action={
        positions.length > 0 && (
          <span className="text-sm tabular-nums">
            {t('trades.manual.total', { pnl: format.money(pnl, currency, { signDisplay: 'exceptZero' }) })}
          </span>
        )
      }
    >
      {positions.length === 0 ? (
        <p className="text-sm text-slate-500">{t('trades.manual.none')}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className={TH}>{t('trades.manual.symbol')}</th>
                  <th className={TH}>{t('trades.manual.volume')}</th>
                  {!compact && <th className={TH}>{t('trades.manual.open')}</th>}
                  {!compact && <th className={TH}>{t('trades.manual.current')}</th>}
                  <th className={TH}>{t('trades.manual.stop')}</th>
                  {!compact && <th className={TH}>{t('trades.manual.target')}</th>}
                  <th className={TH}>{t('trades.manual.pnl')}</th>
                  <th className={TH}>{t('trades.manual.risk')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {positions.map((p) => {
                  const value = p.profit + p.swap;
                  return (
                    <tr key={p.ticket}>
                      <td className="px-2 py-1">
                        <span className="font-medium">{p.symbol}</span>{' '}
                        <span className="text-xs text-slate-500">{sideText(t, p.side)}</span>
                        {!compact && (
                          <span className="block text-xs text-slate-500">
                            #{p.ticket} · {format.dateTime(p.opened_at)}
                            {p.comment && ` · ${p.comment}`}
                          </span>
                        )}
                      </td>
                      <td className={TD}>{format.number(p.volume)}</td>
                      {!compact && <td className={TD}>{price(p.price_open)}</td>}
                      {!compact && <td className={TD}>{price(p.price_current)}</td>}
                      <td className={TD}>
                        {p.sl === null ? (
                          <span className="text-amber-800 dark:text-amber-300">
                            {t('trades.manual.noStop')}
                          </span>
                        ) : (
                          price(p.sl)
                        )}
                      </td>
                      {!compact && <td className={TD}>{price(p.tp)}</td>}
                      <td
                        className={`${TD} ${value > 0 ? 'text-emerald-700 dark:text-emerald-400' : value < 0 ? 'text-red-700 dark:text-red-400' : ''}`}
                      >
                        {format.money(value, currency, { signDisplay: 'exceptZero' })}
                      </td>
                      <td className={TD}>
                        {p.risk_to_stop === null ? '—' : format.money(p.risk_to_stop, currency)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {counted.length > 0
              ? t('trades.manual.counted', { risk: format.money(risk, currency) })
              : t('trades.manual.notCounted')}
          </p>
          {noStop > 0 && (
            <p role="alert" className="mt-1 text-sm text-amber-800 dark:text-amber-300">
              {t('trades.manual.noStopWarning', { n: noStop })}
            </p>
          )}
        </>
      )}
    </Card>
  );
}
