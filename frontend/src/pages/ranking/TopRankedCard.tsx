import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ApiError } from '@/api/client';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { useRanking } from './hooks';
import { topEligible } from './rankingModel';

const TOP = 5;

/** The dashboard's top-5 ranked symbols this user can trade (PLAN §A28 dashboard additions). */
export function TopRankedCard({ engineId }: { engineId: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const ranking = useRanking(engineId);
  const top = ranking.data ? topEligible(ranking.data.items, TOP) : [];
  const notYet = ranking.error instanceof ApiError && ranking.error.code === 'advisory_not_found';
  return (
    <Card
      title={t('ranking.top.title')}
      action={
        <Link to="/ranking" className="text-sm underline">
          {t('ranking.top.all')}
        </Link>
      }
    >
      {ranking.data === undefined ? (
        ranking.isError && !notYet ? (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {t('dashboard.loadFailed')}
          </p>
        ) : (
          <p className="text-sm text-slate-500">{t(notYet ? 'ranking.empty' : 'dashboard.loading')}</p>
        )
      ) : top.length === 0 ? (
        <p className="text-sm text-slate-500">{t('ranking.top.none')}</p>
      ) : (
        <ol className="text-sm">
          {top.map((item, index) => (
            <li
              key={item.symbol}
              className="flex items-baseline justify-between gap-2 border-b border-slate-100 py-1 last:border-0 dark:border-slate-800"
            >
              <span>
                <span className="mr-2 text-slate-500 tabular-nums">{index + 1}.</span>
                <Link
                  to={`/ranking?symbol=${encodeURIComponent(item.symbol)}`}
                  className="font-medium underline"
                >
                  {item.symbol}
                </Link>
                <span className="ml-2 text-xs text-slate-500">
                  {translateCode(i18n, 'assetClass', item.asset_class)}
                </span>
              </span>
              <span className="tabular-nums">
                {t('ranking.top.now', { score: format.number(item.now_score, { maximumFractionDigits: 1 }) })}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
