import { useQuery, useQueryClient } from '@tanstack/react-query';
import { type SubmitEvent, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError, apiGet, apiPost } from '@/api/client';
import { useNow } from '@/app/useNow';
import { translateDynamic } from '@/i18n/dynamic';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { StrategiesSchema, strategyKeys } from '@/pages/strategies/schemas';

import { buildRequest, defaultPeriod, type RunForm, symbolsWithHistory } from './backtestModel';
import { backtestKeys, HistorySchema, PresetsSchema, RunSchema } from './schemas';

const INPUT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950';
const KNOWN_ERRORS = new Set(['invalid_backtest', 'backtest_limit', 'plan_limit']);

/** PLAN §A15 "new run from presets": a preset plus bounded parameters (`BacktestRequest`), never a config. */
export function NewRunForm({
  engineId,
  onCreated,
  onCancel,
}: {
  engineId: string;
  onCreated: (runId: string) => void;
  onCancel: () => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const queryClient = useQueryClient();
  const now = useNow(60_000);
  const ids = { start: useId(), end: useId(), risk: useId(), seed: useId(), preset: useId() };
  const enc = encodeURIComponent(engineId);
  const presets = useQuery({
    queryKey: backtestKeys.presets,
    queryFn: ({ signal }) => apiGet('/backtests/presets', PresetsSchema, { signal }),
    staleTime: Infinity,
  });
  const history = useQuery({
    queryKey: backtestKeys.history(engineId),
    queryFn: ({ signal }) => apiGet(`/engines/${enc}/backtests/history`, HistorySchema, { signal }),
  });
  const strategies = useQuery({
    queryKey: strategyKeys.list(engineId, 30),
    queryFn: ({ signal }) => apiGet(`/engines/${enc}/strategies?days=30`, StrategiesSchema, { signal }),
  });
  const available = history.data ? symbolsWithHistory(history.data) : [];
  const [form, setForm] = useState<RunForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!presets.data || !history.data) {
    return (
      <Card title={t('backtests.form.title')}>
        <p className="text-sm text-slate-500">
          {presets.isError || history.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      </Card>
    );
  }
  const limits = { maxSymbols: presets.data.max_symbols, maxDays: presets.data.max_days };
  const current: RunForm = form ?? {
    preset: presets.data.presets[0] ?? 'standard',
    symbols: available.slice(0, 1).map((s) => s.symbol),
    ...defaultPeriod(available, now),
    strategies: [],
    riskPercent: '',
    seed: '',
  };
  const update = (patch: Partial<RunForm>) => {
    setForm({ ...current, ...patch });
    setError(null);
  };
  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    const built = buildRequest(current, now, limits);
    if ('problem' in built) {
      setError(
        t(`backtests.form.problem.${built.problem}`, { max: limits.maxSymbols, days: limits.maxDays }),
      );
      return;
    }
    setBusy(true);
    try {
      const run = await apiPost(`/engines/${enc}/backtests`, built.body, RunSchema);
      await queryClient.invalidateQueries({ queryKey: backtestKeys.list(engineId) });
      onCreated(run.run_id);
    } catch (err) {
      if (err instanceof ApiError && KNOWN_ERRORS.has(err.code)) {
        setError(translateDynamic(i18n, `backtests.form.error.${err.code}`, { message: err.message }));
      } else if (err instanceof ApiError) {
        setError(t('backtests.form.error.other', { code: err.code }));
      } else {
        setError(t('stepUp.network'));
      }
    } finally {
      setBusy(false);
    }
  };

  const configured = strategies.data?.strategies.map((s) => s.name) ?? [];
  return (
    <Card title={t('backtests.form.title')}>
      {available.length === 0 ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t('backtests.form.noHistory')} <code>python -m app.cli sync upload-history --send</code>
        </p>
      ) : (
        <form onSubmit={(e) => void submit(e)} className="space-y-4 text-sm">
          <div>
            <label htmlFor={ids.preset} className="block font-medium">
              {t('backtests.form.preset')}
            </label>
            <select
              id={ids.preset}
              value={current.preset}
              onChange={(e) => {
                update({ preset: e.target.value });
              }}
              className={`${INPUT} mt-1`}
            >
              {presets.data.presets.map((p) => (
                <option key={p} value={p}>
                  {i18n.exists(`backtests.preset.${p}.name`)
                    ? translateDynamic(i18n, `backtests.preset.${p}.name`)
                    : p}
                </option>
              ))}
            </select>
            {i18n.exists(`backtests.preset.${current.preset}.desc`) && (
              <p className="mt-1 text-xs text-slate-500">
                {translateDynamic(i18n, `backtests.preset.${current.preset}.desc`)}
              </p>
            )}
          </div>
          <fieldset>
            <legend className="font-medium">{t('backtests.form.symbols')}</legend>
            <p className="text-xs text-slate-500">
              {t('backtests.form.symbolsHint', { max: limits.maxSymbols })}
            </p>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
              {available.map((s) => (
                <label key={`${s.server}/${s.symbol}`} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={current.symbols.includes(s.symbol)}
                    onChange={() => {
                      update({ symbols: toggle(current.symbols, s.symbol) });
                    }}
                  />
                  {s.symbol}
                  <span className="text-xs text-slate-500">
                    {format.date(s.first)} – {format.date(s.last)}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label htmlFor={ids.start} className="block font-medium">
                {t('backtests.form.start')}
              </label>
              <input
                id={ids.start}
                type="date"
                value={current.start}
                onChange={(e) => {
                  update({ start: e.target.value });
                }}
                className={`${INPUT} mt-1`}
              />
            </div>
            <div>
              <label htmlFor={ids.end} className="block font-medium">
                {t('backtests.form.end')}
              </label>
              <input
                id={ids.end}
                type="date"
                value={current.end}
                onChange={(e) => {
                  update({ end: e.target.value });
                }}
                className={`${INPUT} mt-1`}
              />
            </div>
            <p className="text-xs text-slate-500">{t('backtests.form.utc', { days: limits.maxDays })}</p>
          </div>
          {configured.length > 0 && (
            <fieldset>
              <legend className="font-medium">{t('backtests.form.strategies')}</legend>
              <p className="text-xs text-slate-500">{t('backtests.form.strategiesHint')}</p>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                {configured.map((name) => (
                  <label key={name} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={current.strategies.includes(name)}
                      onChange={() => {
                        update({ strategies: toggle(current.strategies, name) });
                      }}
                    />
                    <code className="text-xs">{name}</code>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <div className="flex flex-wrap gap-3">
            <div>
              <label htmlFor={ids.risk} className="block font-medium">
                {t('backtests.form.risk')}
              </label>
              <input
                id={ids.risk}
                inputMode="decimal"
                value={current.riskPercent}
                placeholder={t('backtests.form.fromPreset')}
                onChange={(e) => {
                  update({ riskPercent: e.target.value });
                }}
                className={`${INPUT} mt-1 w-36`}
              />
            </div>
            <div>
              <label htmlFor={ids.seed} className="block font-medium">
                {t('backtests.form.seed')}
              </label>
              <input
                id={ids.seed}
                inputMode="numeric"
                value={current.seed}
                placeholder={t('backtests.form.fromPreset')}
                onChange={(e) => {
                  update({ seed: e.target.value });
                }}
                className={`${INPUT} mt-1 w-36`}
              />
            </div>
          </div>
          {error && (
            <p role="alert" className="text-red-700 dark:text-red-400">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-slate-800 px-3 py-1.5 font-medium text-white hover:bg-slate-900 disabled:opacity-60 dark:bg-slate-700"
            >
              {busy ? t('backtests.form.submitting') : t('backtests.form.submit')}
            </button>
            <button type="button" onClick={onCancel} className="rounded px-3 py-1.5 underline">
              {t('stepUp.cancel')}
            </button>
          </div>
        </form>
      )}
    </Card>
  );
}
