import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, Outlet, useNavigate } from 'react-router';

import { ThemeSwitcher } from '@/app/ThemeSwitcher';

import { useAuthState, useSessionExpiry } from '@/auth/hooks';
import { endSession, logout } from '@/auth/session';
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher';

/** The page frame: the header (brand, account, theme, language) above every page. */
export function Layout() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data } = useAuthState();
  useSessionExpiry();

  const signOut = useMutation({
    mutationFn: logout,
    // Whatever the server answers (even "already ended"), this browser is signed out afterwards.
    onSettled: () => {
      endSession(queryClient, 'logged_out');
      void navigate('/login', { replace: true, state: { from: '/', reason: 'logged_out' } });
    },
  });

  return (
    <div className="min-h-dvh bg-slate-50 font-sans text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-800">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-3">
          <Link to="/" className="text-lg font-semibold">
            {t('app.name')}
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            {data?.status === 'signed_in' && (
              <>
                <span className="hidden text-sm text-slate-600 sm:inline dark:text-slate-400">
                  {t('auth.signedInAs', { username: data.session.user.username })}
                </span>
                <button
                  type="button"
                  disabled={signOut.isPending}
                  onClick={() => {
                    signOut.mutate();
                  }}
                  className="rounded px-2 py-1 text-sm underline hover:bg-slate-200 dark:hover:bg-slate-800"
                >
                  {t('auth.logout')}
                </button>
              </>
            )}
            <ThemeSwitcher />
            <LanguageSwitcher />
          </div>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
