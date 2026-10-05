import { useTranslation } from 'react-i18next';

import { translateCode } from '@/i18n/codes';
import { translateDynamic } from '@/i18n/dynamic';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { LIMITATION_KEYS } from './backtestModel';
import type { Run } from './schemas';

export function PresetName({ preset }: { preset: string }) {
  const { i18n } = useTranslation();
  const key = `backtests.preset.${preset}.name`;
  return <>{i18n.exists(key) ? translateDynamic(i18n, key) : preset}</>;
}

const STATUS_TONE: Record<string, string> = {
  DONE: 'text-emerald-700 dark:text-emerald-400',
  FAILED: 'text-red-700 dark:text-red-400',
};

export function RunStatus({ run }: { run: Pick<Run, 'status' | 'progress'> }) {
  const { i18n } = useTranslation();
  const format = useFormat();
  return (
    <span className={STATUS_TONE[run.status] ?? 'text-slate-500'}>
      {translateCode(i18n, 'backtestStatus', run.status)}
      {run.status === 'RUNNING' && ` ${format.percent(run.progress * 100, { maximumFractionDigits: 0 })}`}
    </span>
  );
}

/** The backtester's documented limitations and the hypothetical-results note (PLAN §A17). */
export function Limitations() {
  const { t } = useTranslation();
  return (
    <Card title={t('backtests.limitations.title')}>
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
        {LIMITATION_KEYS.map((key) => (
          <li key={key}>{t(`backtests.limitations.${key}`)}</li>
        ))}
      </ul>
    </Card>
  );
}
