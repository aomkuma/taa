import { useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { useServerNow } from '@/app/useNow';
import { useEngine } from '@/engine/context';
import { useLiveEvents } from '@/live/context';

import { useAppBadge, useOpportunities } from './hooks';
import { OpportunityDetail } from './OpportunityDetail';
import { activeCount, sortForCards, windowState } from './opportunityModel';
import { OpportunityCard } from './parts';
import { opportunityKeys } from './schemas';

type View = 'open' | 'all';

function OpportunityList({ engineId }: { engineId: string }) {
  const { t } = useTranslation();
  const { own } = useEngine();
  const now = useServerNow(1_000);
  const [view, setView] = useState<View>('open');
  const list = useOpportunities(engineId);
  const items = list.data?.items;
  const sorted = useMemo(() => (items ? sortForCards(items, now) : []), [items, now]);
  useAppBadge(items ? activeCount(items, now) : null);
  const open = sorted.filter((o) => {
    const s = windowState(o, now).status;
    return s === 'ACTIVE' || s === 'CANDIDATE' || s === 'EXPIRING';
  });
  const shown = view === 'open' ? open : sorted;
  const tab = (value: View, label: string) => (
    <button
      type="button"
      aria-pressed={view === value}
      onClick={() => {
        setView(value);
      }}
      className={`rounded px-3 py-1 text-sm ${view === value ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900' : 'border border-slate-300 dark:border-slate-700'}`}
    >
      {label}
    </button>
  );
  if (list.data === undefined) {
    return list.isError ? (
      <p role="alert" className="text-sm text-red-700 dark:text-red-400">
        {t('dashboard.loadFailed')}
      </p>
    ) : (
      <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
    );
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {tab('open', t('opportunities.view.open', { n: open.length }))}
        {tab('all', t('opportunities.view.all', { n: sorted.length }))}
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-slate-500">
          {t(view === 'open' ? 'opportunities.noneOpen' : 'opportunities.none')}
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {shown.map((o) => (
            <OpportunityCard key={o.opportunity_id} opportunity={o} state={windowState(o, now)} own={own} />
          ))}
        </div>
      )}
      <p className="text-xs text-slate-500">{t('opportunities.advice')}</p>
    </div>
  );
}

/** PLAN §A26/§A28 opportunities (TAA-917): live cards, countdowns, statuses and the explainable %. */
export function OpportunitiesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { engineId, state } = useEngine();
  const id = engineId ?? '';
  const { opportunityId } = useParams();
  // an alert or its expiry update arrives as a notification: refresh the cards at once
  useLiveEvents('notifications', () => {
    void queryClient.invalidateQueries({ queryKey: [...opportunityKeys.list(id).slice(0, 3)] });
  });
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.opportunities')}</h1>
      {state === 'ready' && engineId === null ? (
        <p className="text-sm text-slate-500">{t('opportunities.noEngine')}</p>
      ) : opportunityId !== undefined ? (
        <OpportunityDetail engineId={id} id={opportunityId} />
      ) : (
        <OpportunityList engineId={id} />
      )}
    </section>
  );
}
