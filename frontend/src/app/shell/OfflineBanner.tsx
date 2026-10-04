import { useTranslation } from 'react-i18next';

import { useOnline } from '@/live/network';

export function OfflineBanner() {
  const { t } = useTranslation();
  const online = useOnline();
  if (online) return null;
  return (
    <p role="status" className="bg-amber-200 px-4 py-1.5 text-center text-sm text-amber-950">
      {t('shell.offline')}
    </p>
  );
}
