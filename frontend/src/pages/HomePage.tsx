import { useTranslation } from 'react-i18next';

export function HomePage() {
  const { t } = useTranslation();
  return (
    <section>
      <h1 className="text-2xl font-semibold">{t('home.title')}</h1>
      <p className="mt-2 text-slate-600 dark:text-slate-400">{t('home.intro')}</p>
    </section>
  );
}
