import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type SubmitEvent, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation, useNavigate } from 'react-router';

import { ApiError, ApiSchemaError } from '@/api/client';
import { useAuthState } from '@/auth/hooks';
import { AUTH_QUERY_KEY, type AuthState, login, safeReturnPath, signedIn } from '@/auth/session';

const INPUT =
  'mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900';

function readLocationState(state: unknown): { from: string; reason: unknown } {
  if (typeof state !== 'object' || state === null) return { from: '/', reason: null };
  const { from, reason } = state as { from?: unknown; reason?: unknown };
  return { from: safeReturnPath(from), reason };
}

export function LoginPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const auth = useAuthState();
  const ids = { username: useId(), password: useId(), code: useId(), codeHint: useId() };
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const { from, reason } = readLocationState(location.state);

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (session) => {
      queryClient.setQueryData<AuthState>(AUTH_QUERY_KEY, signedIn(session));
      void navigate(from, { replace: true });
    },
    onError: () => {
      setCode('');
    },
  });

  if (auth.data?.status === 'signed_in' && !mutation.isPending) {
    return <Navigate to={from} replace />;
  }

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    mutation.mutate({ username, password, code });
  };

  return (
    <section className="mx-auto max-w-sm">
      <h1 className="text-2xl font-semibold">{t('auth.title')}</h1>
      {reason === 'expired' && !mutation.isError && (
        <p role="status" className="mt-3 rounded bg-amber-100 px-3 py-2 text-amber-900">
          {t('auth.sessionExpired')}
        </p>
      )}
      {reason === 'logged_out' && !mutation.isError && (
        <p role="status" className="mt-3 rounded bg-slate-200 px-3 py-2 dark:bg-slate-800">
          {t('auth.signedOut')}
        </p>
      )}
      {mutation.isError && (
        <p role="alert" className="mt-3 rounded bg-red-100 px-3 py-2 text-red-900">
          {errorText(mutation.error, t)}
        </p>
      )}
      <form className="mt-4 space-y-4" onSubmit={onSubmit} noValidate={false}>
        <div>
          <label htmlFor={ids.username}>{t('auth.username')}</label>
          <input
            id={ids.username}
            className={INPUT}
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            maxLength={64}
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
            }}
          />
        </div>
        <div>
          <label htmlFor={ids.password}>{t('auth.password')}</label>
          <input
            id={ids.password}
            className={INPUT}
            name="password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={256}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
          />
        </div>
        <div>
          <label htmlFor={ids.code}>{t('auth.code')}</label>
          <input
            id={ids.code}
            className={INPUT}
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            required
            maxLength={6}
            aria-describedby={ids.codeHint}
            value={code}
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, '').slice(0, 6));
            }}
          />
          <p id={ids.codeHint} className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {t('auth.codeHint')}
          </p>
        </div>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full rounded bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900"
        >
          {mutation.isPending ? t('auth.submitting') : t('auth.submit')}
        </button>
      </form>
    </section>
  );
}

function errorText(error: Error, t: ReturnType<typeof useTranslation>['t']): string {
  if (error instanceof ApiError) {
    if (error.code === 'invalid_credentials') return t('auth.errors.invalidCredentials');
    if (error.code === 'too_many_attempts') {
      return t('auth.errors.tooManyAttempts', {
        minutes: Math.max(1, Math.ceil((error.retryAfter ?? 60) / 60)),
      });
    }
    return t('auth.errors.unknown');
  }
  if (error instanceof ApiSchemaError) return t('auth.errors.unknown');
  return t('auth.errors.network');
}
