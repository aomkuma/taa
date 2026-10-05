import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost } from '@/api/client';

import {
  FavouriteToggleSchema,
  PREFERENCES_QUERY_KEY,
  type PreferencesWatchlists,
  PreferencesWatchlistsSchema,
  rankingKeys,
  RankingSchema,
} from './schemas';

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

const FAVOURITES = 'FAVOURITES';

/** The user's favourites (the FAVOURITES watchlist) and a toggle that updates the cached preferences. */
export function useFavourites() {
  const queryClient = useQueryClient();
  const prefs = useQuery({
    queryKey: PREFERENCES_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/advisory/preferences', PreferencesWatchlistsSchema, { signal }),
  });
  const toggle = useMutation({
    mutationFn: (symbol: string) =>
      apiPost(`/advisory/favourites/${encodeURIComponent(symbol)}`, undefined, FavouriteToggleSchema),
    onSuccess: (result) => {
      queryClient.setQueryData<PreferencesWatchlists>(PREFERENCES_QUERY_KEY, (old) => {
        if (!old) return old;
        const has = old.watchlists.some((w) => w.kind === FAVOURITES);
        const watchlists = has
          ? old.watchlists.map((w) => (w.kind === FAVOURITES ? { ...w, symbols: result.favourites } : w))
          : [{ name: 'Favourites', kind: FAVOURITES, symbols: result.favourites }, ...old.watchlists];
        return { ...old, watchlists };
      });
      void queryClient.invalidateQueries({ queryKey: PREFERENCES_QUERY_KEY });
    },
  });
  const favourites = new Set(prefs.data?.watchlists.find((w) => w.kind === FAVOURITES)?.symbols ?? []);
  return { favourites, loaded: prefs.data !== undefined, toggle };
}
