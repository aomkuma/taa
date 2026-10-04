import { useTranslation } from 'react-i18next';
import { Link, Outlet } from 'react-router';

import { useEngine } from '@/engine/context';

/** Pages with the user's own engine data; on the market feed (or without an engine) they explain why not. */
export function RequireOwnEngine() {
  const { t } = useTranslation();
  const { state, engineId, own } = useEngine();
  if (state !== 'ready') return null; // the engine bar shows loading and errors
  if (engineId === null || !own) {
    return (
      <section>
        <p>{t('shell.ownEngineRequired')}</p>
        <Link to="/engines" className="mt-2 inline-block underline">
          {t('shell.linkEngine')}
        </Link>
      </section>
    );
  }
  return <Outlet />;
}
