import { useQuery, useQueryClient } from '@tanstack/react-query';
import { type ReactNode, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { apiGet } from '@/api/client';
import { StepUpDialog } from '@/components/StepUpDialog';
import { type Command, postCommand } from '@/engine/commands';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { translateDynamic } from '@/i18n/dynamic';
import { useFormat } from '@/i18n/useFormat';
import { useLiveEvents } from '@/live/context';
import { Card } from '@/pages/dashboard/cards';

import { type Strategies, StrategiesSchema, type Strategy, strategyKeys, WINDOWS } from './schemas';

const DEFAULT_DAYS = 30;
const OPEN_COMMAND = new Set(['QUEUED', 'DELIVERED']);
const SELECT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';
const STATE_TONE: Record<Strategy['state'], string> = {
  ENABLED: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  DISABLED_REMOTE: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  DISABLED_CONFIG: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  UNKNOWN: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
};

function windowOf(raw: string | null): number {
  const days = Number(raw);
  return (WINDOWS as readonly number[]).includes(days) ? days : DEFAULT_DAYS;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5 text-sm">
      <dt className="text-slate-600 dark:text-slate-400">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

/** A parameter value as text: choices and yes/no through their translations, other values as they are. */
function ParamValue({ name, value }: { name: string; value: unknown }) {
  const { i18n } = useTranslation();
  if (value === null || value === undefined) return <>—</>;
  const key =
    typeof value === 'boolean'
      ? `strategies.paramValue.bool.${String(value)}`
      : typeof value === 'string'
        ? `strategies.paramValue.${name}.${value}`
        : null;
  if (key !== null && i18n.exists(key)) return <>{translateDynamic(i18n, key)}</>;
  return <>{typeof value === 'string' ? value : JSON.stringify(value)}</>;
}

/** The parameter's name and one-line explanation, with its config.yaml key underneath. */
function ParamName({ name }: { name: string }) {
  const { i18n } = useTranslation();
  const label = `strategies.param.${name}.label`;
  if (!i18n.exists(label)) return <code className="text-xs">{name}</code>;
  return (
    <>
      <span>{translateDynamic(i18n, label)}</span>
      <span className="block text-xs text-slate-500">
        {translateDynamic(i18n, `strategies.param.${name}.hint`)}
      </span>
      <code className="block text-xs text-slate-400 dark:text-slate-500">{name}</code>
    </>
  );
}

/** Effective parameters (read-only); values set in config.yaml are marked. */
function Parameters({ strategy }: { strategy: Strategy }) {
  const { t } = useTranslation();
  const entries = Object.entries(strategy.params).sort(([a], [b]) => a.localeCompare(b));
  const overrides = new Set(strategy.overrides);
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-sm font-medium">
        {t('strategies.params.title', { n: entries.length })}
      </summary>
      {!strategy.known && (
        <p className="mt-1 text-xs text-slate-500">{t('strategies.params.configuredOnly')}</p>
      )}
      {entries.length === 0 ? (
        <p className="mt-1 text-sm text-slate-500">{t('strategies.params.none')}</p>
      ) : (
        <table
          aria-label={t('strategies.params.table', { name: strategy.name })}
          className="mt-1 w-full text-sm"
        >
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key} className="border-t border-slate-100 dark:border-slate-800">
                <th scope="row" className="py-1 pr-3 text-left font-normal">
                  <ParamName name={key} />
                  {overrides.has(key) && (
                    <span className="ml-1.5 rounded bg-sky-100 px-1 text-xs text-sky-900 dark:bg-sky-900/40 dark:text-sky-200">
                      {t('strategies.params.override')}
                    </span>
                  )}
                </th>
                <td className="py-1 text-right align-top tabular-nums">
                  <ParamValue name={key} value={value} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}

function LastCommand({ command }: { command: Command }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const failed = ['REJECTED', 'FAILED', 'EXPIRED'].includes(command.status);
  return (
    <p className={`mt-2 text-xs ${failed ? 'text-red-700 dark:text-red-400' : 'text-slate-500'}`}>
      {t('strategies.command', {
        status: translateCode(i18n, 'commandStatus', command.status),
        user: command.created_by,
        time: format.dateTime(command.created_at),
      })}
      {command.result.detail && ` · ${command.result.detail}`}
    </p>
  );
}

function StrategyCard({ strategy, onDisable }: { strategy: Strategy; onDisable: (s: Strategy) => void }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const perf = strategy.performance;
  const pending = strategy.last_command !== null && OPEN_COMMAND.has(strategy.last_command.status);
  const canDisable = (strategy.state === 'ENABLED' || strategy.state === 'UNKNOWN') && !pending;
  const description = i18n.exists(`codes:strategy.${strategy.name}`)
    ? translateCode(i18n, 'strategy', strategy.name)
    : (strategy.description ?? '');
  const d = strategy.decisions;
  return (
    <Card
      title={translateCode(i18n, 'strategyName', strategy.name)}
      action={
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATE_TONE[strategy.state]}`}>
          {translateCode(i18n, 'strategyState', strategy.state)}
        </span>
      }
    >
      {description && <p className="text-sm text-slate-600 dark:text-slate-400">{description}</p>}
      <p className="mt-1 text-xs text-slate-500">
        {[
          strategy.name,
          strategy.version && t('strategies.version', { version: strategy.version }),
          strategy.warmup_bars !== null && t('strategies.warmup', { bars: strategy.warmup_bars }),
          strategy.timeframes.length > 0 &&
            t('strategies.extraTimeframes', { tfs: strategy.timeframes.join(', ') }),
          strategy.demo_only && t('strategies.demoOnly'),
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
      <div className="mt-3 grid gap-x-6 sm:grid-cols-2">
        <dl aria-label={t('strategies.decisions.title', { name: strategy.name })}>
          <Row label={t('strategies.decisions.accept')}>{format.number(d.ACCEPT)}</Row>
          <Row label={t('strategies.decisions.reject')}>{format.number(d.REJECT)}</Row>
          <Row label={t('strategies.decisions.hold')}>{format.number(d.HOLD)}</Row>
          {strategy.top_reject_reasons.length > 0 && (
            <div className="py-0.5 text-xs text-slate-500">
              <dt className="inline">{t('strategies.decisions.topReasons')} </dt>
              <dd className="inline">
                {strategy.top_reject_reasons
                  .map((r) => `${translateCode(i18n, 'reason', r.code)} (${format.number(r.count)})`)
                  .join(' · ')}
              </dd>
            </div>
          )}
        </dl>
        <dl aria-label={t('strategies.perf.title', { name: strategy.name })}>
          <Row label={t('strategies.perf.trades')}>
            {t('strategies.perf.tradesValue', {
              trades: format.number(perf.trades),
              wins: format.number(perf.wins),
              losses: format.number(perf.losses),
            })}
          </Row>
          <Row label={t('strategies.perf.winRate')}>
            {perf.win_rate === null ? '—' : format.percent(perf.win_rate * 100, { maximumFractionDigits: 1 })}
          </Row>
          <Row label={t('strategies.perf.net')}>{format.number(perf.net, { signDisplay: 'exceptZero' })}</Row>
          <Row label={t('strategies.perf.profitFactor')}>{format.number(perf.profit_factor)}</Row>
          <Row label={t('strategies.perf.avgR')}>
            {perf.avg_r === null
              ? '—'
              : t('strategies.perf.avgRValue', {
                  r: format.number(perf.avg_r, { signDisplay: 'exceptZero' }),
                  n: format.number(perf.r_trades),
                })}
          </Row>
          <Row label={t('strategies.perf.open')}>{format.number(perf.open)}</Row>
          <Row label={t('strategies.perf.lastExit')}>{format.dateTime(perf.last_exit_at)}</Row>
        </dl>
      </div>
      <Parameters strategy={strategy} />
      {strategy.last_command && <LastCommand command={strategy.last_command} />}
      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        {canDisable && (
          <button
            type="button"
            onClick={() => {
              onDisable(strategy);
            }}
            className="rounded border border-red-700 px-3 py-1 font-medium text-red-700 hover:bg-red-50 dark:border-red-400 dark:text-red-400 dark:hover:bg-red-950"
          >
            {t('strategies.disable.button')}
          </button>
        )}
        {pending && <span className="text-slate-500">{t('strategies.disable.pending')}</span>}
        {strategy.state === 'DISABLED_REMOTE' && (
          <span className="text-xs text-slate-500">
            {t('strategies.reEnable')} <code>python -m app.cli strategy enable {strategy.name}</code>
          </span>
        )}
        {strategy.state === 'DISABLED_CONFIG' && (
          <span className="text-xs text-slate-500">{t('strategies.configOff')}</span>
        )}
      </div>
    </Card>
  );
}

function DisableDialog({
  engineId,
  strategy,
  onClose,
}: {
  engineId: string;
  strategy: Strategy;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const reasonId = useId();
  const [reason, setReason] = useState('');
  const confirm = async () => {
    const trimmed = reason.trim();
    await postCommand(engineId, {
      type: 'STRATEGY_DISABLE',
      strategy: strategy.name,
      ...(trimmed ? { reason: trimmed } : {}),
    });
    await queryClient.invalidateQueries({ queryKey: strategyKeys.all(engineId) });
  };
  return (
    <StepUpDialog
      title={t('strategies.disable.title', { name: strategy.name })}
      confirmLabel={t('strategies.disable.confirm')}
      danger
      onConfirm={confirm}
      onClose={onClose}
    >
      <p>{t('strategies.disable.body')}</p>
      <p className="text-xs text-slate-500">
        {t('strategies.reEnable')} <code>python -m app.cli strategy enable {strategy.name}</code>
      </p>
      <div>
        <label htmlFor={reasonId} className="block font-medium">
          {t('strategies.disable.reason')}
        </label>
        <textarea
          id={reasonId}
          value={reason}
          maxLength={200}
          rows={2}
          onChange={(e) => {
            setReason(e.target.value);
          }}
          className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-950"
        />
      </div>
    </StepUpDialog>
  );
}

/**
 * Whether a heartbeat's remote-disable list changes what the page shows: only strategies that run by
 * config.yaml count (the engine may also list ones config.yaml switched off since).
 */
function remoteChanged(data: Strategies, listed: readonly string[]): boolean {
  if (!data.remote_known) return true; // the first heartbeat that reports the list
  const running = data.strategies.filter((s) => s.configured_enabled);
  const off = new Set(listed);
  return running.some((s) => (s.state === 'DISABLED_REMOTE') !== off.has(s.name));
}

/** PLAN §A15 strategies (TAA-909): state, read-only parameters, performance per strategy, disable action. */
export function StrategiesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const [params, setParams] = useSearchParams();
  const days = windowOf(params.get('days'));
  const [disabling, setDisabling] = useState<Strategy | null>(null);
  const query = useQuery({
    queryKey: strategyKeys.list(id, days),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(id)}/strategies?days=${String(days)}`, StrategiesSchema, {
        signal,
      }),
  });
  const refetch = () => {
    void queryClient.invalidateQueries({ queryKey: strategyKeys.all(id) });
  };
  useLiveEvents('status', (event) => {
    if (event.type === 'command' || event.type === 'run') {
      refetch();
      return;
    }
    if (event.type !== 'heartbeat' || !query.data) return;
    const listed = (event.item as { disabled_strategies?: unknown } | null)?.disabled_strategies;
    if (Array.isArray(listed) && remoteChanged(query.data, listed.map(String))) refetch();
  });
  useLiveEvents('positions', refetch);
  useLiveEvents('decisions', refetch);

  const data = query.data;
  return (
    <section>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t('nav.strategies')}</h1>
        <label className="flex items-center gap-1.5 text-sm">
          {t('strategies.window')}
          <select
            value={days}
            onChange={(e) => {
              const next = new URLSearchParams(params);
              next.set('days', e.target.value);
              setParams(next, { replace: true });
            }}
            className={SELECT}
          >
            {WINDOWS.map((w) => (
              <option key={w} value={w}>
                {t('strategies.days', { n: w })}
              </option>
            ))}
          </select>
        </label>
      </div>
      {data === undefined ? (
        <p className="text-sm text-slate-500">
          {query.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : data.strategies.length === 0 ? (
        <p className="text-sm text-slate-500">{t('strategies.none')}</p>
      ) : (
        <>
          <div className="mb-4 space-y-1 text-sm text-slate-600 dark:text-slate-400">
            <p>
              {t('strategies.shared', {
                higher: data.timeframes.higher ?? '—',
                entry: data.timeframes.entry ?? '—',
                cooldown: data.shared.cooldown_bars ?? '—',
                expiry: data.shared.signal_expiry_bars ?? '—',
              })}
            </p>
            {!data.remote_known && <p>{t('strategies.remoteUnknown')}</p>}
            <p className="text-xs">{t('strategies.note')}</p>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            {data.strategies.map((s) => (
              <StrategyCard key={s.name} strategy={s} onDisable={setDisabling} />
            ))}
          </div>
        </>
      )}
      {disabling && (
        <DisableDialog
          engineId={id}
          strategy={disabling}
          onClose={() => {
            setDisabling(null);
          }}
        />
      )}
    </section>
  );
}
