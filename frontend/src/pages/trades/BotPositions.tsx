import { useTranslation } from 'react-i18next';

import { useEngineStatus } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { botR } from './tradeMath';

const TH = 'py-1 pr-3 font-normal whitespace-nowrap';
const TD = 'py-1.5 pr-3 whitespace-nowrap tabular-nums';

/**
 * The bot's open positions on the broker account (DEMO/LIVE; TAA-1211), from the engine's newest heartbeat:
 * the stop in force, the floating P/L (swap included) and R from the intent's stop. Shown only while the engine
 * reports them (never in PAPER, whose book has its own card).
 */
export function BotPositionsCard({
  canClose,
  onClose,
}: {
  canClose: boolean;
  onClose: (ticket: number, label: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const positions = status.data?.heartbeat?.account?.bot_positions;
  if (positions === undefined || positions === null) return null;
  const mode = status.data?.heartbeat?.mode === 'LIVE' ? 'LIVE' : 'DEMO';
  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 6 });
  const signed = (value: number | null) =>
    format.number(value, { maximumFractionDigits: 2, signDisplay: 'exceptZero' });
  return (
    <Card title={t(`trades.bot.title.${mode}`)}>
      {positions.length === 0 ? (
        <p className="text-sm text-slate-500">{t('trades.bot.none')}</p>
      ) : (
        <div className="overflow-x-auto">
          <table aria-label={t(`trades.bot.title.${mode}`)} className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className={TH}>{t('trades.col.position')}</th>
                <th className={TH}>{t('trades.col.entry')}</th>
                <th className={TH}>{t('trades.col.current')}</th>
                <th className={TH}>{t('trades.col.slTp')}</th>
                <th className={TH}>{t('trades.col.pnl')}</th>
                <th className={TH}>{t('trades.col.r')}</th>
                <th className={TH}>{t('trades.col.opened')}</th>
                {canClose && (
                  <th className={TH}>
                    <span className="sr-only">{t('controls.close.column')}</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.ticket} className="border-t border-slate-100 dark:border-slate-800">
                  <td className={TD}>
                    <span className="font-medium">
                      #{p.ticket} {p.symbol} {p.side} {format.number(p.volume)}
                    </span>
                    {p.strategy !== null && (
                      <span className="block text-xs text-slate-500">
                        {translateCode(i18n, 'strategyName', p.strategy)}
                      </span>
                    )}
                  </td>
                  <td className={TD}>{price(p.price_open)}</td>
                  <td className={TD}>{price(p.price_current)}</td>
                  <td className={TD}>
                    {price(p.sl)} / {price(p.tp)}
                  </td>
                  <td className={TD}>{signed(p.profit + p.swap)}</td>
                  <td className={TD}>{signed(botR(p))}</td>
                  <td className={TD}>{format.dateTime(p.opened_at)}</td>
                  {canClose && (
                    <td className={TD}>
                      <button
                        type="button"
                        onClick={() => {
                          onClose(p.ticket, `#${String(p.ticket)} ${p.symbol} ${p.side}`);
                        }}
                        className="rounded border border-red-700 px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-400 dark:text-red-400 dark:hover:bg-red-950"
                      >
                        {t('controls.close.button')}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-2 text-xs text-slate-500">{t('trades.bot.note')}</p>
    </Card>
  );
}
