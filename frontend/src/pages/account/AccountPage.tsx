import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type SubmitEvent, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ApiError, apiGet, apiPost, apiPut } from '@/api/client';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { useRanking } from '@/pages/ranking/hooks';
import { useEntitlements } from '@/pages/theories/hooks';

import { formOf, type ManualForm, manualProblems } from './accountModel';
import { PlanName } from './parts';
import {
  AccountProfileSchema,
  accountKeys,
  FEATURES,
  LIMITS,
  type MyEntitlements,
  PlansSchema,
  RISK_CEILING,
} from './schemas';

const INPUT =
  'mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950';
const PRIMARY =
  'rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50';
const BAD = 'text-sm text-red-700 dark:text-red-400';
const CURRENCIES = ['USD', 'THB', 'EUR', 'GBP', 'JPY', 'SGD', 'AUD'];

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-500">{error ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** The engine's MT5 account as the ranking last saw it (the values a linked profile sizes with). */
function LinkedValues({ engineId }: { engineId: string }) {
  const { t } = useTranslation();
  const format = useFormat();
  const ranking = useRanking(engineId);
  const account = ranking.data?.account;
  if (ranking.data === undefined) return <Loading error={ranking.isError} />;
  if (account == null) return <p className="text-sm text-slate-500">{t('account.profile.linkedUnknown')}</p>;
  const currency = account.currency ?? 'USD';
  return (
    <>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Figure label={t('account.profile.equity')} value={format.money(account.equity, currency)} />
        <Figure label={t('account.profile.balance')} value={format.money(account.balance, currency)} />
        <Figure
          label={t('account.profile.leverage')}
          value={account.leverage != null ? `1:${format.number(account.leverage)}` : '—'}
        />
        <Figure label={t('account.profile.riskPercent')} value={format.percent(account.risk_percent)} />
      </dl>
      {ranking.data.computed_at && (
        <p className="mt-1 text-xs text-slate-500">
          {t('account.profile.asOf', { time: format.dateTime(ranking.data.computed_at) })}
        </p>
      )}
    </>
  );
}

