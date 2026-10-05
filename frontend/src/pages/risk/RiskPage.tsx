import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useAuthState } from '@/auth/hooks';
import { EngineCodeField } from '@/components/EngineCodeField';
import { StepUpDialog } from '@/components/StepUpDialog';
import { CommandsPageSchema, commandKeys, ENGINE_CODE, postCommand } from '@/engine/commands';
import { useEngine, useEngineStatus } from '@/engine/context';
import { engineStatusKey } from '@/engine/schemas';
import { COMMAND_STATUSES, translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { useLiveEvents } from '@/live/context';
import { Card } from '@/pages/dashboard/cards';

import { EngineLimits } from './EngineLimits';
import { controlsOf, measuredLimits, type MeasuredLimit, sortBreakers, STATIC_LIMITS } from './riskModel';
import { BreakersPageSchema, EngineConfigSchema, KillSwitchPageSchema, riskKeys } from './schemas';

const PAGE = 20;
const SELECT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';
const LEVEL_TONE: Record<MeasuredLimit['level'], string> = {
  ok: 'text-emerald-700 dark:text-emerald-400',
  warn: 'text-amber-700 dark:text-amber-400',
  danger: 'text-red-700 dark:text-red-400',
  breached: 'font-semibold text-red-700 dark:text-red-400',
  unknown: 'text-slate-500',
};
const STATE_TONE: Record<string, string> = {
  OPEN: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
  HALF_OPEN: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  CLOSED: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
};

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-500">{error ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
}

function ReasonField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block font-medium">
        {t('controls.reason')}
      </label>
      <textarea
        id={id}
        value={value}
        maxLength={200}
        rows={2}
        onChange={(e) => {
          onChange(e.target.value);
        }}
        className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-950"
      />
    </div>
  );
}

type KillAction = 'halt' | 'flatten';

