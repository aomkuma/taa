import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { useAccuracy } from '@/pages/accuracy/hooks';
import { useOpportunities } from '@/pages/opportunities/hooks';

import { Card } from './cards';

const SHOWN = 5;

/** The opportunities whose window is open now, strongest first (PLAN §A28 dashboard additions). */
export function ActiveOpportunitiesCard({ engineId }: { engineId: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const list = useOpportunities(engineId);
  const active = (list.data?.items ?? [])
    .filter((o) => o.status === 'ACTIVE')
    .sort((a, b) => b.setup_strength - a.setup_strength);
  return (
    <Card
      title={t('dashboard.opportunities.title')}
      action={
        <Link to="/opportunities" className="text-sm underline">
          {t('dashboard.opportunities.all')}
        </Link>
      }
    >
      {list.data === undefined ? (
        <p className="text-sm text-slate-500">
          {list.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : active.length === 0 ? (
        <p className="text-sm text-slate-500">{t('dashboard.opportunities.none')}</p>
      ) : (
        <ul className="text-sm">
          {active.slice(0, SHOWN).map((o) => (
            <li
              key={o.opportunity_id}
              className="flex items-baseline justify-between gap-2 border-b border-slate-100 py-1 last:border-0 dark:border-slate-800"
            >
              <span>
                <Link
                  to={`/opportunities/${encodeURIComponent(o.opportunity_id)}`}
                  className="font-medium underline"
                >
                  {o.symbol} {o.side === 'BUY' ? t('opportunities.buy') : t('opportunities.sell')}
                </Link>
                <span className="ml-2 text-xs text-slate-500">
                  {translateCode(i18n, 'strategyName', o.strategy)} · {o.timeframe}
                </span>
              </span>
              <span className="tabular-nums">
                {t('dashboard.opportunities.strength', {
                  value: format.number(o.setup_strength, { maximumFractionDigits: 0 }),
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
      {active.length > SHOWN && (
        <p className="mt-1 text-xs text-slate-500">
          {t('dashboard.opportunities.more', { n: active.length - SHOWN })}
        </p>
      )}
    </Card>
  );
}

/** The signals' simulated track record (shadow trades as planned, LIVE section) in three numbers. */
export function AccuracySummaryCard({ engineId }: { engineId: string }) {
  const { t } = useTranslation();
  const format = useFormat();
  const accuracy = useAccuracy(engineId, 'PLAN', false);
  const s = accuracy.data?.live.summary;
  const pct = (v: number | null) => (v === null ? '—' : format.percent(v, { maximumFractionDigits: 0 }));
  return (
    <Card
      title={t('dashboard.accuracy.title')}
      action={
        <Link to="/accuracy" className="text-sm underline">
          {t('dashboard.accuracy.all')}
        </Link>
      }
    >
      {s === undefined ? (
        <p className="text-sm text-slate-500">
          {accuracy.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : s.n === 0 ? (
        <p className="text-sm text-slate-500">{t('dashboard.accuracy.none')}</p>
      ) : (
        <>
          <dl className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <dt className="text-xs text-slate-500">{t('dashboard.accuracy.closed')}</dt>
              <dd className="text-lg font-semibold tabular-nums">{format.number(s.n)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">{t('dashboard.accuracy.hitRate')}</dt>
              <dd className="text-lg font-semibold tabular-nums">{pct(s.hit_rate)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">{t('dashboard.accuracy.expectancy')}</dt>
              <dd className="text-lg font-semibold tabular-nums">
                {s.expectancy_r === null
                  ? '—'
                  : `${format.number(s.expectancy_r, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}R`}
              </dd>
            </div>
          </dl>
          {s.hit_low !== null && s.hit_high !== null && (
            <p className="mt-1 text-xs text-slate-500">
              {t('dashboard.accuracy.range', { low: pct(s.hit_low), high: pct(s.hit_high) })}
            </p>
          )}
        </>
      )}
      <p className="mt-1 text-xs text-slate-500">{t('dashboard.accuracy.simulated')}</p>
    </Card>
  );
}