function Field({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="text-sm">
      <label htmlFor={id} className="block font-medium">
        {label}
      </label>
      <input
        id={id}
        inputMode="decimal"
        className={INPUT}
        value={value}
        onChange={(e) => {
          onChange(e.target.value.trim());
        }}
      />
      {hint !== undefined && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function ProfileCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { engineId, own } = useEngine();
  const currencyId = useId();
  const profile = useQuery({
    queryKey: accountKeys.profile,
    queryFn: ({ signal }) => apiGet('/me/account-profile', AccountProfileSchema, { signal }),
  });
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPut('/me/account-profile', body, AccountProfileSchema),
    onSuccess: (data) => {
      queryClient.setQueryData(accountKeys.profile, data);
      // the ranking's header and every alert's sizing use the profile
      void queryClient.invalidateQueries({ queryKey: ['engine'] });
    },
  });
  const [draft, setDraft] = useState<{ source: 'LINKED_ENGINE' | 'MANUAL'; form: ManualForm } | null>(null);
  if (profile.data === undefined) {
    return (
      <Card title={t('account.profile.title')}>
        <Loading error={profile.isError} />
      </Card>
    );
  }
  const saved = profile.data;
  const current = draft ?? {
    source: saved.source ?? (own ? 'LINKED_ENGINE' : 'MANUAL'),
    form: formOf(saved),
  };
  const linked = current.source === 'LINKED_ENGINE' && own && engineId !== null;
  const problems = linked ? [] : manualProblems(current.form);
  const set = (patch: Partial<ManualForm>) => {
    save.reset();
    setDraft({ ...current, form: { ...current.form, ...patch } });
  };
  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const f = current.form;
    save.mutate(
      linked
        ? { source: 'LINKED_ENGINE', engine_id: engineId }
        : {
            source: 'MANUAL',
            equity: Number(f.equity),
            balance: f.balance === '' ? null : Number(f.balance),
            currency: f.currency,
            leverage: Number(f.leverage),
            risk_percent: f.risk === '' ? null : Number(f.risk),
          },
      {
        onSuccess: () => {
          setDraft(null);
        },
      },
    );
  };
  return (
    <Card title={t('account.profile.title')}>
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
        {saved.source === null ? t('account.profile.notSet') : t('account.profile.intro')}
      </p>
      <form className="space-y-3" onSubmit={submit}>
        {own && (
          <fieldset className="flex flex-wrap gap-4 text-sm">
            <legend className="sr-only">{t('account.profile.source')}</legend>
            {(['LINKED_ENGINE', 'MANUAL'] as const).map((source) => (
              <label key={source} className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name={`${currencyId}-source`}
                  checked={current.source === source}
                  onChange={() => {
                    save.reset();
                    setDraft({ ...current, source });
                  }}
                />
                {t(`account.profile.sourceName.${source}`)}
              </label>
            ))}
          </fieldset>
        )}
        {linked ? (
          <>
            <LinkedValues engineId={engineId} />
            <p className="text-xs text-slate-500">{t('account.profile.linkedNote')}</p>
          </>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label={t('account.profile.equity')}
                value={current.form.equity}
                onChange={(equity) => {
                  set({ equity });
                }}
              />
              <Field
                label={t('account.profile.balanceOptional')}
                value={current.form.balance}
                onChange={(balance) => {
                  set({ balance });
                }}
                hint={t('account.profile.balanceHint')}
              />
              <div className="text-sm">
                <label htmlFor={currencyId} className="block font-medium">
                  {t('account.profile.currency')}
                </label>
                <select
                  id={currencyId}
                  className={INPUT}
                  value={current.form.currency}
                  onChange={(e) => {
                    set({ currency: e.target.value });
                  }}
                >
                  {[...new Set([current.form.currency, ...CURRENCIES])].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label={t('account.profile.leverageInput')}
                value={current.form.leverage}
                onChange={(leverage) => {
                  set({ leverage });
                }}
                hint={t('account.profile.leverageHint')}
              />
              <Field
                label={t('account.profile.riskOptional')}
                value={current.form.risk}
                onChange={(risk) => {
                  set({ risk });
                }}
                hint={t('account.profile.riskHint', { max: RISK_CEILING })}
              />
            </div>
            {problems.length > 0 && current.form.equity !== '' && (
              <ul className={`${BAD} list-disc pl-5`}>
                {problems.map((p) => (
                  <li key={p}>{t(`account.profile.problem.${p as 'equity'}`, { max: RISK_CEILING })}</li>
                ))}
              </ul>
            )}
          </>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <button type="submit" className={PRIMARY} disabled={problems.length > 0 || save.isPending}>
            {t('account.profile.save')}
          </button>
          {save.isSuccess && (
            <span role="status" className="text-sm text-slate-600 dark:text-slate-400">
              {t('account.profile.saved')}
            </span>
          )}
          {save.error && (
            <span role="alert" className={BAD}>
              {save.error instanceof ApiError && save.error.code === 'engine_not_found'
                ? t('account.profile.engineGone')
                : t('account.profile.failed')}
            </span>
          )}
        </div>
      </form>
    </Card>
  );
}

function Allowed({
  label,
  values,
  kind,
}: {
  label: string;
  values: string[] | null;
  kind: 'assetClass' | 'family';
}) {
  const { t, i18n } = useTranslation();
  return (
    <div className="text-sm">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd>
        {values === null ? t('account.plan.all') : values.map((v) => translateCode(i18n, kind, v)).join(', ')}
      </dd>
    </div>
  );
}

function PlanCard({ ent }: { ent: MyEntitlements }) {
  const { t } = useTranslation();
  return (
    <Card title={t('account.plan.title')}>
      <p className="mb-3 text-lg font-semibold">
        <PlanName code={ent.plan} />
      </p>
      <h3 className="mb-1 text-sm font-medium">{t('account.plan.usage')}</h3>
      <table className="mb-3 w-full text-sm">
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
          {LIMITS.map((limit) => {
            const max = ent.limits[limit] ?? null;
            const used = ent.usage[limit] ?? 0;
            return (
              <tr key={limit}>
                <td className="py-1">{t(`account.limit.${limit}`)}</td>
                <td className="py-1 text-right tabular-nums">
                  {max === null ? t('account.plan.noLimit', { used }) : t('account.plan.used', { used, max })}
                  {ent.overrides.includes(limit) && ` · ${t('account.plan.adjusted')}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h3 className="mb-1 text-sm font-medium">{t('account.plan.features')}</h3>
      <ul className="mb-3 text-sm">
        {FEATURES.map((feature) => (
          <li key={feature}>
            <span aria-hidden="true">{ent.features[feature] === true ? '✓' : '–'}</span>{' '}
            {t(`account.feature.${feature}`)}
            <span className="sr-only">
              : {ent.features[feature] === true ? t('account.plan.included') : t('account.plan.notIncluded')}
            </span>
          </li>
        ))}
      </ul>
      <dl className="space-y-2">
        <Allowed label={t('account.plan.assetClasses')} values={ent.asset_classes} kind="assetClass" />
        <Allowed label={t('account.plan.families')} values={ent.families} kind="family" />
      </dl>
    </Card>
  );
}

const CheckoutSchema = z.object({ url: z.string() });

/** Plans to buy: only while subscriptions are enabled (`/billing/*` answers 404 otherwise, so nothing shows). */
function BillingCard({ current }: { current: string }) {
  const { t } = useTranslation();
  const plans = useQuery({
    queryKey: accountKeys.billingPlans,
    queryFn: ({ signal }) => apiGet('/billing/plans', PlansSchema, { signal }),
    retry: false,
  });
  const checkout = useMutation({
    mutationFn: (plan: string) => apiPost('/billing/checkout', { plan }, CheckoutSchema),
    onSuccess: (data) => {
      window.location.assign(data.url);
    },
  });
  if (plans.data === undefined) return null;
  return (
    <Card title={t('account.billing.title')}>
      <ul className="space-y-2">
        {plans.data.items.map((plan) => (
          <li key={plan.code} className="flex items-center justify-between gap-2 text-sm">
            <PlanName code={plan.code} />
            <button
              type="button"
              className={PRIMARY}
              disabled={plan.code === current || checkout.isPending}
              onClick={() => {
                checkout.mutate(plan.code);
              }}
            >
              {plan.code === current ? t('account.billing.current') : t('account.billing.choose')}
            </button>
          </li>
        ))}
      </ul>
      {checkout.error && (
        <p role="alert" className={`${BAD} mt-2`}>
          {t('account.billing.unavailable')}
        </p>
      )}
    </Card>
  );
}

/**
 * PLAN §A30 settings pages (TAA-921): the account the user's alerts are sized for (linked MT5 values for an
 * engine owner, a manual form otherwise) and the plan with this period's usage. Billing shows only while
 * subscriptions are enabled.
 */
export function AccountPage() {
  const { t } = useTranslation();
  const ent = useEntitlements();
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.account')}</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <ProfileCard />
        <div className="flex flex-col gap-4">
          {ent.data === undefined ? (
            <Card title={t('account.plan.title')}>
              <Loading error={ent.isError} />
            </Card>
          ) : (
            <>
              <PlanCard ent={ent.data} />
              <BillingCard current={ent.data.plan} />
            </>
          )}
        </div>
      </div>
    </section>
  );
}
