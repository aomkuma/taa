import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router';

import { useAuthState } from './hooks';

export interface LoginLocationState {
  from: string;
  reason: 'expired' | 'logged_out' | null;
}

/** Renders the protected routes only for a live session; otherwise sends the user to the login page. */
export function RequireAuth() {
  const { t } = useTranslation();
  const location = useLocation();
  const { data, isPending, isError } = useAuthState();

  if (isPending) {
    return <p role="status">{t('auth.loading')}</p>;
  }
  if (isError) {
    // Fail closed: without a confirmed session nothing protected is shown.
    return <p role="alert">{t('auth.errors.unavailable')}</p>;
  }
  if (data.status === 'signed_out') {
    const state: LoginLocationState = { from: location.pathname + location.search, reason: data.reason };
    return <Navigate to="/login" replace state={state} />;
  }
  return <Outlet />;
}
