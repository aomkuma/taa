import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { useEngine } from '@/engine/context';
import { engineKey } from '@/engine/schemas';
import { useLiveEvents } from '@/live/context';
import { ManualPositionsCard } from '@/pages/trades/ManualPositions';
import { TopRankedCard } from '@/pages/ranking/TopRankedCard';

import { AccuracySummaryCard, ActiveOpportunitiesCard } from './AdvisoryCards';

import { AccountCard, AlertsCard, BreakersCard, DecisionsCard, HealthCard, PositionsCard } from './cards';
import { NOTIFICATIONS_QUERY_KEY } from './schemas';

/** Stream topics → the queries they change (heartbeats update the cached status in the shell already). */
function useLiveDashboard(engineId: string) {
  const queryClient = useQueryClient();
  const refetch = (...key: readonly string[]) => {
    void queryClient.invalidateQueries({ queryKey: key });
  };
  useLiveEvents('positions', () => {
    refetch(...engineKey(engineId), 'positions');
  });
  useLiveEvents('decisions', () => {
    refetch(...engineKey(engineId), 'decisions');
  });
  useLiveEvents('notifications', () => {
    refetch(...NOTIFICATIONS_QUERY_KEY);
  });
  useLiveEvents('status', (event) => {
    if (event.type.startsWith('breaker')) refetch(...engineKey(engineId), 'breakers');
  });
}

function OwnDashboard({ engineId }: { engineId: string }) {
  useLiveDashboard(engineId);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="lg:col-span-2">
        <AccountCard />
      </div>
      <HealthCard />
      <BreakersCard />
      <PositionsCard />
      <ManualPositionsCard compact />
      <DecisionsCard />
      <TopRankedCard engineId={engineId} />
      <ActiveOpportunitiesCard engineId={engineId} />
      <AccuracySummaryCard engineId={engineId} />
      <AlertsCard />
    </div>
  );
}

/** Subscribers on the market feed: no account data; the advisory pages are where their information is. */
function FeedDashboard({ engineId }: { engineId: string | null }) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-lg border border-slate-200 bg-white p-4 lg:col-span-2 dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('home.intro')}</p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <Link to="/opportunities" className="underline">
            {t('nav.opportunities')}
          </Link>
          <Link to="/ranking" className="underline">
            {t('nav.ranking')}
          </Link>
          <Link to="/accuracy" className="underline">
            {t('nav.accuracy')}
          </Link>
        </div>
      </section>
      {engineId !== null && <TopRankedCard engineId={engineId} />}
      {engineId !== null && <ActiveOpportunitiesCard engineId={engineId} />}
      {engineId !== null && <AccuracySummaryCard engineId={engineId} />}
      <AlertsCard />
    </div>
  );
}

/** PLAN §A15 dashboard (TAA-904). */
export function DashboardPage() {
  const { t } = useTranslation();
  const { state, engineId, own } = useEngine();
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.dashboard')}</h1>
      {state === 'ready' &&
        (own && engineId !== null ? (
          <OwnDashboard engineId={engineId} />
        ) : (
          <FeedDashboard engineId={engineId} />
        ))}
    </section>
  );
}
