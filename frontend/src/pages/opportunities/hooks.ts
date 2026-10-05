import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';

import { apiGet } from '@/api/client';

import {
  OpportunitiesPageSchema,
  OpportunityDetailSchema,
  opportunityKeys,
  ScoreboardSchema,
} from './schemas';

/** Opportunities are not a stream topic: poll, and the page refetches on `notifications` events too. */
const REFRESH_MS = 30_000;
const LIMIT = 50;

export function useOpportunities(engineId: string) {
  return useQuery({
    queryKey: opportunityKeys.list(engineId),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/opportunities?limit=${String(LIMIT)}`,
        OpportunitiesPageSchema,
        { signal },
      ),
    refetchInterval: REFRESH_MS,
    enabled: engineId !== '',
  });
}

export function useOpportunity(engineId: string, id: string) {
  return useQuery({
    queryKey: opportunityKeys.detail(engineId, id),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/opportunities/${encodeURIComponent(id)}`,
        OpportunityDetailSchema,
        { signal },
      ),
    refetchInterval: REFRESH_MS,
    enabled: engineId !== '',
  });
}

export function useScoreboard(engineId: string) {
  return useQuery({
    queryKey: opportunityKeys.scoreboard(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/theory-scoreboard`, ScoreboardSchema, { signal }),
    staleTime: 5 * 60_000,
    enabled: engineId !== '',
  });
}

/**
 * The app icon badge = ACTIVE opportunities (R25), where the Badging API exists. The service worker sets it
 * from each push; the page keeps it right while open (windows end without a push).
 */
export function useAppBadge(count: number | null) {
  useEffect(() => {
    if (count === null || !('setAppBadge' in navigator)) return;
    const done = count > 0 ? navigator.setAppBadge(count) : navigator.clearAppBadge();
    done.catch(() => undefined);
  }, [count]);
}
