import { useTranslation } from 'react-i18next';

import { useFormat } from '@/i18n/useFormat';

/** "Not up to date since <time>": shown wherever data stopped updating (live stream lost, offline, cache). */
export function StaleBadge({ since }: { since: number | string | null }) {
  const { t } = useTranslation();
  const format = useFormat();
  const time = since === null ? null : format.dateTime(typeof since === 'number' ? new Date(since) : since);
  return (
    <span className="inline-flex items-center rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
      {time === null ? t('shell.stale') : t('shell.staleSince', { time })}
    </span>
  );
}
