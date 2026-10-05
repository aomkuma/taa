import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError, apiGet, apiPost, apiPostEmpty, apiPut } from '@/api/client';
import { useAuthState } from '@/auth/hooks';
import { AUTH_QUERY_KEY } from '@/auth/session';
import { StepUpDialog } from '@/components/StepUpDialog';
import { useEngine } from '@/engine/context';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { deviceLabel } from '@/pages/notifications/push';
import {
  type Enrollment,
  EnrollmentSchema,
  MaskedConfigSchema,
  PasswordChangedSchema,
  ProfileSchema,
  RevokedOthersSchema,
  SessionsSchema,
  systemKeys,
} from '@/pages/system/schemas';

const INPUT =
  'mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-950';
const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const OK = 'text-emerald-700 dark:text-emerald-400';
const BAD = 'text-red-700 dark:text-red-400';
const TIMEZONES = [
  'Asia/Bangkok',
  'UTC',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Europe/London',
  'America/New_York',
];
const MIN_PASSWORD = 8;

function Field({
  label,
  type = 'text',
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block font-medium">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        onChange={(e) => {
          onChange(e.target.value);
        }}
        className={INPUT}
      />
    </div>
  );
}

// --- profile ------------------------------------------------------------------------------------------------

function ProfileCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data } = useAuthState();
  const user = data?.status === 'signed_in' ? data.session.user : null;
  const langId = useId();
  const zoneId = useId();
  const save = useMutation({
    mutationFn: (body: { locale: string; timezone: string }) => apiPut('/auth/profile', body, ProfileSchema),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY }),
  });
  if (user === null) return null;
  const zones = TIMEZONES.includes(user.timezone) ? TIMEZONES : [user.timezone, ...TIMEZONES];
  return (
    <Card title={t('settings.profile.title')}>
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <label htmlFor={langId} className="block font-medium">
            {t('settings.profile.language')}
          </label>
          <select
            id={langId}
            value={user.locale}
            disabled={save.isPending}
            onChange={(e) => {
              save.mutate({ locale: e.target.value, timezone: user.timezone });
            }}
            className={INPUT}
          >
            <option value="th">ไทย</option>
            <option value="en">English</option>
          </select>
        </div>
        <div>
          <label htmlFor={zoneId} className="block font-medium">
            {t('settings.profile.timezone')}
          </label>
          <select
            id={zoneId}
            value={user.timezone}
            disabled={save.isPending}
            onChange={(e) => {
              save.mutate({ locale: user.locale, timezone: e.target.value });
            }}
            className={INPUT}
          >
            {zones.map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">{t('settings.profile.note')}</p>
      {save.isError && (
        <p role="alert" className={`mt-1 text-sm ${BAD}`}>
          {t('settings.failed')}
        </p>
      )}
    </Card>
  );
}

// --- security -----------------------------------------------------------------------------------------------

function PasswordDialog({ onDone, onClose }: { onDone: (revoked: number) => void; onClose: () => void }) {
  const { t } = useTranslation();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  return (
    <StepUpDialog
      title={t('settings.password.title')}
      confirmLabel={t('settings.password.confirm')}
      validate={() => {
        if (current === '' || next === '') return t('settings.password.required');
        if (next.length < MIN_PASSWORD) return t('settings.password.weak');
        if (next !== again) return t('settings.password.mismatch');
        return null;
      }}
      errorText={(err) =>
        err instanceof ApiError && err.code === 'invalid_password'
          ? t('settings.password.wrong')
          : err instanceof ApiError && err.code === 'weak_password'
            ? t('settings.password.weak')
            : null
      }
      onConfirm={async () => {
        const result = await apiPost(
          '/auth/password',
          { current_password: current, new_password: next },
          PasswordChangedSchema,
        );
        onDone(result.other_sessions_revoked);
      }}
      onClose={onClose}
    >
      <p>{t('settings.password.body')}</p>
      <Field
        label={t('settings.password.current')}
        type="password"
        autoComplete="current-password"
        value={current}
        onChange={setCurrent}
      />
      <Field
        label={t('settings.password.new')}
        type="password"
        autoComplete="new-password"
        value={next}
        onChange={setNext}
      />
      <Field
        label={t('settings.password.again')}
        type="password"
        autoComplete="new-password"
        value={again}
        onChange={setAgain}
      />
    </StepUpDialog>
  );
}

