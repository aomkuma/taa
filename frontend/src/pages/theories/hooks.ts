import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPut } from '@/api/client';
import { PREFERENCES_QUERY_KEY, PreferencesSchema, type Theories } from '@/pages/watchlists/schemas';

import { CATALOG_QUERY_KEY, CatalogSchema, ENTITLEMENTS_QUERY_KEY, EntitlementsSchema } from './schemas';

/** The detector catalog changes only with a release. */
export function useCatalog() {
  return useQuery({
    queryKey: CATALOG_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/advisory/detectors', CatalogSchema, { signal }),
    staleTime: Infinity,
  });
}

export function useEntitlements() {
  return useQuery({
    queryKey: ENTITLEMENTS_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/me/entitlements', EntitlementsSchema, { signal }),
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
