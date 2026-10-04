import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { apiGet } from '@/api/client';
import { StaleBadge } from '@/app/shell/StaleBadge';
import { useServerNow } from '@/app/useNow';
import { useEngine, useEngineStatus } from '@/engine/context';
import { engineHealth } from '@/engine/health';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';

import { Gauge } from '@/components/Gauge';
import { lossUsed } from '@/components/gaugeLevels';
import { dashboardKeys, RECENT } from './keys';
import { BreakersSchema, DecisionsPageSchema, NotificationsPageSchema, PositionsPageSchema } from './schemas';

export function Card({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return error ? (
    <p role="alert" className="text-sm text-red-700 dark:text-red-400">
      {t('dashboard.loadFailed')}
    </p>
  ) : (
    <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <dt className="text-slate-600 dark:text-slate-400">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

const OK = 'text-emerald-700 dark:text-emerald-400';
const BAD = 'text-red-700 dark:text-red-400';

function useEngineId(): string {
  const { engineId } = useEngine();
  return engineId ?? '';
}

/** Engine, MT5, clock and sync health (PLAN §A15). */
export function HealthCard() {
  const { t } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const serverNow = useServerNow(5_000);
  const beat = status.data?.heartbeat;
  const health = engineHealth(beat, serverNow);
  const reporting = health === 'online' || health === 'disconnected';
  return (
    <Card title={t('dashboard.health.title')}>
      {status.data === undefined ? (
        <Loading error={status.isError} />
      ) : (
        <dl>
          <Row label={t('dashboard.health.engine')}>
            <span className={reporting ? OK : BAD}>
              {t(`shell.health.${health}`, { since: beat ? format.dateTime(beat.received_at) : '' })}
            </span>
          </Row>
          <Row label={t('dashboard.health.mt5')}>
            {beat && reporting ? (
              <span className={beat.connected ? OK : BAD}>
                {t(beat.connected ? 'dashboard.health.connected' : 'dashboard.health.notConnected')}
              </span>
            ) : (
              '—'
            )}
          </Row>
          <Row label={t('dashboard.health.clock')}>
            {beat && reporting ? (
              <span className={beat.clock_verified ? OK : BAD}>
                {t(beat.clock_verified ? 'dashboard.health.verified' : 'dashboard.health.notVerified')}
              </span>
            ) : (
              '—'
            )}
          </Row>
          <Row label={t('dashboard.health.lastData')}>{format.dateTime(status.data.last_received_at)}</Row>
          <Row label={t('dashboard.health.backlog')}>{format.number(beat?.outbox_pending ?? null)}</Row>
        </dl>
      )}
    </Card>
  );
}

/** Equity, balance, loss limits, drawdown and open risk from the engine's account snapshot. */
export function AccountCard() {
  const { t } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const serverNow = useServerNow(5_000);
  const beat = status.data?.heartbeat;
  const account = beat?.account ?? null;
  const health = engineHealth(beat, serverNow);

  if (status.data === undefined) {
    return (
      <Card title={t('dashboard.account.title')}>
        <Loading error={status.isError} />
      </Card>
    );
  }
  if (account === null) {
    return (
      <Card title={t('dashboard.account.title')}>
        <p className="text-sm text-slate-500">{t('dashboard.account.none')}</p>
      </Card>
    );
  }
  const { currency, limits } = account;
  const pct = (value: number | null) => format.percent(value, { maximumFractionDigits: 2 });
  const signedPct = (value: number | null) =>
    format.percent(value, { maximumFractionDigits: 2, signDisplay: 'exceptZero' });
  const stale = health === 'silent' || health === 'stopped';
  return (
    <Card
      title={t('dashboard.account.title')}
      action={stale ? <StaleBadge since={beat?.received_at ?? null} /> : undefined}
    >
      <dl className="mb-4">
        <Row label={t('dashboard.account.equity')}>{format.money(account.equity, currency)}</Row>
        <Row label={t('dashboard.account.balance')}>{format.money(account.balance, currency)}</Row>
        <Row label={t('dashboard.account.marginFree')}>{format.money(account.margin_free, currency)}</Row>
      </dl>
      <div className="grid gap-4 sm:grid-cols-2">
        <Gauge
          label={t('dashboard.account.dayPnl')}
          used={lossUsed(account.day_pnl_percent)}
          limit={limits.daily_loss_percent}
          value={`${format.money(account.day_pnl, currency, { signDisplay: 'exceptZero' })} (${signedPct(account.day_pnl_percent)})`}
          limitText={pct(-limits.daily_loss_percent)}
        />
        <Gauge
          label={t('dashboard.account.weekPnl')}
          used={lossUsed(account.week_pnl_percent)}
          limit={limits.weekly_loss_percent}
          value={`${format.money(account.week_pnl, currency, { signDisplay: 'exceptZero' })} (${signedPct(account.week_pnl_percent)})`}
          limitText={pct(-limits.weekly_loss_percent)}
        />
        <Gauge
          label={t('dashboard.account.drawdown')}
          used={account.drawdown_percent}
          limit={limits.drawdown_percent}
          value={pct(account.drawdown_percent)}
          limitText={pct(limits.drawdown_percent)}
        />
        <Gauge
          label={t('dashboard.account.openRisk')}
          used={account.heat_percent}
          limit={limits.heat_percent}
          value={`${format.money(account.open_risk, currency)} (${pct(account.heat_percent)})`}
          limitText={pct(limits.heat_percent)}
        />
        <Gauge
          label={t('dashboard.account.losingStreak')}
          used={account.consecutive_losses}
          limit={limits.consecutive_losses}
          value={format.number(account.consecutive_losses)}
          limitText={format.number(limits.consecutive_losses)}
        />
      </div>
      {account.unknown_risk_positions > 0 && (
        <p role="alert" className="mt-3 text-sm text-amber-800 dark:text-amber-300">
          {t('dashboard.account.unknownRisk', { n: account.unknown_risk_positions })}
        </p>
      )}
      <p className="mt-3 text-xs text-slate-500">
        {t('dashboard.account.asOf', { time: format.dateTime(account.as_of) })}
      </p>
    </Card>
  );
}

/** Open positions: the count from the heartbeat, the newest paper positions from the replica. */
export function PositionsCard() {
  const { t } = useTranslation();
  const format = useFormat();
  const engineId = useEngineId();
  const status = useEngineStatus();
  const positions = useQuery({
    queryKey: dashboardKeys.positions(engineId),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/positions?status=OPEN&limit=${String(RECENT)}`,
        PositionsPageSchema,
        { signal },
      ),
  });
  const count = status.data?.heartbeat?.open_positions ?? status.data?.open_positions;
  const price = (value: number | null) => format.number(value, { maximumFractionDigits: 5 });
  return (
    <Card
      title={t('dashboard.positions.title')}
      action={
        <Link to="/positions" className="text-sm underline">
          {t('dashboard.viewAll')}
        </Link>
      }
    >
      <p className="mb-2 text-sm">{t('dashboard.positions.open', { n: format.number(count ?? null) })}</p>
      {positions.data === undefined ? (
        <Loading error={positions.isError} />
      ) : positions.data.items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('dashboard.positions.none')}</p>
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {positions.data.items.map((p) => (
            <li key={p.ticket} className="flex flex-wrap justify-between gap-x-3 py-1.5 text-sm">
              <span className="font-medium">
                {p.symbol} {p.side} {format.number(p.volume)}
              </span>
              <span className="text-slate-600 tabular-nums dark:text-slate-400">
                {t('dashboard.positions.prices', {
                  entry: price(p.entry_price),
                  sl: price(p.sl),
                  tp: price(p.tp),
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Kill switch and every breaker that is not CLOSED. */
export function BreakersCard() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const engineId = useEngineId();
  const status = useEngineStatus();
  const breakers = useQuery({
    queryKey: dashboardKeys.breakers(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/breakers?limit=1`, BreakersSchema, { signal }),
  });
  const killSwitch = status.data?.kill_switch.active === true || status.data?.heartbeat?.kill_switch === true;
  const open = breakers.data?.states.filter((s) => s.state !== 'CLOSED') ?? [];
  return (
    <Card
      title={t('dashboard.breakers.title')}
      action={
        <Link to="/risk" className="text-sm underline">
          {t('dashboard.viewAll')}
        </Link>
      }
    >
      <p className={`mb-2 text-sm font-medium ${killSwitch ? BAD : OK}`}>
        {t(killSwitch ? 'dashboard.breakers.killSwitchOn' : 'dashboard.breakers.killSwitchOff')}
      </p>
      {breakers.data === undefined ? (
        <Loading error={breakers.isError} />
      ) : open.length === 0 ? (
        <p className="text-sm text-slate-500">{t('dashboard.breakers.allClosed')}</p>
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {open.map((s) => (
            <li key={`${s.name}:${s.scope_key}`} className="py-1.5 text-sm">
              <span className={`font-medium ${BAD}`}>
                {translateCode(i18n, 'breaker', s.name)}
                {s.scope_key && ` · ${s.scope_key}`}
              </span>
              <span className="ml-2 text-slate-600 dark:text-slate-400">
                {t(s.latched ? 'dashboard.breakers.latched' : 'dashboard.breakers.open')} ·{' '}
                {format.dateTime(s.opened_at)}
              </span>
              {s.reason && <p className="text-xs text-slate-500">{s.reason}</p>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** The newest decisions of the trading profile (the scanner's advisory decisions are on their own pages). */
export function DecisionsCard() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const engineId = useEngineId();
  const decisions = useQuery({
    queryKey: dashboardKeys.decisions(engineId),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/decisions?profile=EXECUTION&limit=${String(RECENT)}`,
        DecisionsPageSchema,
        { signal },
      ),
  });
  return (
    <Card
      title={t('dashboard.decisions.title')}
      action={
        <Link to="/decisions" className="text-sm underline">
          {t('dashboard.viewAll')}
        </Link>
      }
    >
      {decisions.data === undefined ? (
        <Loading error={decisions.isError} />
      ) : decisions.data.items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('dashboard.decisions.none')}</p>
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {decisions.data.items.map((d) => (
            <li key={d.decision_id} className="py-1.5 text-sm">
              <div className="flex flex-wrap justify-between gap-x-3">
                <span className="font-medium">
                  {d.symbol} {d.action} · {translateCode(i18n, 'decision', d.decision)}
                </span>
                <span className="text-slate-500">{format.dateTime(d.created_at)}</span>
              </div>
              {d.reason_codes[0] !== undefined && (
                <p className="text-xs text-slate-500">{translateCode(i18n, 'reason', d.reason_codes[0])}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const SEVERITY: Record<string, string> = {
  CRITICAL: BAD,
  WARNING: 'text-amber-700 dark:text-amber-400',
};

/** The user's newest notifications. */
export function AlertsCard() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const alerts = useQuery({
    queryKey: dashboardKeys.notifications,
    queryFn: ({ signal }) =>
      apiGet(`/notifications?limit=${String(RECENT)}`, NotificationsPageSchema, { signal }),
  });
  return (
    <Card
      title={t('dashboard.alerts.title')}
      action={
        <Link to="/notifications" className="text-sm underline">
          {t('dashboard.viewAll')}
        </Link>
      }
    >
      {alerts.data === undefined ? (
        <Loading error={alerts.isError} />
      ) : alerts.data.items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('dashboard.alerts.none')}</p>
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {alerts.data.items.map((n) => (
            <li key={n.notification_id} className="flex flex-wrap justify-between gap-x-3 py-1.5 text-sm">
              <span className={`${n.read_at === null ? 'font-semibold' : ''} ${SEVERITY[n.severity] ?? ''}`}>
                {translateCode(i18n, 'notificationType', n.type)}
              </span>
              <span className="text-slate-500">{format.dateTime(n.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
