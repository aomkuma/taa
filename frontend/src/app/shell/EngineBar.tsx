import { useTranslation } from 'react-i18next';

import { useServerNow } from '@/app/useNow';
import { useEngine, useEngineStatus } from '@/engine/context';
import { type EngineHealth, engineHealth } from '@/engine/health';
import { useFormat } from '@/i18n/useFormat';
import { useLive } from '@/live/context';

import { StaleBadge } from './StaleBadge';

const HEALTH_DOT: Record<EngineHealth, string> = {
  online: 'bg-emerald-500',
  disconnected: 'bg-amber-500',
  stopped: 'bg-red-600',
  silent: 'bg-red-600',
  unknown: 'bg-slate-400',
};

function EnginePicker() {
  const { t } = useTranslation();
  const { engineId, engines, select } = useEngine();
  if (engines.length < 2) return null;
  return (
    <label className="flex items-center gap-1">
      <span className="sr-only">{t('shell.engine')}</span>
      <select
        value={engineId ?? ''}
        onChange={(event) => {
          select(event.target.value);
        }}
        className="rounded border border-slate-300 bg-white px-1 py-0.5 dark:border-slate-700 dark:bg-slate-900"
      >
        {engines.map((engine) => (
          <option key={engine.engine_id} value={engine.engine_id}>
            {engine.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function LiveIndicator() {
  const { t } = useTranslation();
  const { state, pausedSince } = useLive();
  switch (state) {
    case 'idle':
      return null;
    case 'live':
      return <span className="text-emerald-700 dark:text-emerald-400">{t('shell.live.live')}</span>;
    case 'connecting':
      return <span className="text-slate-500">{t('shell.live.connecting')}</span>;
    case 'reconnecting':
      return (
        <span className="flex items-center gap-1">
          <span className="text-slate-500">{t('shell.live.reconnecting')}</span>
          <StaleBadge since={pausedSince} />
        </span>
      );
    case 'ended':
      return <span className="text-slate-500">{t('shell.live.ended')}</span>;
  }
}

/**
 * The shown engine (picker when the user has several), its health from the newest heartbeat and the state of
 * live updates (PLAN §A15 "offline and stale indicators").
 */
export function EngineBar() {
  const { t } = useTranslation();
  const format = useFormat();
  const { state, engineId, own, engines } = useEngine();
  const status = useEngineStatus();
  const serverNow = useServerNow(5_000);

  if (state === 'loading') return <p className="mb-3 text-sm text-slate-500">{t('shell.loadingEngine')}</p>;
  if (state === 'error') {
    return (
      <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
        {t('shell.engineUnavailable')}
      </p>
    );
  }
  if (engineId === null || !own) return null;

  const label = engines.find((engine) => engine.engine_id === engineId)?.label ?? status.data?.engine.label;
  const heartbeat = status.data?.heartbeat;
  const health = engineHealth(heartbeat, serverNow);
  const since = heartbeat ? format.dateTime(heartbeat.received_at) : '';

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      {engines.length > 1 ? <EnginePicker /> : label && <span className="font-medium">{label}</span>}
      {status.isError ? (
        <span role="alert" className="text-red-700 dark:text-red-400">
          {t('shell.statusUnavailable')}
        </span>
      ) : (
        status.data && (
          <span className="flex items-center gap-1.5" data-health={health}>
            <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${HEALTH_DOT[health]}`} />
            {t(`shell.health.${health}`, { since })}
          </span>
        )
      )}
      {heartbeat && health !== 'silent' && health !== 'stopped' && !heartbeat.market_open && (
        <span className="text-slate-500">{t('shell.marketClosed')}</span>
      )}
      <LiveIndicator />
    </div>
  );
}
