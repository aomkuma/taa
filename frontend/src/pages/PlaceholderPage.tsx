import { useTranslation } from 'react-i18next';

import type { NavId } from '@/app/shell/nav';

/** A page that is not built yet; its ticket replaces this route. */
export function PlaceholderPage({ id }: { id: NavId }) {
  const { t } = useTranslation();
  return (
    <section>
      <h1 className="text-2xl font-semibold">{t(`nav.${id}`)}</h1>
      <p className="mt-2 text-slate-600 dark:text-slate-400">{t('shell.placeholder')}</p>
    </section>
  );
}
