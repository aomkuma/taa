import { useTranslation } from 'react-i18next';

import { applyUpdate, dismissUpdate, useUpdateAvailable } from '@/app/swUpdate';

/** Offers the newer app version the service worker has downloaded. */
export function UpdateBanner() {
  const { t } = useTranslation();
  const available = useUpdateAvailable();
  if (!available) return null;
  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-center gap-3 bg-sky-100 px-4 py-1.5 text-sm text-sky-950 dark:bg-sky-900 dark:text-sky-50"
    >
      <span>{t('shell.update.available')}</span>
      <button
        type="button"
        className="rounded bg-sky-700 px-2 py-0.5 font-medium text-white hover:bg-sky-800"
        onClick={() => {
          void applyUpdate();
        }}
      >
        {t('shell.update.reload')}
      </button>
      <button
        type="button"
        className="underline"
        onClick={() => {
          dismissUpdate();
        }}
      >
        {t('shell.update.later')}
      </button>
    </div>
  );
}