function TotpDialog({ onStarted, onClose }: { onStarted: (e: Enrollment) => void; onClose: () => void }) {
  const { t } = useTranslation();
  const [password, setPassword] = useState('');
  return (
    <StepUpDialog
      title={t('settings.totp.title')}
      confirmLabel={t('settings.totp.start')}
      validate={() => (password === '' ? t('settings.password.required') : null)}
      errorText={(err) =>
        err instanceof ApiError && err.code === 'invalid_password' ? t('settings.password.wrong') : null
      }
      onConfirm={async () => {
        onStarted(await apiPost('/auth/totp/enroll', { password }, EnrollmentSchema));
      }}
      onClose={onClose}
    >
      <p>{t('settings.totp.body')}</p>
      <Field
        label={t('settings.password.current')}
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={setPassword}
      />
    </StepUpDialog>
  );
}

function TotpConfirm({ enrollment, onDone }: { enrollment: Enrollment; onDone: (ok: boolean) => void }) {
  const { t } = useTranslation();
  const codeId = useId();
  const [code, setCode] = useState('');
  const confirm = useMutation({
    mutationFn: () => apiPostEmpty('/auth/totp/confirm', { code }),
    onSuccess: () => {
      onDone(true);
    },
  });
  return (
    <div className="mt-3 rounded border border-slate-200 p-3 text-sm dark:border-slate-700">
      <p>{t('settings.totp.scan')}</p>
      <img src={enrollment.qr_svg} alt={t('settings.totp.qr')} className="my-2 h-44 w-44 bg-white p-2" />
      <p className="text-xs">
        {t('settings.totp.manual')} <code className="break-all">{enrollment.secret}</code>
      </p>
      <label htmlFor={codeId} className="mt-2 block font-medium">
        {t('settings.totp.code')}
      </label>
      <div className="mt-1 flex gap-2">
        <input
          id={codeId}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(e) => {
            setCode(e.target.value.replace(/\D/g, ''));
          }}
          className="w-32 rounded border border-slate-300 bg-white px-2 py-1 tracking-widest dark:border-slate-700 dark:bg-slate-950"
        />
        <button
          type="button"
          className={BUTTON}
          disabled={code.length !== 6 || confirm.isPending}
          onClick={() => {
            confirm.mutate();
          }}
        >
          {t('settings.totp.confirm')}
        </button>
        <button
          type="button"
          className="text-sm underline"
          onClick={() => {
            onDone(false);
          }}
        >
          {t('settings.cancel')}
        </button>
      </div>
      {confirm.isError && (
        <p role="alert" className={`mt-2 ${BAD}`}>
          {t('settings.totp.wrongCode')}
        </p>
      )}
    </div>
  );
}

function SecurityCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<'password' | 'totp' | null>(null);
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const close = () => {
    setDialog(null);
  };
  return (
    <Card title={t('settings.security.title')}>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={BUTTON}
          onClick={() => {
            setMessage(null);
            setDialog('password');
          }}
        >
          {t('settings.password.title')}
        </button>
        <button
          type="button"
          className={BUTTON}
          disabled={enrollment !== null}
          onClick={() => {
            setMessage(null);
            setDialog('totp');
          }}
        >
          {t('settings.totp.title')}
        </button>
      </div>
      <p className="mt-2 text-xs text-slate-500">{t('settings.security.note')}</p>
      {enrollment && (
        <TotpConfirm
          enrollment={enrollment}
          onDone={(ok) => {
            setEnrollment(null);
            if (ok) {
              setMessage(t('settings.totp.done'));
              void queryClient.invalidateQueries({ queryKey: systemKeys.sessions });
            }
          }}
        />
      )}
      {message !== null && (
        <p role="status" className={`mt-2 text-sm ${OK}`}>
          {message}
        </p>
      )}
      {dialog === 'password' && (
        <PasswordDialog
          onDone={(revoked) => {
            setMessage(t('settings.password.done', { n: revoked }));
            void queryClient.invalidateQueries({ queryKey: systemKeys.sessions });
          }}
          onClose={close}
        />
      )}
      {dialog === 'totp' && <TotpDialog onStarted={setEnrollment} onClose={close} />}
    </Card>
  );
}

