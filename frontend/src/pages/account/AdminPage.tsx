import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { apiDelete, apiGet, apiPost, apiPut } from '@/api/client';
import { ADMIN_ROLES } from '@/app/shell/nav';
import { useAuthState } from '@/auth/hooks';
import { StepUpDialog } from '@/components/StepUpDialog';
import { ASSET_CLASSES, FAMILIES, translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { type OverrideValue, overrideKind, overrideValueOf } from './accountModel';
import { PlanName } from './parts';
import {
  type AdminUser,
  AdminUsersSchema,
  ALLOW_LISTS,
  accountKeys,
  EntitlementsSchema,
  FEATURES,
  LIMITS,
  type OverrideRow,
  PlansSchema,
  type UserEntitlements,
  UserEntitlementsSchema,
} from './schemas';

const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const INPUT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950';
const TH = 'px-2 py-1 text-left font-medium';
const KEYS = [...FEATURES, ...LIMITS, ...ALLOW_LISTS];

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-500">{error ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
}

function useRole(): string | null {
  const { data } = useAuthState();
  return data?.status === 'signed_in' ? data.session.user.role : null;
}

/** An override's value in words. */
function ValueText({ keyName, value }: { keyName: string; value: OverrideRow['value'] }) {
  const { t, i18n } = useTranslation();
  if (value === null) return <>{t('admin.override.unlimited')}</>;
  if (typeof value === 'boolean') return <>{value ? t('admin.override.on') : t('admin.override.off')}</>;
  if (Array.isArray(value)) {
    const kind = keyName === 'FAMILIES' ? 'family' : 'assetClass';
    return <>{value.map((v) => translateCode(i18n, kind, v)).join(', ') || '—'}</>;
  }
  return <>{value}</>;
}

function keyLabel(t: (key: string) => string, key: string): string {
  if ((FEATURES as readonly string[]).includes(key)) return t(`account.feature.${key}`);
  if ((LIMITS as readonly string[]).includes(key)) return t(`account.limit.${key}`);
  return t(`admin.allowList.${key}`);
}

function KeyLabel({ name }: { name: string }) {
  const { t } = useTranslation();
  return <>{keyLabel(t as (key: string) => string, name)}</>;
}

function ValueEditor({
  keyName,
  value,
  onChange,
}: {
  keyName: string;
  value: OverrideValue;
  onChange: (value: OverrideValue) => void;
}) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const kind = overrideKind(keyName);
  if (kind === 'feature') {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(e) => {
            onChange(e.target.checked);
          }}
        />
        {t('admin.override.included')}
      </label>
    );
  }
  if (kind === 'limit') {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor={id}>{t('admin.override.limit')}</label>
        <input
          id={id}
          type="number"
          min={0}
          step={1}
          className={`${INPUT} w-28`}
          value={typeof value === 'number' ? value : ''}
          placeholder={t('admin.override.unlimited')}
          onChange={(e) => {
            onChange(e.target.value === '' ? null : Number(e.target.value));
          }}
        />
        <span className="text-xs text-slate-500">{t('admin.override.emptyUnlimited')}</span>
      </div>
    );
  }
  const options: readonly string[] = keyName === 'FAMILIES' ? FAMILIES : ASSET_CLASSES;
  const codeKind = keyName === 'FAMILIES' ? 'family' : 'assetClass';
  const chosen = Array.isArray(value) ? value : [];
  return (
    <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      <legend className="sr-only">{keyLabel(t as (key: string) => string, keyName)}</legend>
      <label className="flex w-full items-center gap-1.5">
        <input
          type="checkbox"
          checked={value === null}
          onChange={(e) => {
            onChange(e.target.checked ? null : []);
          }}
        />
        {t('account.plan.all')}
      </label>
      {value !== null &&
        options.map((option) => (
          <label key={option} className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={chosen.includes(option)}
              onChange={(e) => {
                onChange(e.target.checked ? [...chosen, option] : chosen.filter((c) => c !== option));
              }}
            />
            {translateCode(i18n, codeKind, option)}
          </label>
        ))}
    </fieldset>
  );
}

type Action =
  | { kind: 'plan'; plan: string }
  | { kind: 'override'; key: string; value: OverrideValue; reason: string }
  | { kind: 'remove'; key: string };

function useAdminActions(user: AdminUser) {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: accountKeys.users });
  };
  const base = `/admin/users/${encodeURIComponent(user.id)}`;
  return useMutation({
    mutationFn: async (action: Action) => {
      if (action.kind === 'plan') await apiPost(`${base}/plan`, { plan: action.plan }, EntitlementsSchema);
      else if (action.kind === 'override') {
        await apiPut(
          `${base}/overrides/${action.key}`,
          { value: action.value, reason: action.reason },
          EntitlementsSchema,
        );
      } else await apiDelete(`${base}/overrides/${action.key}`);
    },
    onSuccess: refresh,
  });
}

