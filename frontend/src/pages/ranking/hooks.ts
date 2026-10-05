import { useQuery } from '@tanstack/react-query';

import { apiGet } from '@/api/client';

import { rankingKeys, RankingSchema } from './schemas';

/** The engine recomputes the Now score every minute (PLAN §A25 scheduling). */
const REFRESH_MS = 60_000;

export function useRanking(engineId: string) {
  return useQuery({
    queryKey: rankingKeys.list(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/ranking`, RankingSchema, { signal }),
    refetchInterval: REFRESH_MS,
    enabled: engineId !== '',
  });
}
