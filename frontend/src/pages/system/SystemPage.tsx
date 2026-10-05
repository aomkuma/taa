import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { useFormat } from '@/i18n/useFormat';
import { useLiveEvents } from '@/live/context';
import { Card } from '@/pages/dashboard/cards';

import {
  AuditVerifySchema,
  MaskedConfigSchema,
  type SystemStatus,
  SystemStatusSchema,
  systemKeys,
} from './schemas';

const GOOD = 'text-emerald-700 dark:text-emerald-400';
const BAD = 'text-red-700 dark:text-red-400';
/** Environment values shown as the terminal and account (the engine masked the login and every secret). */
const ACCOUNT_ENV = [
  'MT5_SERVER',
  'MT5_LOGIN',
  'TRADING_MODE',
  'MT5_TERMINAL_PATH',
  'BROKER_TIMEZONE',
  'ENABLE_DEMO_TRADING',
  'ENABLE_LIVE_TRADING',
] as const;

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5 text-sm">
      <dt className="text-slate-600 dark:text-slate-400">{label}</dt>
      <dd className="text-right font-medium break-all tabular-nums">{children}</dd>
    </div>
  );
}

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-500">{error ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
}

function YesNo({ value, good = true }: { value: boolean; good?: boolean }) {
  const { t } = useTranslation();
  return <span className={value === good ? GOOD : BAD}>{value ? t('system.yes') : t('system.no')}</span>;
}

function EngineCard({ status }: { status: SystemStatus }) {
  const { t } = useTranslation();
  const format = useFormat();
  const beat = status.heartbeat;
  return (
    <Card title={t('system.engine.title')}>
      <dl>
        <Row label={t('system.engine.label')}>{status.engine.label}</Row>
        <Row label={t('system.engine.run')}>
          {status.run ? `${status.run.mode} · ${status.run.status}` : t('system.none')}
        </Row>
        {status.run && <Row label={t('system.engine.started')}>{format.dateTime(status.run.started_at)}</Row>}
        {status.run?.version && <Row label={t('system.engine.version')}>{status.run.version}</Row>}
        {status.run?.config_hash && (
          <Row label={t('system.engine.configHash')}>
            <code className="text-xs">{status.run.config_hash.slice(0, 12)}</code>
          </Row>
        )}
        {beat === null ? (
          <Row label={t('system.engine.heartbeat')}>{t('system.none')}</Row>
        ) : (
          <>
            <Row label={t('system.engine.watch')}>
              <span className={beat.watch_status === 'OFFLINE' ? BAD : GOOD}>
                {beat.state === 'stopped'
                  ? t('system.engine.stopped')
                  : beat.watch_status === 'OFFLINE'
                    ? t('system.engine.offline')
                    : t('system.engine.online')}
              </span>
            </Row>
            <Row label={t('system.engine.mt5')}>
              <YesNo value={beat.connected} />
            </Row>
            <Row label={t('system.engine.clock')}>
              <YesNo value={beat.clock_verified} />
            </Row>
            <Row label={t('system.engine.market')}>
              {beat.market_open ? t('system.engine.marketOpen') : t('system.engine.marketClosed')}
              {beat.market_change_at &&
                ` · ${t('system.engine.until', { at: format.dateTime(beat.market_change_at) })}`}
            </Row>
            <Row label={t('system.engine.cycles')}>{format.number(beat.cycles)}</Row>
          </>
        )}
      </dl>
    </Card>
  );
}

function SyncCard({ status }: { status: SystemStatus }) {
  const { t } = useTranslation();
  const format = useFormat();
  const beat = status.heartbeat;
  const lag = beat ? (Date.parse(beat.received_at) - Date.parse(beat.at)) / 1000 : null;
  return (
    <Card title={t('system.sync.title')}>
      <dl>
        <Row label={t('system.sync.lastHeartbeat')}>
          {beat ? format.dateTime(beat.received_at) : t('system.none')}
        </Row>
        <Row label={t('system.sync.lag')}>
          {lag === null
            ? '—'
            : t('system.sync.seconds', { n: format.number(Math.max(0, lag), { maximumFractionDigits: 1 }) })}
        </Row>
        <Row label={t('system.sync.backlog')}>
          {beat?.outbox_pending == null ? '—' : format.number(beat.outbox_pending)}
        </Row>
        <Row label={t('system.sync.lastBatch')}>
          {status.last_received_at ? format.dateTime(status.last_received_at) : t('system.none')}
        </Row>
      </dl>
    </Card>
  );
}