function UserPanel({ user, canEdit }: { user: AdminUser; canEdit: boolean }) {
  const { t } = useTranslation();
  const format = useFormat();
  const planId = useId();
  const keyId = useId();
  const reasonId = useId();
  const ent = useQuery({
    queryKey: accountKeys.user(user.id),
    queryFn: ({ signal }) =>
      apiGet(`/admin/users/${encodeURIComponent(user.id)}/entitlements`, UserEntitlementsSchema, { signal }),
  });
  const plans = useQuery({
    queryKey: accountKeys.plans,
    queryFn: ({ signal }) => apiGet('/admin/plans', PlansSchema, { signal }),
  });
  const action = useAdminActions(user);
  const [pending, setPending] = useState<Action | null>(null);
  const [plan, setPlan] = useState('');
  const [key, setKey] = useState<string>(LIMITS[0]);
  const [value, setValue] = useState<OverrideValue>(null);
  const [reason, setReason] = useState('');
  const data: UserEntitlements | undefined = ent.data;
  return (
    <Card title={t('admin.user.title', { name: user.username })}>
      {data === undefined ? (
        <Loading error={ent.isError} />
      ) : (
        <div className="space-y-4 text-sm">
          <p>
            {t('admin.user.plan')}:{' '}
            <strong>
              <PlanName code={data.plan} />
            </strong>
          </p>
          <table className="w-full">
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {LIMITS.map((limit) => (
                <tr key={limit}>
                  <td className="py-1">{t(`account.limit.${limit}`)}</td>
                  <td className="py-1 text-right tabular-nums">
                    <ValueText keyName={limit} value={data.limits[limit] ?? null} />
                  </td>
                </tr>
              ))}
              {FEATURES.map((feature) => (
                <tr key={feature}>
                  <td className="py-1">{t(`account.feature.${feature}`)}</td>
                  <td className="py-1 text-right">
                    <ValueText keyName={feature} value={data.features[feature] ?? false} />
                  </td>
                </tr>
              ))}
              <tr>
                <td className="py-1">{t('admin.allowList.ASSET_CLASSES')}</td>
                <td className="py-1 text-right">
                  {data.asset_classes === null ? (
                    t('account.plan.all')
                  ) : (
                    <ValueText keyName="ASSET_CLASSES" value={data.asset_classes} />
                  )}
                </td>
              </tr>
              <tr>
                <td className="py-1">{t('admin.allowList.FAMILIES')}</td>
                <td className="py-1 text-right">
                  {data.families === null ? (
                    t('account.plan.all')
                  ) : (
                    <ValueText keyName="FAMILIES" value={data.families} />
                  )}
                </td>
              </tr>
            </tbody>
          </table>

          <section aria-label={t('admin.override.title')}>
            <h3 className="mb-1 font-medium">{t('admin.override.title')}</h3>
            {data.override_rows.length === 0 ? (
              <p className="text-slate-500">{t('admin.override.none')}</p>
            ) : (
              <table className="w-full">
                <thead className="text-xs text-slate-500">
                  <tr>
                    <th className={TH}>{t('admin.override.key')}</th>
                    <th className={TH}>{t('admin.override.value')}</th>
                    <th className={TH}>{t('admin.override.reason')}</th>
                    <th className={TH}>{t('admin.override.by')}</th>
                    {canEdit && (
                      <th className={TH}>
                        <span className="sr-only">{t('admin.override.remove')}</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {data.override_rows.map((row) => (
                    <tr key={row.key}>
                      <td className="px-2 py-1">
                        <KeyLabel name={row.key} />
                      </td>
                      <td className="px-2 py-1">
                        <ValueText keyName={row.key} value={row.value} />
                      </td>
                      <td className="px-2 py-1">{row.reason || '—'}</td>
                      <td className="px-2 py-1 text-xs text-slate-500">
                        {row.created_by} · {format.dateTime(row.created_at)}
                      </td>
                      {canEdit && (
                        <td className="px-2 py-1">
                          <button
                            type="button"
                            className="text-sm underline"
                            aria-label={t('admin.override.removeKey', {
                              key: keyLabel(t as (k: string) => string, row.key),
                            })}
                            onClick={() => {
                              setPending({ kind: 'remove', key: row.key });
                            }}
                          >
                            {t('admin.override.remove')}
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {canEdit ? (
            <>
              <section aria-label={t('admin.assign.title')} className="space-y-2">
                <h3 className="font-medium">{t('admin.assign.title')}</h3>
                <div className="flex flex-wrap items-center gap-2">
                  <label htmlFor={planId} className="sr-only">
                    {t('admin.assign.title')}
                  </label>
                  <select
                    id={planId}
                    className={INPUT}
                    value={plan}
                    onChange={(e) => {
                      setPlan(e.target.value);
                    }}
                  >
                    <option value="">{t('admin.assign.choose')}</option>
                    {(plans.data?.items ?? []).map((p) => (
                      <option key={p.code} value={p.code}>
                        {p.code}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className={BUTTON}
                    disabled={plan === '' || plan === data.plan}
                    onClick={() => {
                      setPending({ kind: 'plan', plan });
                    }}
                  >
                    {t('admin.assign.button')}
                  </button>
                </div>
                <p className="text-xs text-slate-500">{t('admin.assign.note')}</p>
              </section>

              <section aria-label={t('admin.override.add')} className="space-y-2">
                <h3 className="font-medium">{t('admin.override.add')}</h3>
                <div className="flex flex-wrap items-center gap-2">
                  <label htmlFor={keyId}>{t('admin.override.key')}</label>
                  <select
                    id={keyId}
                    className={INPUT}
                    value={key}
                    onChange={(e) => {
                      setKey(e.target.value);
                      setValue(overrideValueOf(e.target.value, data));
                    }}
                  >
                    {KEYS.map((k) => (
                      <option key={k} value={k}>
                        {keyLabel(t as (k2: string) => string, k)}
                      </option>
                    ))}
                  </select>
                </div>
                <ValueEditor keyName={key} value={value} onChange={setValue} />
                <div className="flex flex-wrap items-center gap-2">
                  <label htmlFor={reasonId}>{t('admin.override.reason')}</label>
                  <input
                    id={reasonId}
                    className={`${INPUT} w-64`}
                    maxLength={200}
                    value={reason}
                    onChange={(e) => {
                      setReason(e.target.value);
                    }}
                  />
                  <button
                    type="button"
                    className={BUTTON}
                    // an empty allow-list would leave the user nothing: pick items or "all"
                    disabled={Array.isArray(value) && value.length === 0}
                    onClick={() => {
                      setPending({ kind: 'override', key, value, reason });
                    }}
                  >
                    {t('admin.override.save')}
                  </button>
                </div>
              </section>
            </>
          ) : (
            <p className="text-xs text-slate-500">{t('admin.readOnly')}</p>
          )}
        </div>
      )}
      {pending !== null && (
        <StepUpDialog
          title={t(`admin.confirm.${pending.kind}.title`)}
          confirmLabel={t(`admin.confirm.${pending.kind}.button`)}
          onConfirm={async () => {
            await action.mutateAsync(pending);
            if (pending.kind === 'override') setReason('');
            await ent.refetch();
          }}
          onClose={() => {
            setPending(null);
          }}
        >
          <p>
            {pending.kind === 'plan'
              ? t('admin.confirm.plan.body', { name: user.username, plan: pending.plan })
              : t(`admin.confirm.${pending.kind}.body`, {
                  name: user.username,
                  key: keyLabel(t as (k: string) => string, pending.key),
                })}
          </p>
        </StepUpDialog>
      )}
    </Card>
  );
}

/**
 * PLAN §A30 owner admin (TAA-921): the users with their plans; per user the resolved entitlements, the
 * overrides behind them, and (OWNER only, with step-up) plan assignment and overrides. Billing stays off.
 */
export function AdminPage() {
  const { t } = useTranslation();
  const format = useFormat();
  const role = useRole();
  const [params, setParams] = useSearchParams();
  const allowed = role !== null && ADMIN_ROLES.includes(role);
  const users = useQuery({
    queryKey: accountKeys.users,
    queryFn: ({ signal }) => apiGet('/admin/users', AdminUsersSchema, { signal }),
    enabled: allowed,
  });
  if (!allowed) {
    return (
      <section>
        <h1 className="mb-4 text-2xl font-semibold">{t('nav.admin')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('admin.forbidden')}</p>
      </section>
    );
  }
  const selected = users.data?.items.find((u) => u.id === params.get('user'));
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.admin')}</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t('admin.users.title')}>
          {users.data === undefined ? (
            <Loading error={users.isError} />
          ) : (
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className={TH}>{t('admin.users.username')}</th>
                  <th className={TH}>{t('admin.users.role')}</th>
                  <th className={TH}>{t('admin.users.plan')}</th>
                  <th className={TH}>{t('admin.users.since')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {users.data.items.map((u) => (
                  <tr key={u.id} className={u.id === selected?.id ? 'bg-sky-50 dark:bg-sky-950/40' : ''}>
                    <td className="px-2 py-1">
                      <button
                        type="button"
                        className="underline"
                        onClick={() => {
                          setParams({ user: u.id });
                        }}
                      >
                        {u.username}
                      </button>
                      {u.disabled && (
                        <span className="ml-1 text-xs text-slate-500">{t('admin.users.disabled')}</span>
                      )}
                    </td>
                    <td className="px-2 py-1">{t(`admin.role.${u.role as 'OWNER'}`)}</td>
                    <td className="px-2 py-1">
                      <PlanName code={u.plan} />
                    </td>
                    <td className="px-2 py-1 text-xs text-slate-500">{format.date(u.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mt-2 text-xs text-slate-500">{t('admin.users.note')}</p>
        </Card>
        {selected !== undefined && <UserPanel key={selected.id} user={selected} canEdit={role === 'OWNER'} />}
      </div>
    </section>
  );
}