function SessionsCard() {
  const { t } = useTranslation();
  const format = useFormat();
  const queryClient = useQueryClient();
  const sessions = useQuery({
    queryKey: systemKeys.sessions,
    queryFn: ({ signal }) => apiGet('/auth/sessions', SessionsSchema, { signal }),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: systemKeys.sessions });
  const revoke = useMutation({
    mutationFn: (id: string) => apiPostEmpty(`/auth/sessions/${encodeURIComponent(id)}/revoke`),
    onSettled: refresh,
  });
  const revokeOthers = useMutation({
    mutationFn: () => apiPost('/auth/sessions/revoke-others', {}, RevokedOthersSchema),
    onSettled: refresh,
  });
  const items = sessions.data?.items ?? [];
  const others = items.filter((s) => !s.current).length;
  return (
    <Card
      title={t('settings.sessions.title')}
      action={
        others > 0 ? (
          <button
            type="button"
            className="text-sm underline disabled:opacity-50"
            disabled={revokeOthers.isPending}
            onClick={() => {
              revokeOthers.mutate();
            }}
          >
            {t('settings.sessions.endOthers')}
          </button>
        ) : undefined
      }
    >
      {sessions.data === undefined ? (
        <p className="text-sm text-slate-500">
          {sessions.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">
          {items.map((s) => (
            <li key={s.session_id} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5">
              <span>
                <span className="font-medium">{s.user_agent ? deviceLabel(s.user_agent) : '—'}</span>
                {s.current && (
                  <span className="ml-1.5 rounded bg-emerald-100 px-1 text-xs text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
                    {t('settings.sessions.current')}
                  </span>
                )}
                <span className="block text-xs text-slate-500">
                  {t('settings.sessions.detail', {
                    ip: s.ip || '—',
                    since: format.dateTime(s.created_at),
                    seen: format.dateTime(s.last_seen_at),
                  })}
                </span>
              </span>
              {!s.current && (
                <button
                  type="button"
                  className="text-sm underline disabled:opacity-50"
                  disabled={revoke.isPending}
                  onClick={() => {
                    revoke.mutate(s.session_id);
                  }}
                >
                  {t('settings.sessions.end')}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// --- configuration and about ----------------------------------------------------------------------------------

function ConfigCard({ engineId }: { engineId: string }) {
  const { t } = useTranslation();
  const format = useFormat();
  const config = useQuery({
    queryKey: systemKeys.config(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/config`, MaskedConfigSchema, { signal }),
  });
  const data = config.data;
  const sections: [string, unknown][] = data
    ? [
        [t('settings.config.env'), data.config.env],
        ...Object.entries(data.config.config).sort(([a], [b]) => a.localeCompare(b)),
      ]
    : [];
  return (
    <Card title={t('settings.config.title')}>
      {data === undefined ? (
        <p className="text-sm text-slate-500">
          {config.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : (
        <>
          <p className="text-xs text-slate-500">
            {t('settings.config.meta', {
              hash: data.config_hash.slice(0, 12),
              at: format.dateTime(data.created_at),
            })}
          </p>
          <div className="mt-2 space-y-1">
            {sections.map(([name, value]) => (
              <details key={name} className="rounded border border-slate-200 dark:border-slate-800">
                <summary className="cursor-pointer px-2 py-1 text-sm font-medium">{name}</summary>
                <pre className="max-h-96 overflow-auto px-2 py-1 text-xs">
                  {JSON.stringify(value, null, 2)}
                </pre>
              </details>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">{t('settings.config.note')}</p>
        </>
      )}
    </Card>
  );
}

function AboutCard() {
  const { t } = useTranslation();
  return (
    <Card title={t('settings.about.title')}>
      <div className="space-y-2 text-sm">
        <p>{t('settings.about.body')}</p>
        <p className="text-xs text-slate-500">{t('settings.about.disclaimer')}</p>
        <ul className="list-disc pl-5 text-xs">
          <li>
            {t('settings.about.charts')}{' '}
            <a className="underline" href="https://www.tradingview.com/" rel="noreferrer" target="_blank">
              TradingView Lightweight Charts™
            </a>{' '}
            (Apache-2.0)
          </li>
          <li>{t('settings.about.font')}</li>
          <li>{t('settings.about.mt5')}</li>
        </ul>
      </div>
    </Card>
  );
}

/** PLAN §A15 Settings (TAA-913): profile, security, sessions, the effective configuration and about. */
export function SettingsPage() {
  const { t } = useTranslation();
  const { engineId, own } = useEngine();
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.settings')}</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <ProfileCard />
        <SecurityCard />
        <SessionsCard />
        <AboutCard />
        {own && engineId !== null && (
          <div className="lg:col-span-2">
            <ConfigCard engineId={engineId} />
          </div>
        )}
      </div>
    </section>
  );
}
