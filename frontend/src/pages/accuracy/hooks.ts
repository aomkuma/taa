import { useInfiniteQuery, useQuery } from '@tanstack/react-query';

import { ApiError, apiGet } from '@/api/client';

import {
  accuracyKeys,
  AccuracySchema,
  CalibrationSchema,
  ShadowTradesSchema,
  type Source,
  type Variant,
} from './schemas';

/** Shadow trades close on M1 bars; a few minutes' delay is fine for statistics. */
const REFRESH_MS = 5 * 60_000;
const HISTORY_PAGE = 25;

const base = (engineId: string) => `/engines/${encodeURIComponent(engineId)}`;

export function useAccuracy(engineId: string, variant: Variant, mine: boolean) {
  return useQuery({
    queryKey: accuracyKeys.report(engineId, variant, mine),
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({ variant });
      if (mine) query.set('mine', 'true');
      return apiGet(`${base(engineId)}/accuracy?${query.toString()}`, AccuracySchema, { signal });
    },
    refetchInterval: REFRESH_MS,
    enabled: engineId !== '',
  });
}

/** The newest calibration version; `null` before the first one is built. */
export function useCalibration(engineId: string) {
  return useQuery({
    queryKey: accuracyKeys.calibration(engineId),
    queryFn: async ({ signal }) => {
      try {
        return await apiGet(`${base(engineId)}/calibration`, CalibrationSchema, { signal });
      } catch (error) {
        if (error instanceof ApiError && error.code === 'calibration_not_found') return null;
        throw error;
      }
    },
    refetchInterval: REFRESH_MS,
    enabled: engineId !== '',
  });
}

/** Closed shadow trades of one source and variant, newest first, page by page. */
export function useOutcomeHistory(engineId: string, source: Source, variant: Variant) {
  return useInfiniteQuery({
    queryKey: accuracyKeys.history(engineId, source, variant),
    queryFn: ({ pageParam, signal }) => {
      const query = new URLSearchParams({
        status: 'CLOSED',
        source,
        variant,
        limit: String(HISTORY_PAGE),
      });
      if (pageParam) query.set('cursor', pageParam);
      return apiGet(`${base(engineId)}/shadow-trades?${query.toString()}`, ShadowTradesSchema, { signal });
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: engineId !== '',
  });
}
