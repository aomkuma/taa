import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <section>
      <h1 className="text-2xl font-semibold">{t('notFound.title')}</h1>
      <Link to="/" className="mt-2 inline-block underline">
        {t('notFound.back')}
      </Link>
    </section>
  );
}
