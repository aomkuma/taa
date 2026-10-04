import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { useEngine, useEngineStatus } from '@/engine/context';

import { isTradingMode, type TradingMode } from './modes';

const MODE_STYLE: Record<TradingMode, string> = {
  BACKTEST: 'bg-slate-200 text-slate-900 dark:bg-slate-800 dark:text-slate-100',
  PAPER: 'bg-sky-100 text-sky-950 dark:bg-sky-950 dark:text-sky-100',
  DEMO: 'bg-amber-200 text-amber-950 dark:bg-amber-900 dark:text-amber-50',
  LIVE: 'bg-red-700 text-white',
};

const BAR = 'px-4 py-1.5 text-center text-sm font-medium';

/**
 * Which mode the shown engine trades in (PLAN §A15 "mode banner"), from its newest heartbeat or else its latest
 * run; plus the kill switch when it is active. Nothing is shown while the mode is not known.
 */
export function ModeBanner() {
  const { t } = useTranslation();
  const { state, engineId, own } = useEngine();
  const status = useEngineStatus();

  if (state !== 'ready') return null;
  if (engineId === null) {
    return (
      <p className={`${BAR} bg-slate-200 dark:bg-slate-800`}>
        {t('shell.noEngine')}{' '}
        <Link to="/engines" className="underline">
          {t('shell.linkEngine')}
        </Link>
      </p>
    );
  }
  if (!own) {
    return <p className={`${BAR} bg-slate-200 dark:bg-slate-800`}>{t('shell.marketFeed')}</p>;
  }
  const data = status.data;
  if (data === undefined) return null;
  const mode = data.heartbeat?.mode ?? data.run?.mode ?? null;
  const killSwitch = data.kill_switch.active || data.heartbeat?.kill_switch === true;
  return (
    <>
      {mode !== null &&
        (isTradingMode(mode) ? (
          <p data-mode={mode} className={`${BAR} ${MODE_STYLE[mode]}`}>
            {t(`shell.mode.${mode}`)}
          </p>
        ) : (
          <p className={`${BAR} bg-slate-200 dark:bg-slate-800`}>{t('shell.modeUnknown', { mode })}</p>
        ))}
      {killSwitch && (
        <p role="alert" className={`${BAR} bg-red-700 text-white`}>
          {t('shell.killSwitch')}
        </p>
      )}
    </>
  );
}
