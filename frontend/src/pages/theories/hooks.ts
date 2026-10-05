import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPut } from '@/api/client';
import { PREFERENCES_QUERY_KEY, PreferencesSchema, type Theories } from '@/pages/watchlists/schemas';

import { accountKeys, MyEntitlementsSchema } from '@/pages/account/schemas';

import { CATALOG_QUERY_KEY, CatalogSchema } from './schemas';

/** The detector catalog changes only with a release. */
export function useCatalog() {
  return useQuery({
    queryKey: CATALOG_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/advisory/detectors', CatalogSchema, { signal }),
    staleTime: Infinity,
  });
}

/** `GET /me/entitlements` (shared with the account page). */
export function useEntitlements() {
  return useQuery({
    queryKey: accountKeys.entitlements,
    queryFn: ({ signal }) => apiGet('/me/entitlements', MyEntitlementsSchema, { signal }),
  });
}

/** `PUT /advisory/preferences/theories`: only the theory selection; the answer is the whole document. */
export function useSaveTheories() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (theories: Theories) => apiPut('/advisory/preferences/theories', theories, PreferencesSchema),
    onSuccess: (data) => {
      queryClient.setQueryData(PREFERENCES_QUERY_KEY, data);
    },
  });
}
