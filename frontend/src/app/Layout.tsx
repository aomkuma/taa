import { useTranslation } from 'react-i18next';
import { Link, Outlet } from 'react-router';

import { LanguageSwitcher } from '@/i18n/LanguageSwitcher';

export function Layout() {
  const { t } = useTranslation();
  return (
    <div className="min-h-dvh bg-slate-50 font-sans text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-800">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-semibold">
            {t('app.name')}
          </Link>
          <LanguageSwitcher />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