function KillDialog({
  engineId,
  action,
  onClose,
}: {
  engineId: string;
  action: KillAction;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState('');
  const [code, setCode] = useState('');
  const flatten = action === 'flatten';
  const validate = () => {
    if (reason.trim() === '') return t('controls.reasonRequired');
    if (flatten && !ENGINE_CODE.test(code)) return t('controls.engineCodeRequired');
    return null;
  };
  const confirm = async () => {
    await postCommand(
      engineId,
      flatten
        ? { type: 'FLATTEN_ALL', reason: reason.trim(), code }
        : { type: 'KILL_SWITCH_ACTIVATE', reason: reason.trim() },
    );
    await queryClient.invalidateQueries({ queryKey: commandKeys.all(engineId) });
  };
  return (
    <StepUpDialog
      title={t(flatten ? 'controls.flatten.title' : 'controls.halt.title')}
      confirmLabel={t(flatten ? 'controls.flatten.confirm' : 'controls.halt.confirm')}
      danger
      validate={validate}
      onConfirm={confirm}
      onClose={onClose}
    >
      <p>{t(flatten ? 'controls.flatten.body' : 'controls.halt.body')}</p>
      <ReasonField value={reason} onChange={setReason} />
      {flatten && <EngineCodeField value={code} onChange={setCode} />}
      <p className="text-xs text-slate-500">
        {t('controls.releaseLocal')} <code>python -m app.cli kill --release --reason &quot;...&quot;</code>
      </p>
    </StepUpDialog>
  );
}

function KillSwitchCard({ engineId, canControl }: { engineId: string; canControl: boolean }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const [dialog, setDialog] = useState<KillAction | null>(null);
  const config = useQuery({
    queryKey: riskKeys.config(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/config`, EngineConfigSchema, { signal }),
    retry: false,
  });
  const history = useQuery({
    queryKey: riskKeys.killSwitch(engineId),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/kill-switch?limit=${String(PAGE)}`,
        KillSwitchPageSchema,
        {
          signal,
        },
      ),
  });
  const controls = controlsOf(config.data);
  const active = status.data?.kill_switch.active ?? false;
  const last = history.data?.items[0];
  return (
    <Card title={t('controls.killSwitch')}>
      {status.data === undefined ? (
        <Loading error={status.isError} />
      ) : (
        <div
          role="status"
          className={`rounded p-3 text-sm ${active ? 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-100' : 'bg-emerald-50 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-100'}`}
        >
          <p className="font-semibold">
            {active
              ? t('controls.active', { mode: last ? translateCode(i18n, 'killMode', last.mode) : '—' })
              : t('controls.inactive')}
          </p>
          {last && (
            <p className="mt-0.5 text-xs">
              {t('controls.lastEvent', {
                action: t(last.action === 'RELEASE' ? 'controls.action.RELEASE' : 'controls.action.ACTIVATE'),
                actor: last.actor,
                source: last.source,
                time: format.dateTime(last.ts_utc),
                reason: last.reason,
              })}
            </p>
          )}
        </div>
      )}
      {canControl ? (
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <button
            type="button"
            disabled={active}
            onClick={() => {
              setDialog('halt');
            }}
            className="rounded bg-red-700 px-3 py-1.5 font-medium text-white hover:bg-red-800 disabled:opacity-50"
          >
            {t('controls.halt.button')}
          </button>
          <button
            type="button"
            disabled={!controls.flattenAllowed || !controls.engineCode}
            onClick={() => {
              setDialog('flatten');
            }}
            className="rounded border border-red-700 px-3 py-1.5 font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-400 dark:text-red-400 dark:hover:bg-red-950"
          >
            {t('controls.flatten.button')}
          </button>
        </div>
      ) : (
        <p className="mt-3 text-xs text-slate-500">{t('controls.noControls')}</p>
      )}
      {canControl && config.data && !controls.flattenAllowed && (
        <p className="mt-1 text-xs text-slate-500">{t('controls.flattenOff')}</p>
      )}
      {canControl && config.data && controls.flattenAllowed && !controls.engineCode && (
        <p className="mt-1 text-xs text-slate-500">{t('controls.noEngineCode')}</p>
      )}
      <p className="mt-2 text-xs text-slate-500">
        {t('controls.releaseLocal')} <code>python -m app.cli kill --release --reason &quot;...&quot;</code>
      </p>
      {history.data && history.data.items.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-medium">{t('controls.history')}</summary>
          <ul className="mt-1 divide-y divide-slate-100 text-sm dark:divide-slate-800">
            {history.data.items.map((e) => (
              <li key={`${e.ts_utc}-${e.action}`} className="py-1">
                <span className="font-medium">
                  {t(e.action === 'RELEASE' ? 'controls.action.RELEASE' : 'controls.action.ACTIVATE')} ·{' '}
                  {translateCode(i18n, 'killMode', e.mode)}
                </span>{' '}
                <span className="text-xs text-slate-500">
                  {format.dateTime(e.ts_utc)} · {e.actor} ({e.source}) · {e.reason}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {dialog && (
        <KillDialog
          engineId={engineId}
          action={dialog}
          onClose={() => {
            setDialog(null);
          }}
        />
      )}
    </Card>
  );
}

function LimitsCard({ engineId }: { engineId: string }) {
  const { t } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const config = useQuery({
    queryKey: riskKeys.config(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/config`, EngineConfigSchema, { signal }),
    retry: false,
  });
  const risk = config.data?.config.config?.risk;
  const beat = status.data?.heartbeat ?? null;
  const rows = measuredLimits(beat?.account ?? null, beat?.open_positions ?? null, risk);
  const value = (v: number | null, unit: 'percent' | 'count') =>
    v === null
      ? '—'
      : unit === 'percent'
        ? format.percent(v, { maximumFractionDigits: 2 })
        : format.number(v);
  return (
    <Card title={t('controls.limits.title')}>
      <table aria-label={t('controls.limits.title')} className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="py-1 pr-3 font-normal">{t('controls.limits.limit')}</th>
            <th className="py-1 pr-3 font-normal">{t('controls.limits.now')}</th>
            <th className="py-1 pr-3 font-normal">{t('controls.limits.max')}</th>
            <th className="py-1 font-normal">{t('controls.limits.state')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t border-slate-100 dark:border-slate-800">
              <th scope="row" className="py-1 pr-3 text-left font-normal">
                {t(`controls.limits.measured.${r.key}`)}
              </th>
              <td className="py-1 pr-3 tabular-nums">{value(r.used, r.unit)}</td>
              <td className="py-1 pr-3 tabular-nums">{value(r.limit, r.unit)}</td>
              <td className={`py-1 ${LEVEL_TONE[r.level]}`}>{t(`controls.limits.level.${r.level}`)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-xs text-slate-500">
        {beat?.account
          ? t('controls.limits.asOf', { time: format.dateTime(beat.account.as_of) })
          : t('controls.limits.noAccount')}
      </p>
      {risk && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-medium">{t('controls.limits.perTrade')}</summary>
          <dl className="mt-1 text-sm">
            {STATIC_LIMITS.map(([key, unit]) => {
              const v = risk[key];
              const shown =
                v === null || v === undefined
                  ? '—'
                  : unit === 'percent'
                    ? format.percent(v)
                    : unit === 'hours'
                      ? t('controls.limits.hours', { n: format.number(v) })
                      : format.number(v);
              return (
                <div key={key} className="flex justify-between gap-3 py-0.5">
                  <dt className="text-slate-600 dark:text-slate-400">{t(`controls.limits.static.${key}`)}</dt>
                  <dd className="tabular-nums">{shown}</dd>
                </div>
              );
            })}
          </dl>
          <p className="mt-1 text-xs text-slate-500">{t('controls.limits.localOnly')}</p>
        </details>
      )}
    </Card>
  );
}

function RiskLimitsCard() {
  const { t } = useTranslation();
  const status = useEngineStatus();
  const limits = status.data?.heartbeat?.account?.risk_limits;
  return (
    <Card title={t('riskLimits.title')}>
      {status.data === undefined ? (
        <Loading error={status.isError} />
      ) : limits ? (
        <EngineLimits limits={limits} />
      ) : (
        <p className="text-sm text-slate-500">{t('riskLimits.unavailable')}</p>
      )}
    </Card>
  );
}

function BreakersCard({ engineId }: { engineId: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const breakers = useInfiniteQuery({
    queryKey: riskKeys.breakers(engineId),
    queryFn: ({ pageParam, signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/breakers?limit=${String(PAGE)}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`,
        BreakersPageSchema,
        { signal },
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.events.next_cursor,
  });
  const first = breakers.data?.pages[0];
  const events = breakers.data?.pages.flatMap((p) => p.events.items) ?? [];
  const name = (n: string, scope: string) =>
    `${translateCode(i18n, 'breaker', n)}${scope ? ` (${scope})` : ''}`;
  return (
    <Card title={t('controls.breakers.title')}>
      {first === undefined ? (
        <Loading error={breakers.isError} />
      ) : (
        <>
          {first.states.length === 0 ? (
            <p className="text-sm text-slate-500">{t('controls.breakers.none')}</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
              {sortBreakers(first.states).map((b) => (
                <li
                  key={`${b.name}/${b.scope_key}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 py-1"
                >
                  <span>
                    {name(b.name, b.scope_key)}
                    {b.state !== 'CLOSED' && (
                      <span className="block text-xs text-slate-500">
                        {[
                          b.reason,
                          b.opened_at && t('controls.breakers.since', { time: format.dateTime(b.opened_at) }),
                          b.latched && t('controls.breakers.latched'),
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </span>
                    )}
                  </span>
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATE_TONE[b.state] ?? ''}`}>
                    {translateCode(i18n, 'breakerState', b.state)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-slate-500">
            {t('controls.breakers.resetLocal')}{' '}
            <code>python -m app.cli breaker reset NAME --reason &quot;...&quot;</code>
          </p>
          <h3 className="mt-3 text-sm font-semibold">{t('controls.breakers.history')}</h3>
          {events.length === 0 ? (
            <p className="text-sm text-slate-500">{t('controls.breakers.noEvents')}</p>
          ) : (
            <ul className="mt-1 divide-y divide-slate-100 text-sm dark:divide-slate-800">
              {events.map((e, i) => (
                <li key={`${e.ts_utc}-${e.name}-${String(i)}`} className="py-1">
                  <span className="font-medium">
                    {name(e.name, e.scope_key)} · {translateCode(i18n, 'breakerAction', e.action)}
                  </span>{' '}
                  <span className="text-xs text-slate-500">
                    {format.dateTime(e.ts_utc)} · {e.actor}
                    {e.reason && ` · ${e.reason}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {breakers.hasNextPage && (
            <button
              type="button"
              disabled={breakers.isFetchingNextPage}
              onClick={() => void breakers.fetchNextPage()}
              className="mt-2 text-sm underline"
            >
              {t('trades.closed.more')}
            </button>
          )}
        </>
      )}
    </Card>
  );
}

function CommandsCard({ engineId }: { engineId: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const [status, setStatus] = useState('');
  const commands = useInfiniteQuery({
    queryKey: commandKeys.list(engineId, status),
    queryFn: ({ pageParam, signal }) => {
      const query = new URLSearchParams({ limit: String(PAGE) });
      if (status) query.set('status', status);
      if (pageParam) query.set('cursor', pageParam);
      return apiGet(
        `/engines/${encodeURIComponent(engineId)}/commands?${query.toString()}`,
        CommandsPageSchema,
        {
          signal,
        },
      );
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = commands.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <Card
      title={t('controls.commands.title')}
      action={
        <label className="flex items-center gap-1.5 text-sm">
          {t('controls.commands.status')}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
            }}
            className={SELECT}
          >
            <option value="">{t('decisions.filter.all')}</option>
            {COMMAND_STATUSES.map((s) => (
              <option key={s} value={s}>
                {translateCode(i18n, 'commandStatus', s)}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {commands.data === undefined ? (
        <Loading error={commands.isError} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">{t('controls.commands.none')}</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
          {rows.map((c) => {
            const params = Object.entries(c.params)
              .map(([k, v]) => `${k}: ${String(v)}`)
              .join(', ');
            const reason = c.result.reason;
            return (
              <li key={c.id} className="py-1.5">
                <span className="flex flex-wrap justify-between gap-x-3">
                  <span className="font-medium">{translateCode(i18n, 'commandType', c.type)}</span>
                  <span>{translateCode(i18n, 'commandStatus', c.status)}</span>
                </span>
                <span className="block text-xs text-slate-500">
                  {format.dateTime(c.created_at)} · {c.created_by}
                  {params && ` · ${params}`}
                </span>
                {(reason || c.result.detail) && (
                  <span className="block text-xs text-slate-600 dark:text-slate-400">
                    {reason && translateCode(i18n, 'commandReason', reason)}
                    {reason && c.result.detail && ' · '}
                    {c.result.detail}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {commands.hasNextPage && (
        <button
          type="button"
          disabled={commands.isFetchingNextPage}
          onClick={() => void commands.fetchNextPage()}
          className="mt-2 text-sm underline"
        >
          {t('trades.closed.more')}
        </button>
      )}
    </Card>
  );
}

/**
 * PLAN §A15 risk & controls (TAA-911): limits against current values, the limits in use and where they come
 * from (TAA-924), breakers, kill switch, command history.
 */
export function RiskPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const auth = useAuthState();
  // ADMIN is a support role without trading controls (PLAN §A30); the API refuses it too
  const canControl = auth.data?.status === 'signed_in' && auth.data.session.user.role !== 'ADMIN';
  useLiveEvents('status', (event) => {
    const refetch = (key: readonly unknown[]) => {
      void queryClient.invalidateQueries({ queryKey: key });
    };
    if (event.type === 'kill_switch') {
      refetch(riskKeys.killSwitch(id));
      refetch(engineStatusKey(id));
    } else if (event.type.startsWith('breaker')) {
      refetch(riskKeys.breakers(id));
    } else if (event.type === 'command') {
      refetch(commandKeys.all(id));
    } else if (event.type === 'run') {
      refetch(riskKeys.config(id));
    }
  });
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.risk')}</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <KillSwitchCard engineId={id} canControl={canControl} />
        <LimitsCard engineId={id} />
        <RiskLimitsCard />
        <BreakersCard engineId={id} />
        <CommandsCard engineId={id} />
      </div>
    </section>
  );
}