function AccountCard({ engineId }: { engineId: string }) {
  const { t } = useTranslation();
  const config = useQuery({
    queryKey: systemKeys.config(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/config`, MaskedConfigSchema, { signal }),
  });
  const env = config.data?.config.env;
  return (
    <Card title={t('system.account.title')}>
      {env === undefined ? (
        <Loading error={config.isError} />
      ) : (
        <>
          <dl>
            {ACCOUNT_ENV.map((key) => {
              const value = env[key];
              return (
                <Row key={key} label={key}>
                  {typeof value === 'boolean' ? (
                    <YesNo value={value} good={key !== 'ENABLE_LIVE_TRADING'} />
                  ) : value === null || value === undefined ? (
                    '—'
                  ) : typeof value === 'string' || typeof value === 'number' ? (
                    String(value)
                  ) : (
                    JSON.stringify(value)
                  )}
                </Row>
              );
            })}
          </dl>
          <p className="mt-2 text-xs text-slate-500">{t('system.account.masked')}</p>
        </>
      )}
    </Card>
  );
}

function AuditCard({ engineId, status }: { engineId: string; status: SystemStatus }) {
  const { t } = useTranslation();
  const format = useFormat();
  const verify = useMutation({
    mutationFn: () => apiGet(`/engines/${encodeURIComponent(engineId)}/audit/verify`, AuditVerifySchema),
  });
  const stored = status.audit;
  const result = verify.data;
  return (
    <Card title={t('system.audit.title')}>
      <dl>
        <Row label={t('system.audit.stored')}>
          {stored === null ? (
            t('system.none')
          ) : (
            <span className={stored.status === 'OK' ? GOOD : BAD}>
              {stored.status === 'OK' ? t('system.audit.ok') : t('system.audit.broken')}
            </span>
          )}
        </Row>
        {stored !== null && (
          <>
            <Row label={t('system.audit.events')}>
              {`${format.number(stored.verified_seq ?? 0)} / ${format.number(stored.max_seq ?? 0)}`}
            </Row>
            {stored.updated_at && (
              <Row label={t('system.audit.checkedAt')}>{format.dateTime(stored.updated_at)}</Row>
            )}
          </>
        )}
      </dl>
      <button
        type="button"
        className="mt-2 rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
        disabled={verify.isPending}
        onClick={() => {
          verify.mutate();
        }}
      >
        {verify.isPending ? t('system.audit.verifying') : t('system.audit.verify')}
      </button>
      {result && (
        <p role="status" className={`mt-2 text-sm ${result.ok ? GOOD : BAD}`}>
          {result.ok
            ? t('system.audit.verifiedOk', { n: format.number(result.events_checked) })
            : t('system.audit.verifiedBad', {
                seq: result.first_bad_seq ?? '?',
                detail: result.detail,
              })}
        </p>
      )}
      {verify.isError && (
        <p role="alert" className={`mt-2 text-sm ${BAD}`}>
          {t('dashboard.loadFailed')}
        </p>
      )}
    </Card>
  );
}

/** PLAN §A15 System (TAA-913): engine health, sync, the masked terminal and account, audit-chain checks. */
export function SystemPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const status = useQuery({
    queryKey: systemKeys.status(id),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(id)}/status`, SystemStatusSchema, { signal }),
    enabled: engineId !== null,
  });
  useLiveEvents('status', () => {
    void queryClient.invalidateQueries({ queryKey: systemKeys.status(id) });
  });
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.system')}</h1>
      {status.data === undefined ? (
        <Loading error={status.isError} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <EngineCard status={status.data} />
          <SyncCard status={status.data} />
          <AccountCard engineId={id} />
          <AuditCard engineId={id} status={status.data} />
        </div>
      )}
    </section>
  );
}
