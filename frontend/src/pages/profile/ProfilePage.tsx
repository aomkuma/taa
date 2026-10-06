import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { z } from 'zod';

import { ApiError, apiPost } from '@/api/client';
import { useEngine, useEngineStatus } from '@/engine/context';
import { engineKey } from '@/engine/schemas';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { EngineLimits } from '@/pages/risk/EngineLimits';
import { profilePending } from '@/pages/risk/riskLimitsModel';
import { usePreferences, useSaveSections } from '@/pages/watchlists/hooks';
import {
  CONFLICT_POLICIES,
  type EntryPlan,
  HOLDING_STYLES,
  SPLIT_MODES,
  STOP_PLACEMENTS,
  type TradingProfile,
  WEIGHT_SCHEMES,
} from '@/pages/watchlists/schemas';

import {
  ANCHORS,
  fillTakeProfits,
  OVERRIDE_BOUNDS,
  overrideValid,
  planProblems,
  PROFILE_FIELDS,
  type ProfileField,
  resolve,
  setMode,
  setOverride,
  warnings,
} from './profileModel';

const INPUT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950';
const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const PRIMARY =
  'rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50';
const BADGE =
  'rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-200';
const TH = 'px-2 py-1 text-left font-medium';
const PERCENT: ReadonlySet<ProfileField> = new Set([
  'risk_per_signal_percent',
  'portfolio_heat_percent',
  'max_daily_loss_percent',
  'min_win_probability',
]);

const PreviewSchema = z.looseObject({
  available: z.boolean(),
  reason: z.string().optional(),
  example: z
    .object({
      symbol: z.string(),
      side: z.string(),
      entry: z.number(),
      stop: z.number(),
      take_profit: z.number(),
    })
    .optional(),
  currency: z.string().optional(),
  equity: z.number().nullable().optional(),
  budget: z.number().optional(),
  lot: z.number().optional(),
  risk_money: z.number().optional(),
  taps: z.number().int().optional(),
  plan: z
    .array(
      z.object({
        entry: z.string(),
        order_type: z.string(),
        take_profit: z.string().nullable(),
        volume: z.string(),
        taps: z.number().int(),
        risk_money: z.string(),
      }),
    )
    .optional(),
});

