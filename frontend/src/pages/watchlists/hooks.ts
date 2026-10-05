import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDelete, apiGet, apiPost, apiPut } from '@/api/client';

import {
  type AlertPreferences,
  FavouriteToggleSchema,
  type Preferences,
  PREFERENCES_QUERY_KEY,
  PreferencesSchema,
  type Watchlist,
  WatchlistsSchema,
} from './schemas';

/** The session user's advisory preferences (one cached document shared by every page that reads it). */
export function usePreferences() {
  return useQuery({
    queryKey: PREFERENCES_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/advisory/preferences', PreferencesSchema, { signal }),
  });
}

function useSetWatchlists() {
  const queryClient = useQueryClient();
  return (watchlists: Watchlist[]) => {
    queryClient.setQueryData<Preferences>(PREFERENCES_QUERY_KEY, (old) => old && { ...old, watchlists });
    void queryClient.invalidateQueries({ queryKey: PREFERENCES_QUERY_KEY });
  };
}

const listPath = (name: string) => `/advisory/watchlists/${encodeURIComponent(name)}`;

/** Create, replace (also renames: the body carries the new name) and delete watchlists. */
export function useWatchlistMutations() {
  const setWatchlists = useSetWatchlists();
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: (list: Watchlist) => apiPost('/advisory/watchlists', list, WatchlistsSchema),
    onSuccess: (data) => {
      setWatchlists(data.watchlists);
    },
  });
  const replace = useMutation({
    mutationFn: ({ name, list }: { name: string; list: Watchlist }) =>
      apiPut(listPath(name), list, WatchlistsSchema),
    onSuccess: (data) => {
      setWatchlists(data.watchlists);
    },
  });
  const remove = useMutation({
    mutationFn: (name: string) => apiDelete(listPath(name)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PREFERENCES_QUERY_KEY }),
  });
  return { create, replace, remove };
}

/**
 * Saves the alert settings: a PUT of the whole document with only `alerts` changed. The document is read
 * again first, so sections changed elsewhere since the page loaded (watchlists, theories) are kept.
 */
export function useSaveAlerts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (alerts: AlertPreferences) => {
      const current = await apiGet('/advisory/preferences', PreferencesSchema);
      return apiPut('/advisory/preferences', { ...current, alerts }, PreferencesSchema);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(PREFERENCES_QUERY_KEY, data);
    },
  });
}

const FAVOURITES = 'FAVOURITES';

/** The user's favourites (the FAVOURITES watchlist) and a toggle that updates the cached preferences. */
export function useFavourites() {
  const prefs = usePreferences();
  const setWatchlists = useSetWatchlists();
  const toggle = useMutation({
    mutationFn: (symbol: string) =>
      apiPost(`/advisory/favourites/${encodeURIComponent(symbol)}`, undefined, FavouriteToggleSchema),
    onSuccess: (result) => {
      const old = prefs.data?.watchlists ?? [];
      const has = old.some((w) => w.kind === FAVOURITES);
      setWatchlists(
        has
          ? old.map((w) => (w.kind === FAVOURITES ? { ...w, symbols: result.favourites } : w))
          : [
              {
                name: 'Favourites',
                kind: FAVOURITES,
                symbols: result.favourites,
                top_n: null,
                alerts: true,
                threshold: null,
              },
              ...old,
            ],
      );
    },
  });
  const favourites = new Set(prefs.data?.watchlists.find((w) => w.kind === FAVOURITES)?.symbols ?? []);
  return { favourites, loaded: prefs.data !== undefined, toggle };
}