/** One resolved field: its value (slider or custom) and, when custom, an editor and a reset. */
function FieldRow({
  field,
  profile,
  value,
  custom,
  change,
}: {
  field: ProfileField;
  profile: TradingProfile;
  value: number | boolean | string;
  custom: boolean;
  change: (next: TradingProfile) => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const id = useId();
  const override = profile.overrides[field];
  const label = t(`profile.field.${field}`);
  const shown =
    typeof value === 'boolean'
      ? value
        ? t('profile.yes')
        : t('profile.no')
      : typeof value === 'string'
        ? t(`theories.rules.policy.${value as 'BLOCK'}`)
        : PERCENT.has(field)
          ? format.percent(value)
          : format.number(value, { maximumFractionDigits: 2 });
  let editor = null;
  if (custom) {
    if (field === 'conflict_policy') {
      editor = (
        <select
          id={id}
          aria-label={label}
          className={INPUT}
          value={String(override)}
          onChange={(e) => {
            change(setOverride(profile, field, e.target.value as (typeof CONFLICT_POLICIES)[number]));
          }}
        >
          {CONFLICT_POLICIES.map((p) => (
            <option key={p} value={p}>
              {t(`theories.rules.policy.${p}`)}
            </option>
          ))}
        </select>
      );
    } else if (field === 'require_htf_alignment') {
      editor = (
        <input
          id={id}
          type="checkbox"
          aria-label={label}
          checked={override === true}
          onChange={(e) => {
            change(setOverride(profile, field, e.target.checked));
          }}
        />
      );
    } else {
      const bound = OVERRIDE_BOUNDS[field];
      editor = (
        <input
          id={id}
          type="number"
          aria-label={label}
          aria-invalid={!overrideValid(field, override)}
          className={`${INPUT} w-24 ${overrideValid(field, override) ? '' : 'border-red-500'}`}
          min={bound?.min}
          max={bound?.max}
          step="any"
          value={typeof override === 'number' && Number.isFinite(override) ? override : ''}
          onChange={(e) => {
            change(setOverride(profile, field, e.target.value === '' ? Number.NaN : Number(e.target.value)));
          }}
        />
      );
    }
  }
  return (
    <tr>
      <td className="px-2 py-1.5">{label}</td>
      <td className="px-2 py-1.5 tabular-nums">
        {custom ? editor : <span className="font-medium">{shown}</span>}
      </td>
      <td className="px-2 py-1.5 text-right">
        {custom ? (
          <>
            <span className={BADGE}>{t('profile.custom')}</span>{' '}
            <button
              type="button"
              className="text-sm underline"
              aria-label={t('profile.resetField', { field: label })}
              onClick={() => {
                change(setOverride(profile, field, null));
              }}
            >
              {t('profile.reset')}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="text-sm underline"
            aria-label={t('profile.customizeField', { field: label })}
            onClick={() => {
              change(setOverride(profile, field, value as never));
            }}
          >
            {t('profile.customize')}
          </button>
        )}
      </td>
    </tr>
  );
}

function StyleCard({ profile, change }: { profile: TradingProfile; change: (next: TradingProfile) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const { values, custom } = resolve(profile);
  const anchor = ANCHORS.reduce((a, b) =>
    Math.abs(b - profile.style) < Math.abs(a - profile.style) ? b : a,
  );
  return (
    <Card title={t('profile.style.title')}>
      <label htmlFor={id} className="block text-sm">
        {t('profile.style.label')}{' '}
        <strong>
          {profile.style} · {t(`profile.style.anchor.${String(anchor) as '50'}`)}
        </strong>
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={5}
        className="mt-2 w-full"
        value={profile.style}
        onChange={(e) => {
          change({ ...profile, style: Number(e.target.value) });
        }}
      />
      <div className="flex justify-between text-xs text-slate-500" aria-hidden="true">
        <span>{t('profile.style.anchor.0')}</span>
        <span>{t('profile.style.anchor.50')}</span>
        <span>{t('profile.style.anchor.100')}</span>
      </div>
      <table className="mt-3 w-full text-sm">
        <thead className="sr-only">
          <tr>
            <th className={TH}>{t('profile.setting')}</th>
            <th className={TH}>{t('profile.value')}</th>
            <th className={TH}>{t('profile.source')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
          {PROFILE_FIELDS.map((field) => (
            <FieldRow
              key={field}
              field={field}
              profile={profile}
              value={values[field]}
              custom={custom.has(field)}
              change={change}
            />
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">{t('profile.style.note')}</p>
    </Card>
  );
}

function HabitsCard({
  profile,
  change,
}: {
  profile: TradingProfile;
  change: (next: TradingProfile) => void;
}) {
  const { t } = useTranslation();
  const holdingId = useId();
  const signalsId = useId();
  const stopId = useId();
  return (
    <Card title={t('profile.habits.title')}>
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={holdingId}>{t('profile.habits.holding')}</label>
          <select
            id={holdingId}
            className={INPUT}
            value={profile.holding_style}
            onChange={(e) => {
              change({ ...profile, holding_style: e.target.value as TradingProfile['holding_style'] });
            }}
          >
            {HOLDING_STYLES.map((h) => (
              <option key={h} value={h}>
                {t(`profile.habits.holdingName.${h}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={signalsId}>{t('profile.habits.signals')}</label>
          <input
            id={signalsId}
            type="number"
            min={1}
            max={100}
            step={1}
            className={`${INPUT} w-24`}
            value={Number.isFinite(profile.max_signals_per_day) ? profile.max_signals_per_day : ''}
            onChange={(e) => {
              change({
                ...profile,
                max_signals_per_day: e.target.value === '' ? Number.NaN : Number(e.target.value),
              });
            }}
          />
        </div>
        {(['avoid_news', 'hold_over_weekend', 'min_lot_fallback'] as const).map((key) => (
          <label key={key} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={profile[key]}
              onChange={(e) => {
                change({ ...profile, [key]: e.target.checked });
              }}
            />
            {t(`profile.habits.${key}`)}
          </label>
        ))}
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={stopId}>{t('profile.habits.stop')}</label>
          <select
            id={stopId}
            className={INPUT}
            value={profile.stop_placement}
            onChange={(e) => {
              change({ ...profile, stop_placement: e.target.value as TradingProfile['stop_placement'] });
            }}
          >
            {STOP_PLACEMENTS.map((s) => (
              <option key={s} value={s}>
                {t(`profile.habits.stopName.${s}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </Card>
  );
}

function Preview({ profile, plan, valid }: { profile: TradingProfile; plan: EntryPlan; valid: boolean }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const body = { entry_plan: plan, trading_profile: profile };
  const preview = useQuery({
    queryKey: [...engineKey(engineId ?? ''), 'entry-plan-preview', JSON.stringify(body)],
    queryFn: () =>
      apiPost(`/engines/${encodeURIComponent(engineId ?? '')}/entry-plan/preview`, body, PreviewSchema),
    enabled: engineId !== null && valid,
    placeholderData: keepPreviousData,
    retry: false,
  });
  const data = preview.data;
  if (!valid) return <p className="text-sm text-slate-500">{t('profile.plan.fixFirst')}</p>;
  if (data === undefined) {
    return (
      <p className="text-sm text-slate-500">
        {preview.isError &&
        !(preview.error instanceof ApiError && preview.error.code === 'advisory_not_found')
          ? t('dashboard.loadFailed')
          : preview.isError
            ? t('profile.preview.reason.no_example')
            : t('dashboard.loading')}
      </p>
    );
  }
  if (!data.available) {
    const reason = data.reason ?? 'sizing_failed';
    return (
      <p className="text-sm text-amber-800 dark:text-amber-300">
        {i18n.exists(`profile.preview.reason.${reason}`)
          ? t(`profile.preview.reason.${reason as 'no_account'}`)
          : translateCode(i18n, 'reason', reason)}
        {reason === 'no_account' && (
          <>
            {' '}
            <Link to="/account" className="underline">
              {t('profile.preview.setAccount')}
            </Link>
          </>
        )}
      </p>
    );
  }
  const currency = data.currency ?? 'USD';
  const ex = data.example;
  const price = (v: string | number | null) =>
    format.number(v === null ? null : Number(v), { maximumFractionDigits: 6 });
  return (
    <div className="space-y-2 text-sm">
      {ex && (
        <p>
          {t('profile.preview.example', {
            symbol: ex.symbol,
            entry: price(ex.entry),
            stop: price(ex.stop),
            target: price(ex.take_profit),
          })}
        </p>
      )}
      <table className="w-full">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className={TH}>#</th>
            <th className={TH}>{t('profile.preview.order')}</th>
            <th className={TH}>{t('profile.preview.price')}</th>
            <th className={TH}>{t('profile.preview.lot')}</th>
            <th className={TH}>{t('profile.preview.taps')}</th>
            <th className={TH}>{t('profile.preview.target')}</th>
            <th className={TH}>{t('profile.preview.risk')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 tabular-nums dark:divide-slate-800">
          {(data.plan ?? []).map((part, i) => (
            <tr key={`${part.entry}-${String(i)}`}>
              <td className="px-2 py-1">{i + 1}</td>
              <td className="px-2 py-1">{t(`profile.preview.type.${part.order_type as 'MARKET'}`)}</td>
              <td className="px-2 py-1">{price(part.entry)}</td>
              <td className="px-2 py-1">{format.number(Number(part.volume))}</td>
              <td className="px-2 py-1">{part.taps}</td>
              <td className="px-2 py-1">{part.take_profit === null ? '—' : price(part.take_profit)}</td>
              <td className="px-2 py-1">{format.money(Number(part.risk_money), currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="font-medium">
        {t('profile.preview.total', {
          lot: format.number(data.lot),
          taps: data.taps,
          risk: format.money(data.risk_money, currency),
          budget: format.money(data.budget, currency),
          pct:
            data.equity != null && data.risk_money != null
              ? format.percent((100 * data.risk_money) / data.equity, { maximumFractionDigits: 2 })
              : '—',
        })}
      </p>
      <p className="text-xs text-slate-500">{t('profile.preview.note')}</p>
    </div>
  );
}

function PlanCard({
  plan,
  profile,
  change,
}: {
  plan: EntryPlan;
  profile: TradingProfile;
  change: (next: EntryPlan) => void;
}) {
  const { t } = useTranslation();
  const ids = { parts: useId(), unit: useId(), spacing: useId(), mode: useId() };
  const problems = planProblems(plan);
  return (
    <Card title={t('profile.plan.title')}>
      <div className="space-y-3 text-sm">
        <fieldset className="space-y-1">
          <legend className="mb-1 font-medium">{t('profile.plan.mode')}</legend>
          {SPLIT_MODES.map((mode) => (
            <label key={mode} className="flex items-start gap-2">
              <input
                type="radio"
                name={ids.mode}
                className="mt-1"
                checked={plan.mode === mode}
                onChange={() => {
                  change(setMode(plan, mode));
                }}
              />
              <span>
                {t(`profile.plan.modeName.${mode}`)}
                <span className="block text-xs text-slate-500">{t(`profile.plan.modeAbout.${mode}`)}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {plan.mode !== 'SINGLE' && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor={ids.parts}>{t('profile.plan.parts')}</label>
              <input
                id={ids.parts}
                type="number"
                min={2}
                max={5}
                step={1}
                className={`${INPUT} w-20`}
                value={plan.parts}
                onChange={(e) => {
                  const parts = Number(e.target.value);
                  change({ ...plan, parts, partial_tp_r: fillTakeProfits(plan.partial_tp_r, parts) });
                }}
              />
            </div>
            <fieldset className="flex flex-wrap gap-4">
              <legend className="mb-1 w-full font-medium">{t('profile.plan.weights')}</legend>
              {WEIGHT_SCHEMES.map((w) => (
                <label key={w} className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    name={`${ids.mode}-w`}
                    checked={plan.weights === w}
                    onChange={() => {
                      change({ ...plan, weights: w });
                    }}
                  />
                  {t(`profile.plan.weightName.${w}`)}
                </label>
              ))}
            </fieldset>
          </>
        )}
        {plan.mode === 'SCALE_IN' && (
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor={ids.spacing}>{t('profile.plan.spacing')}</label>
            <input
              id={ids.spacing}
              type="number"
              min={0.1}
              max={3}
              step={0.1}
              className={`${INPUT} w-20`}
              value={Number.isFinite(plan.spacing_atr) ? plan.spacing_atr : ''}
              onChange={(e) => {
                change({ ...plan, spacing_atr: e.target.value === '' ? Number.NaN : Number(e.target.value) });
              }}
            />
          </div>
        )}
        {plan.mode === 'SAME_PRICE' && (
          <fieldset className="flex flex-wrap items-center gap-2">
            <legend className="mb-1 w-full font-medium">{t('profile.plan.takeProfits')}</legend>
            {plan.partial_tp_r.slice(0, plan.parts - 1).map((r, i) => (
              <label key={i} className="flex items-center gap-1">
                {t('profile.plan.tpN', { n: i + 1 })}
                <input
                  type="number"
                  min={0.1}
                  step={0.1}
                  className={`${INPUT} w-20`}
                  value={Number.isFinite(r) ? r : ''}
                  onChange={(e) => {
                    const levels = [...plan.partial_tp_r];
                    levels[i] = e.target.value === '' ? Number.NaN : Number(e.target.value);
                    change({ ...plan, partial_tp_r: levels });
                  }}
                />
                R
              </label>
            ))}
            <span className="text-xs text-slate-500">{t('profile.plan.lastRuns')}</span>
          </fieldset>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={ids.unit}>{t('profile.plan.lotUnit')}</label>
          <input
            id={ids.unit}
            inputMode="decimal"
            className={`${INPUT} w-24`}
            placeholder={t('profile.plan.lotUnitAuto')}
            value={plan.lot_unit === null ? '' : String(plan.lot_unit)}
            onChange={(e) => {
              change({ ...plan, lot_unit: e.target.value === '' ? null : Number(e.target.value) });
            }}
          />
        </div>
        {problems.length > 0 && (
          <ul className="list-disc pl-5 text-sm text-red-700 dark:text-red-400">
            {problems.map((p) => (
              <li key={p}>{t(`profile.plan.problem.${p}`)}</li>
            ))}
          </ul>
        )}
        <section
          aria-label={t('profile.preview.title')}
          className="border-t border-slate-200 pt-3 dark:border-slate-800"
        >
          <h3 className="mb-2 font-medium">{t('profile.preview.title')}</h3>
          <Preview profile={profile} plan={plan} valid={problems.length === 0} />
        </section>
      </div>
    </Card>
  );
}

/** What the engine trades with after the cage (TAA-924); only for an engine that reports it (its owner). */
function EngineLimitsCard({ saved }: { saved: TradingProfile }) {
  const { t } = useTranslation();
  const status = useEngineStatus();
  const limits = status.data?.heartbeat?.account?.risk_limits;
  if (!limits) return null;
  const pending = profilePending(limits, resolve(saved).values);
  return (
    <Card title={t('riskLimits.title')}>
      {pending && (
        <p role="status" className="mb-2 text-sm text-amber-800 dark:text-amber-300">
          {t('riskLimits.pending')}
        </p>
      )}
      <EngineLimits limits={limits} />
    </Card>
  );
}

function ProfileForm({ saved }: { saved: { profile: TradingProfile; plan: EntryPlan } }) {
  const { t } = useTranslation();
  const save = useSaveSections();
  const [draft, setDraft] = useState(saved);
  const [base, setBase] = useState(saved);
  if (JSON.stringify(base) !== JSON.stringify(saved)) {
    setBase(saved);
    setDraft(saved);
  }
  const setProfile = (profile: TradingProfile) => {
    save.reset();
    setDraft((old) => ({ ...old, profile }));
  };
  const setPlan = (plan: EntryPlan) => {
    save.reset();
    setDraft((old) => ({ ...old, plan }));
  };
  const { values } = resolve(draft.profile);
  const found = warnings(values, draft.plan);
  const badFields = PROFILE_FIELDS.filter((f) => !overrideValid(f, draft.profile.overrides[f]));
  const signals = draft.profile.max_signals_per_day;
  const badSignals = !Number.isInteger(signals) || signals < 1 || signals > 100;
  const invalid = badFields.length > 0 || badSignals || planProblems(draft.plan).length > 0;
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  return (
    <div className="flex flex-col gap-4">
      {found.length > 0 && (
        <section
          aria-label={t('profile.warnings.title')}
          className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
        >
          <h2 className="mb-1 font-semibold">{t('profile.warnings.title')}</h2>
          <ul className="list-disc pl-5">
            {found.map((w) => (
              <li key={w}>{t(`profile.warnings.${w}`)}</li>
            ))}
          </ul>
        </section>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <StyleCard profile={draft.profile} change={setProfile} />
        <div className="flex flex-col gap-4">
          <PlanCard plan={draft.plan} profile={draft.profile} change={setPlan} />
          <HabitsCard profile={draft.profile} change={setProfile} />
          <EngineLimitsCard saved={saved.profile} />
        </div>
      </div>
      <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t border-slate-200 bg-white/95 py-2 dark:border-slate-800 dark:bg-slate-950/95">
        <button
          type="button"
          className={PRIMARY}
          disabled={!dirty || invalid || save.isPending}
          onClick={() => {
            save.mutate({ trading_profile: draft.profile, entry_plan: draft.plan });
          }}
        >
          {t('profile.save')}
        </button>
        {dirty && (
          <button
            type="button"
            className={BUTTON}
            onClick={() => {
              save.reset();
              setDraft(saved);
            }}
          >
            {t('profile.undo')}
          </button>
        )}
        {save.isSuccess && !dirty && (
          <span role="status" className="text-sm text-slate-600 dark:text-slate-400">
            {t('profile.saved')}
          </span>
        )}
        {(badFields.length > 0 || badSignals) && (
          <span className="text-sm text-red-700 dark:text-red-400">{t('profile.invalidFields')}</span>
        )}
        {save.error && (
          <span role="alert" className="text-sm text-red-700 dark:text-red-400">
            {save.error instanceof ApiError && save.error.code === 'invalid_preferences'
              ? t('profile.invalid', { detail: save.error.message })
              : t('profile.failed')}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * PLAN §A31 "บุคลิกการเทรด / Trading profile" (TAA-922): the style slider with the resulting numbers, per-field
 * overrides, holding habits and the entry plan with an example lot breakdown sized by the server. The engine
 * owner's profile also sets the engine's own limits inside the engine machine's config.yaml (TAA-710/924).
 */
export function ProfilePage() {
  const { t } = useTranslation();
  const prefs = usePreferences();
  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.profile')}</h1>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">{t('profile.intro')}</p>
      {prefs.data === undefined ? (
        <p className="text-sm text-slate-500">
          {prefs.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : (
        <ProfileForm saved={{ profile: prefs.data.trading_profile, plan: prefs.data.entry_plan }} />
      )}
    </section>
  );
}
